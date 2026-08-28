"""A BuildPlan is the fully-resolved answer to "what goes on this USB".

It is pure data derived from a :class:`Machine` — no downloads, no disk I/O —
so it can be printed by ``ocforge plan`` and consumed by ``ocforge build``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocforge.catalog import acpi, kexts, macos
from ocforge.model import Chassis, Machine, Vendor

# SMBIOS model per hardware class. Chosen for a still-supported board-id with
# the right core count / graphics expectations; the serial is generated later.
_SMBIOS = {
    "amd_desktop": "iMacPro1,1",
    "amd_desktop_navi": "MacPro7,1",
    "intel_desktop": "iMac20,1",
    "intel_desktop_old": "iMac19,1",
    "intel_laptop": "MacBookPro16,1",
    "intel_laptop_old": "MacBookPro15,1",
}


def pick_smbios(m: Machine, target: macos.MacOSRelease) -> str:
    if m.cpu.vendor is Vendor.AMD:
        navi = m.dgpu is not None and m.dgpu.vendor is Vendor.AMD
        return _SMBIOS["amd_desktop_navi"] if navi else _SMBIOS["amd_desktop"]
    if m.is_laptop:
        return _SMBIOS["intel_laptop"] if m.cpu.intel_gen >= 8 else _SMBIOS["intel_laptop_old"]
    if m.cpu.intel_gen >= 9:
        return _SMBIOS["intel_desktop"]
    return _SMBIOS["intel_desktop_old"]


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


def make(m: Machine, *, target_major: int | None = None) -> BuildPlan:
    # Pre-Sandy-Bridge Intel (Nehalem/Westmere and older) has no supported
    # graphics path on any macOS ocforge targets — fail loud, not vague.
    if m.cpu.vendor is Vendor.INTEL and 0 < m.cpu.intel_gen < 2:
        raise ValueError(
            f"{m.cpu.brand or 'this CPU'} is 1st-gen Intel Core (pre-Sandy-Bridge); "
            "the oldest supported target here is Sandy Bridge on Big Sur. Not buildable."
        )

    target = macos.by_major(target_major) if target_major else macos.recommended(m)
    if target is None:
        why = "no supported macOS release for this machine"
        if m.cpu.vendor is Vendor.INTEL and 0 < m.cpu.intel_gen < 3:
            why += " (pre-Ivy-Bridge Intel — try --macos 11/12 at your own risk)"
        raise ValueError(why)

    warnings: list[str] = []
    if m.chassis is Chassis.UNKNOWN:
        warnings.append("chassis type unknown — assuming desktop for ACPI/SMBIOS")
    if m.cpu.vendor is Vendor.UNKNOWN:
        warnings.append("CPU vendor unknown — kernel quirks may be wrong")
    if not m.wired_nics and m.wifi is None:
        warnings.append("no supported NIC detected — you may have no network in the installer")
    _brand = (m.cpu.brand or "").lower()
    if m.cpu.vendor is Vendor.INTEL and ("pentium" in _brand or "celeron" in _brand):
        if m.cpu.intel_gen:
            warnings.append("Pentium/Celeron: CPUID is spoofed to the same-gen i3 "
                            "(Emulate -> Cpuid1Data) -- required or macOS panics")
        else:
            warnings.append("Pentium/Celeron with unknown generation — CPUID spoof "
                            "can't be applied; pass --spec after fixing cpu.intel_gen")
    if m.wifi is not None and m.wifi.vendor not in _WIFI_OK:
        warnings.append(
            f"Wi-Fi chip is {m.wifi.vendor.value} — no macOS driver exists "
            "(Atheros/MediaTek/Killer-WiFi); use a supported card or a USB adapter"
        )
    if m.cpu.vendor is Vendor.AMD:
        warnings.append("AMD build: kernel patches are spliced from AMD_Vanilla; verify the core count")
        if not m.firmware.board_name:
            warnings.append("AMD board model unknown — if it's B550/A520 or AM5, add SSDT-CPUR by hand")

    return BuildPlan(
        machine=m,
        target=target,
        smbios_model=pick_smbios(m, target),
        kexts=kexts.resolve(m, target),
        ssdts=acpi.select(m),
        acpi_patches=acpi.patches(m),
        manual_acpi=acpi.needs_generation(m),
        warnings=warnings,
    )
