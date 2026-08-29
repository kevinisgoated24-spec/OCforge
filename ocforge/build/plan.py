"""A BuildPlan is the fully-resolved answer to "what goes on this USB".

It is pure data derived from a :class:`Machine` — no downloads, no disk I/O —
so it can be printed by ``ocforge plan`` and consumed by ``ocforge build``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocforge.catalog import acpi, bios, kexts, macos
from ocforge.model import Chassis, Machine, Vendor

# SMBIOS model per hardware class. Chosen for a still-supported board-id with
# the right core count / graphics expectations; the serial is generated later.
_SMBIOS = {
    "amd_desktop": "iMacPro1,1",
    "amd_desktop_navi": "MacPro7,1",
    "intel_desktop_igpu": "Macmini8,1",   # Coffee Lake, UHD 630 as the only GPU
    "intel_laptop": "MacBookPro16,1",
    "intel_laptop_old": "MacBookPro15,1",
}

# Desktop Intel SMBIOS per generation: (iGPU drives the display, dGPU drives
# it instead). Per Dortania's desktop guides — a generation's own models get
# bumped to a newer sibling once Apple drops them for a later macOS; ocforge
# never targets anything older than Big Sur (11), so the pre-Big-Sur options
# each guide also lists aren't reachable here and are skipped.
def _intel_desktop_smbios(gen: int, target_major: int) -> tuple[str, str]:
    if gen <= 2:  # Sandy Bridge: iGPU has no driver past 10.13 (unreachable
        # here already, see catalog.macos) -- MacPro6,1 either way.
        return "MacPro6,1", "MacPro6,1"
    if gen == 3:  # Ivy Bridge: iGPU capped at Big Sur (see catalog.macos);
        # Monterey+ needs the dGPU driving it through MacPro6,1.
        return "iMac14,4", ("iMac15,1" if target_major <= 11 else "MacPro6,1")
    if gen == 4:  # Haswell: own models dropped in Monterey, bump to Broadwell's.
        return (("iMac14,4", "iMac15,1") if target_major <= 11
                else ("iMac16,2", "iMac17,1"))
    if gen == 5:  # Broadwell: same models cover Big Sur and Monterey.
        return "iMac16,2", "iMac17,1"
    if gen == 6:  # Skylake: dropped in Ventura, bump to Kaby Lake's.
        return (("iMac17,1", "iMac17,1") if target_major <= 12
                else ("iMac18,1", "iMac18,3"))
    if gen == 7:  # Kaby Lake
        return "iMac18,1", "iMac18,3"
    return "iMac19,1", "iMac19,1"  # Coffee Lake (8/9): one model either way


def pick_smbios(m: Machine, target: macos.MacOSRelease) -> str:
    if m.cpu.vendor is Vendor.AMD:
        navi = m.dgpu is not None and m.dgpu.vendor is Vendor.AMD
        return _SMBIOS["amd_desktop_navi"] if navi else _SMBIOS["amd_desktop"]
    if m.is_laptop:
        return _SMBIOS["intel_laptop"] if m.cpu.intel_gen >= 8 else _SMBIOS["intel_laptop_old"]
    # iGPU-only Coffee Lake desktop -> Mac mini (the iMac models assume a dGPU)
    if m.igpu is not None and m.dgpu is None and 8 <= m.cpu.intel_gen <= 9:
        return _SMBIOS["intel_desktop_igpu"]
    if m.cpu.intel_gen >= 10:
        return "iMac20,1"  # Comet Lake
    igpu_model, dgpu_model = _intel_desktop_smbios(m.cpu.intel_gen, target.major)
    return dgpu_model if m.dgpu is not None else igpu_model


@dataclass
class BuildPlan:
    machine: Machine
    target: macos.MacOSRelease
    smbios_model: str
    kexts: list[kexts.Selected]
    ssdts: list[acpi.Ssdt]
    acpi_patches: list[dict] = field(default_factory=list)
    manual_acpi: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    bios: list[str] = field(default_factory=list)

    @property
    def is_amd(self) -> bool:
        return self.machine.cpu.vendor is Vendor.AMD

    @property
    def boot_args(self) -> list[str]:
        args = ["-v", "debug=0x100", "keepsyms=1"]
        if self.smbios_model not in ("iMac20,1", "iMac19,1", "MacBookPro16,1"):
            args.append("-no_compat_check")
        if self.is_amd:
            args.append("npci=0x2000")
        if self.machine.dgpu and self.machine.dgpu.vendor is Vendor.NVIDIA:
            args.append("nv_disable=1")
        dg = self.machine.dgpu
        if dg and dg.vendor is Vendor.AMD:
            try:  # Navi (RX 5000+) needs agdpmod=pikera or it black-screens on boot
                if int(dg.pci.device, 16) >= 0x7300:
                    args.append("agdpmod=pikera")
            except (ValueError, AttributeError):
                pass
        if self.machine.is_laptop and self.machine.igpu and self.machine.igpu.vendor is Vendor.INTEL:
            args.append("igfxonln=1")
        if self.target.darwin >= 24:  # Sequoia+
            args.append("-lilubetaall")
        return args


# Wi-Fi vendors with a working modern-macOS driver path.
_WIFI_OK = (Vendor.INTEL, Vendor.BROADCOM, Vendor.APPLE, Vendor.UNKNOWN)


def make(m: Machine, *, target_major: int | None = None,
        allow_unsupported_gpu: bool = False) -> BuildPlan:
    # An old spec (or an unparseable CPU brand) can leave intel_gen at 0; if
    # there's an Intel iGPU, recover the generation from its device id.
    from ocforge.probe.base import backfill_intel_gen

    backfill_intel_gen(m)

    # Pre-Sandy-Bridge Intel (Nehalem/Westmere and older) has no supported
    # graphics path on any macOS ocforge targets — fail loud, not vague.
    if m.cpu.vendor is Vendor.INTEL and 0 < m.cpu.intel_gen < 2:
        raise ValueError(
            f"{m.cpu.brand or 'this CPU'} is 1st-gen Intel Core (pre-Sandy-Bridge); "
            "the oldest supported target here is Sandy Bridge on Big Sur. Not buildable."
        )

    # No iGPU and no supported (AMD) dGPU -> macOS has nothing to drive a
    # display with once it hands off from the boot picker. Checked
    # unconditionally, ahead of --macos N, since forcing a version doesn't
    # change what the hardware can do. A caller can pass
    # allow_unsupported_gpu=True to proceed anyway (after asking the user).
    gpu_unsupported = not macos.has_display_path(m)
    if gpu_unsupported and not allow_unsupported_gpu:
        gpu = f"the {m.dgpu.vendor.value} dGPU ({m.dgpu.name or 'unnamed'})" if m.dgpu else "no GPU"
        raise macos.UnsupportedGpuError(
            f"no supported graphics — {gpu} has no macOS driver, and there's no Intel "
            "iGPU to fall back on. Needs an Intel iGPU or a supported AMD dGPU."
        )

    target = (macos.by_major(target_major) if target_major
             else macos.recommended(m, ignore_gpu=gpu_unsupported))
    if target is None:
        why = "no supported macOS release for this machine"
        if m.cpu.vendor is Vendor.INTEL and 0 < m.cpu.intel_gen < 3:
            why += " (pre-Ivy-Bridge Intel — try --macos 11/12 at your own risk)"
        raise ValueError(why)

    warnings: list[str] = []
    if gpu_unsupported:
        warnings.append(
            "UNSUPPORTED BUILD — no working display path was detected (needs an Intel "
            "iGPU or an AMD dGPU) and this build was forced through anyway. macOS will "
            "very likely show nothing once it hands off from the boot picker. Proceed "
            "only if you know something ocforge doesn't (an eGPU, a card you're adding "
            "later, etc.)."
        )
    if m.chassis is Chassis.UNKNOWN:
        warnings.append("chassis type unknown — assuming desktop for ACPI/SMBIOS")
    if m.cpu.vendor is Vendor.UNKNOWN:
        warnings.append("CPU vendor unknown — kernel quirks may be wrong")
    if not m.wired_nics and m.wifi is None:
        warnings.append("no supported NIC detected — you may have no network in the installer")
    from ocforge.build.config import is_pentium_or_celeron

    if is_pentium_or_celeron(m):
        if m.cpu.intel_gen:
            warnings.append("Pentium/Celeron: CPUID is spoofed to the same-gen i3 "
                            "(Emulate -> Cpuid1Data) -- required or macOS panics")
        else:
            warnings.append("Pentium/Celeron with unknown generation — CPUID spoof "
                            "can't be applied; check cpu.intel_gen in the spec")
        if target.major >= 13:
            warnings.append(f"Pentium/Celeron have no AVX2, but macOS {target.major} "
                            "needs it -- this build will not boot; use --macos 12 (Monterey)")
    if m.dgpu is not None and m.dgpu.vendor is Vendor.NVIDIA and m.igpu is not None:
        # A no-iGPU machine with only this NVIDIA card already got the
        # UNSUPPORTED BUILD warning above (or was rejected outright); this
        # one's for the common case where the iGPU is quietly picking up
        # the slack and it's easy not to notice the dGPU is dead weight.
        warnings.append(
            f"{m.dgpu.name or 'the NVIDIA dGPU'} has no macOS driver — it's disabled "
            "(nv_disable=1); the iGPU drives the display, no GPU acceleration/CUDA "
            "in macOS from this card"
        )
    if m.wifi is not None and m.wifi.vendor not in _WIFI_OK:
        warnings.append(
            f"Wi-Fi chip is {m.wifi.vendor.value} — no macOS driver exists "
            "(Atheros/MediaTek/Killer-WiFi); use a supported card or a USB adapter"
        )
    if m.cpu.vendor is Vendor.AMD:
        warnings.append("AMD build: kernel patches are spliced from AMD_Vanilla; verify the core count")
        if not m.firmware.board_name:
            warnings.append("AMD board model unknown — if it's B550/A520 or AM5, add SSDT-CPUR by hand")
    _bv = (m.firmware.board_vendor or "").lower()
    if any(v in _bv for v in ("dell", "hewlett", "hp ", "lenovo")):
        warnings.append("OEM firmware (Dell/HP/Lenovo) can lack the MAT table -- if the "
                        "build panics or hangs early, rebuild with --legacy-mmap")

    return BuildPlan(
        machine=m,
        target=target,
        smbios_model=pick_smbios(m, target),
        kexts=kexts.resolve(m, target),
        ssdts=acpi.select(m),
        acpi_patches=acpi.patches(m),
        manual_acpi=acpi.needs_generation(m),
        bios=bios.checklist(m),
        warnings=warnings,
    )
