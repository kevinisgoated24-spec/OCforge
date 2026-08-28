"""Turn a BuildPlan into an EFI/ folder (and optionally onto a USB).

    plan ──► fetch OpenCore + OcBinaryData
         ──► scaffold EFI/
         ──► fetch + place kexts, SSDTs
         ──► generate SMBIOS, splice AMD patches
         ──► assemble config.plist, reconcile against what actually landed
         ──► write config
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ocforge.build import config as config_
from ocforge.build import layout
from ocforge.build import ssdtgen
from ocforge.build.plan import BuildPlan
from ocforge.build.smbios import generate as gen_smbios
from ocforge.fetch import acpi as fetch_acpi
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
    src = work / "acpi-in"
    if dsdt is not None:
        log(f"staging supplied DSDT: {dsdt}")
        acpi_dir = acpi_dump.stage_supplied(dsdt, src)
    elif dump_dsdt and acpi_dump.can_dump():
        log("dumping this host's ACPI tables…")
        try:
            acpi_dir = acpi_dump.dump_tables(src)
        except acpi_dump.DsdtUnavailable as exc:
            log(f"  can't dump ACPI ({exc}); using precompiled SSDTs")
            return None
    else:
        return None

    st_dir = fetch_ssdttime.fetch(work)
    res = ssdtgen.run(st_dir, acpi_dir, ssdtgen.plan_ops(plan.machine), log=log)
    if not res.ok:
        log(f"  SSDTTime did not produce usable output ({res.error}); "
            "using precompiled SSDTs")
        return None
    log(f"  SSDTTime built {len(res.aml)} SSDT(s): "
        f"{', '.join(p.name for p in res.aml)}")
    return res


def build_efi(plan: BuildPlan, work: Path, out: Path, *, log: Log = lambda _: None,
              debug: bool = False, dsdt: Path | None = None,
              dump_dsdt: bool = False, recovery_major: int | None = None) -> BuildReport:
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

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
        acpi_patch=gen.acpi_patch if gen else None,
        acpi_delete=gen.acpi_delete if gen else None,
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
        manual_todo=list(plan.manual_acpi),
        smbios_model=sm.model,
        used_placeholder_smbios=macserial is None,
        ssdt_source=ssdt_source,
        recovery_dir=recovery_dir,
        recovery_error=recovery_error,
    )


def build_usb(plan: BuildPlan, work: Path, device: str, *, recovery_major: int | None = None,
              log: Log = lambda _: None, dsdt: Path | None = None,
              dump_dsdt: bool = False) -> BuildReport:
    from ocforge.fetch import recovery as fetch_recovery
    from ocforge.media import write as media

    report = build_efi(plan, work, work / "staging", log=log, dsdt=dsdt, dump_dsdt=dump_dsdt)

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
