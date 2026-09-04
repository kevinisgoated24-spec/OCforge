"""Turn a BuildPlan into an EFI/ folder (and optionally onto a USB).

    plan ──► fetch OpenCore + OcBinaryData
         ──► scaffold EFI/
         ──► fetch + place kexts, SSDTs
         ──► generate SMBIOS, splice AMD patches
         ──► assemble config.plist, reconcile against what actually landed
         ──► write config
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ocforge.build import config as config_
from ocforge.build import layout
from ocforge.build import ssdtgen
from ocforge.build.plan import BuildPlan
from ocforge.build.smbios import generate as gen_smbios
from ocforge.fetch import acpi as fetch_acpi
from ocforge.fetch import acpidump as fetch_acpidump
from ocforge.fetch import github as fetch_github
from ocforge.fetch import kexts as fetch_kexts
from ocforge.fetch import ocbinary, opencore
from ocforge.fetch import ssdttime as fetch_ssdttime
from ocforge.model import Vendor
from ocforge.probe import acpi_dump

Log = Callable[[str], None]


@dataclass
class BuildReport:
    efi_dir: Path
    config_path: Path
    kext_failures: list[str] = field(default_factory=list)
    ssdt_failures: list[str] = field(default_factory=list)
    manual_todo: list[str] = field(default_factory=list)
    smbios_model: str = ""
    used_placeholder_smbios: bool = False
    ssdt_source: str = "precompiled"  # or "ssdttime"
    recovery_dir: Path | None = None
    recovery_error: str | None = None

    @property
    def ok(self) -> bool:
        return not self.kext_failures and not self.ssdt_failures


def _run_ssdttime(plan: BuildPlan, work: Path, *, dsdt: Path | None, dump_dsdt: bool,
                  log: Log) -> ssdtgen.SsdtResult | None:
    """Stage the target's ACPI tables and let SSDTTime build the SSDTs.

    Returns ``None`` when there is nothing to work from (no ``--dsdt`` and the
    host can't dump its own tables), leaving the precompiled path in charge.
    """
    m = plan.machine
    # Linux reads its own tables straight from sysfs; Windows can dump too,
    # but needs acpidump.exe fetched first (see fetch/acpidump.py). macOS has
    # no automatic path at all -- SSDTTime's own dumper doesn't implement one.
    host_can_dump = acpi_dump.can_dump() or sys.platform == "win32"

    # A laptop's I2C-HID trackpad only gets a real SSDT-GPIO when we can see
    # the DSDT (see gpio.py) — without --dsdt/--dump-dsdt that silently never
    # happens, just a manual-TODO note easy to miss. When this host can dump
    # its own tables and it's a laptop with that kind of trackpad, auto-dump
    # even without being asked; --dsdt/--dump-dsdt still win if given.
    auto_gpio = (dsdt is None and not dump_dsdt and m.is_laptop
                and m.inputs.touchpad_bus == "i2c-hid" and host_can_dump)
    if auto_gpio:
        log("laptop with an I2C-HID trackpad — auto-dumping ACPI tables for SSDT-GPIO…")
        dump_dsdt = True

    if dsdt is None and not (dump_dsdt and host_can_dump):
        if dump_dsdt:
            log("  can't dump ACPI on this host (no automatic path — pass --dsdt instead); "
                "using precompiled SSDTs")
        return None

    src = work / "acpi-in"
    if dsdt is not None:
        log(f"staging supplied DSDT: {dsdt}")
        acpi_dir = acpi_dump.stage_supplied(dsdt, src)
    else:
        log("dumping this host's ACPI tables…")
        try:
            acpidump_exe = fetch_acpidump.fetch(work) if sys.platform == "win32" else None
            acpi_dir = acpi_dump.dump_tables(src, acpidump_exe=acpidump_exe)
        except acpi_dump.DsdtUnavailable as exc:
            extra = " — no SSDT-GPIO, but the build's still fine without it" if auto_gpio else ""
            log(f"  can't dump ACPI ({exc}); using precompiled SSDTs{extra}")
            return None

    st_dir = fetch_ssdttime.fetch(work)  # for iasl, to decompile/compile
    res = ssdtgen.run(st_dir, acpi_dir, ssdtgen.plan_ops(plan.machine), log=log)
    if not res.ok:
        log(f"  SSDTTime did not produce usable output ({res.error}); "
            "using precompiled SSDTs")
        return None
    log(f"  SSDTTime built {len(res.aml)} SSDT(s): "
        f"{', '.join(p.name for p in res.aml)}")

    # I2C-HID trackpad: try SSDT-GPIO straight from the DSDT
    if plan.machine.inputs.touchpad_bus == "i2c-hid":
        from ocforge.build import gpio

        try:
            finding = gpio.generate(acpi_dir, st_dir, work / "gpio")
        except Exception as exc:  # noqa: BLE001 - GPIO gen is best-effort
            log(f"  SSDT-GPIO probe failed: {exc}")
            finding = None
        if finding and finding.generated:
            res.aml.append(finding.generated)
            res.acpi_add.append({
                "Comment": "SSDT-GPIO (ocforge, from DSDT)",
                "Enabled": True, "Path": finding.generated.name,
            })
            res.extra_todo.append(finding.todo() + " — VERIFY the trackpad works")
            log(f"  {finding.todo()}")
        elif finding:
            res.extra_todo.append(finding.todo() + " — build SSDT-GPIO by hand")
            log(f"  {finding.todo()} (not auto-generated)")

    # Prebuilt SSDTs SSDTTime can't make headless (XOSI, IMEI, CPUR, RHUB, UNC,
    # RTC0-RANGE-HEDT) still come from Dortania, plus any ACPI rename they need.
    from ocforge.catalog import acpi as acpi_cat

    _covered = {"SSDT-EC-USBX", "SSDT-EC", "SSDT-PLUG", "SSDT-AWAC", "SSDT-PMC", "SSDT-PNLF"}
    extra = [s for s in acpi_cat.select(plan.machine) if s.name not in _covered]
    if extra:
        log(f"  fetching {len(extra)} prebuilt SSDT(s) SSDTTime can't generate: "
            f"{', '.join(s.name for s in extra)}")
        for r in fetch_acpi.fetch_all(extra, work / "acpi-extra"):
            if r.path is not None:
                res.aml.append(r.path)
                res.acpi_add.append({"Comment": r.name, "Enabled": True, "Path": r.path.name})
    res.acpi_patch.extend(acpi_cat.patches(plan.machine))
    return res


def build_efi(plan: BuildPlan, work: Path, out: Path, *, log: Log = lambda _: None,
              debug: bool = False, dsdt: Path | None = None,
              dump_dsdt: bool = False, recovery_major: int | None = None,
              legacy_mmap: bool = False) -> BuildReport:
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    fetch_github.set_cache_dir(work / ".gh-cache")  # dedupe/persist release lookups

    if plan.spoof_devices and not debug:
        log("device-id spoof active -> forcing the OpenCore DEBUG build for easier troubleshooting")
        debug = True

    log("fetching OpenCore…")
    oc_src = opencore.fetch(work, debug=debug)
    log("fetching OcBinaryData…")
    ocb = ocbinary.fetch(work)

    log("scaffolding EFI/…")
    oc = layout.scaffold(oc_src, out)
    layout.add_hfsplus(oc, ocb)
    layout.add_resources(oc, ocb)

    log(f"fetching {len(plan.kexts)} kexts…")
    kres = fetch_kexts.fetch_all(plan.kexts, work, work / "kexts")
    good_kexts = {r.name for r in kres if r.bundle_dir is not None}
    layout.place_kexts(oc, [r.bundle_dir for r in kres if r.bundle_dir is not None])
    kext_failures = [f"{r.name}: {r.error}" for r in kres if r.bundle_dir is None and r.error and "generated" not in r.error]

    gen = _run_ssdttime(plan, work, dsdt=dsdt, dump_dsdt=dump_dsdt, log=log)
    if gen is not None:
        layout.place_acpi(oc, gen.aml)
        ssdt_failures: list[str] = []
        ssdt_source = "ssdttime"
    else:
        log(f"fetching {len(plan.ssdts)} SSDTs…")
        sres = fetch_acpi.fetch_all(plan.ssdts, work / "acpi")
        layout.place_acpi(oc, [r.path for r in sres if r.path is not None])
        ssdt_failures = [f"{r.name}: {r.error}" for r in sres if r.path is None]
        ssdt_source = "precompiled"

    log("generating SMBIOS…")
    macserial = opencore.macserial_binary(oc_src)
    sm = gen_smbios(plan.smbios_model, macserial)

    amd_patches = None
    if plan.machine.cpu.vendor is Vendor.AMD:
        log("splicing AMD_Vanilla kernel patches…")
        from ocforge.build.amdvanilla import fetch as fetch_amd

        try:
            amd_patches = fetch_amd(plan.machine.cpu.cores or 1)
        except Exception as exc:  # noqa: BLE001 - AMD patch fetch is best-effort; surfaced below
            kext_failures.append(f"AMD_Vanilla patches: {exc}")

    log("assembling config.plist…")
    cfg = config_.assemble(
        plan, sm, amd_patches=amd_patches,
        acpi_add=gen.acpi_add if gen else None,
        acpi_patch=(gen.acpi_patch if gen else plan.acpi_patches) or None,
        acpi_delete=gen.acpi_delete if gen else None,
        legacy_mmap=legacy_mmap,
    )

    # reconcile config against what actually made it onto disk
    cfg["Kernel"]["Add"] = [
        e for e in cfg["Kernel"]["Add"] if e["BundlePath"].removesuffix(".kext") in good_kexts
    ]
    dropped_acpi = layout.prune_dead_acpi(cfg, oc)
    if dropped_acpi:
        log(f"  dropped {dropped_acpi} ACPI entr(y/ies) with no .aml")
    layout.fixup_kext_paths(cfg, oc)

    config_path = layout.write_config(oc, cfg)
    log(f"wrote {config_path}")

    recovery_dir: Path | None = None
    recovery_error: str | None = None
    if recovery_major:
        from ocforge.fetch import recovery as fetch_recovery

        log(f"downloading macOS {recovery_major} recovery (this is the slow part)…")
        try:
            recovery_dir = fetch_recovery.download(recovery_major, oc_src, out, work=work)
            log(f"  recovery staged at {recovery_dir}")
        except fetch_recovery.RecoveryError as exc:
            recovery_error = str(exc)
            log(f"  recovery download failed: {exc}")

    return BuildReport(
        efi_dir=out / "EFI",
        config_path=config_path,
        kext_failures=kext_failures,
        ssdt_failures=ssdt_failures,
        smbios_model=sm.model,
        used_placeholder_smbios=macserial is None,
        ssdt_source=ssdt_source,
        recovery_dir=recovery_dir,
        recovery_error=recovery_error,
        manual_todo=list(plan.manual_acpi) + (gen.extra_todo if gen else []),
    )


def build_usb(plan: BuildPlan, work: Path, device: str, *, recovery_major: int | None = None,
              log: Log = lambda _: None, dsdt: Path | None = None,
              dump_dsdt: bool = False, legacy_mmap: bool = False) -> BuildReport:
    from ocforge.fetch import recovery as fetch_recovery
    from ocforge.media import write as media

    report = build_efi(plan, work, work / "staging", log=log, dsdt=dsdt,
                       dump_dsdt=dump_dsdt, legacy_mmap=legacy_mmap)

    recovery_boot = None
    if recovery_major:
        log("downloading macOS recovery (this is the slow part)…")
        recovery_boot = fetch_recovery.download(
            recovery_major, work / "opencore", work / "recovery", work=work
        )

    log(f"formatting {device} and writing payload…")
    mount = media.format_and_mount(device)
    try:
        media.write_payload(mount, report.efi_dir, recovery_boot)
    finally:
        media.unmount(device)
    log("done — USB is bootable.")
    return report
