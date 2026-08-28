"""Explain the config.plist ocforge would write for a machine.

:func:`explain` walks the same conditions :mod:`ocforge.build.config`,
:mod:`ocforge.build.plan` and :mod:`ocforge.catalog` use, and emits a flat
list of :class:`Decision` - *what* was set and *why*, tied to the detected
hardware. It's a read-only view for ``ocforge explain`` and the GUI; it never
builds anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from ocforge.build.config import _IG_PLATFORM
from ocforge.build.plan import BuildPlan
from ocforge.catalog import macos
from ocforge.model import Vendor


@dataclass(frozen=True)
class Decision:
    section: str
    setting: str
    value: str
    reason: str


_BOOT_ARG_WHY = {
    "-v": "verbose boot - shows the log instead of the Apple logo; drop it once stable",
    "debug=0x100": "don't reboot on a kernel panic - keep the panic screen up to read it",
    "keepsyms=1": "print symbol names in panic backtraces",
    "npci=0x2000": "skip PCI enumeration past the config stage - avoids early hangs on AMD",
    "nv_disable=1": "no macOS driver for this NVIDIA card - disable it so the desktop loads",
    "agdpmod=pikera": "patch the board-id check that black-screens Navi (RX 5000+) GPUs",
    "igfxonln=1": "force Intel laptop display connectors online (fixes a black internal panel)",
    "-lilubetaall": "macOS is newer than Lilu's whitelist - let Lilu + plugins run anyway",
}


def _macos_reason(plan: BuildPlan) -> str:
    for c in macos.evaluate(plan.machine):
        if c.release.major == plan.target.major:
            return c.note or "newest release this hardware runs cleanly"
    return "forced target"


def _smbios_reason(plan: BuildPlan) -> str:
    m = plan.machine
    if m.cpu.vendor is Vendor.AMD:
        if m.dgpu is not None and m.dgpu.vendor is Vendor.AMD:
            return "AMD desktop with an AMD dGPU - MacPro7,1 expects discrete AMD graphics, no iGPU"
        return "AMD desktop - iMacPro1,1 is the safe no-iGPU profile"
    if m.is_laptop:
        return ("Intel laptop, 8th-gen+ - MacBookPro16,1"
                if m.cpu.intel_gen >= 8 else
                "Intel laptop, pre-8th-gen - MacBookPro15,1")
    if m.cpu.intel_gen >= 9:
        return "Intel desktop, 9th-gen+ - iMac20,1"
    return "Intel desktop, pre-9th-gen - iMac19,1"


def explain(plan: BuildPlan) -> list[Decision]:
    m = plan.machine
    cpu = m.cpu
    gen = cpu.intel_gen
    amd = plan.is_amd
    intel = cpu.vendor is Vendor.INTEL
    board = m.firmware.board_name.lower()
    z390 = any(x in board for x in ("z390", "z490"))
    modern_mmap = amd or (intel and gen >= 8)

    out: list[Decision] = []

    # --- platform ----------------------------------------------------------
    out.append(Decision(
        "macOS", "target",
        f"{plan.target.name} {plan.target.major} (darwin {plan.target.darwin})",
        _macos_reason(plan)))
    out.append(Decision(
        "SMBIOS", "PlatformInfo > Generic > SystemProductName",
        plan.smbios_model, _smbios_reason(plan)))

    # --- boot-args -------------------------------------------------------
    for arg in plan.boot_args:
        why = _BOOT_ARG_WHY.get(arg)
        if arg == "-no_compat_check":
            why = (f"{plan.smbios_model} isn't the Mac this hardware matches - "
                   "skip the model/OS compatibility gate")
        out.append(Decision("boot-args", arg, "on", why or "standard"))

    # --- Booter quirks (the hardware-driven ones) -------------------------
    if modern_mmap:
        src = "AMD" if amd else f"Intel {gen}th-gen"
        out.append(Decision("Booter", "Quirks > RebuildAppleMemoryMap", "True",
                            f"{src} firmware hands over a clean memory map"))
        out.append(Decision("Booter", "Quirks > EnableWriteUnprotector", "False",
                            "not needed with a modern memory map - safer left off"))
        out.append(Decision("Booter", "Quirks > SyncRuntimePermissions", "True",
                            "realign runtime page permissions after the rebuild"))
    else:
        out.append(Decision("Booter", "Quirks > EnableWriteUnprotector", "True",
                            "older firmware - unlock the memory map the legacy way"))
    if not (amd or gen >= 11 or z390):
        out.append(Decision("Booter", "Quirks > SetupVirtualMap", "True",
                            "pre-300-series Intel - sandbox the virtual address map"))
    else:
        out.append(Decision("Booter", "Quirks > SetupVirtualMap", "False",
                            "AMD / Z390 / 11th-gen+ firmware maps runtime services correctly"))
    if z390 or gen >= 11:
        out.append(Decision("Booter", "Quirks > ProtectUefiServices", "True",
                            "Z390 / 11th-gen+ firmware relocates UEFI services at boot"))
    if z390 or (not amd and gen >= 11):
        out.append(Decision("Booter", "Quirks > DevirtualiseMmio", "True",
                            "Z390 / 11th-gen+ - free up MMIO regions the slide would trip on"))

    # --- Kernel quirks -------------------------------------------------
    out.append(Decision("Kernel", "Quirks > ProvideCurrentCpuInfo",
                        "True" if amd else "False",
                        "AMD chips don't expose topology macOS can read - inject it"
                        if amd else "Intel reports its own topology"))
    out.append(Decision("Kernel", "Quirks > AppleXcpmCfgLock",
                        "False" if amd else "True",
                        "no XCPM path on AMD" if amd else
                        "MSR 0xE2 is locked on most consumer boards - patch the write"))
    out.append(Decision("Kernel", "Emulate > DummyPowerManagement",
                        "True" if amd else "False",
                        "AMD has no AppleIntelCPUPowerManagement - stub it"
                        if amd else "Intel uses AppleXcpm / plugin-type"))
    out.append(Decision("Kernel", "Quirks > DisableIoMapper", "True",
                        "disable VT-d unless you've added a DMAR/-remap SSDT"))
    if amd:
        n = cpu.cores or 1
        out.append(Decision("Kernel", "Patch (AMD_Vanilla)",
                            f"spliced to {n} cores",
                            "AMD_Vanilla core-count patches rewritten for this CPU"))

    # --- DeviceProperties --------------------------------------------------
    ig = m.igpu
    if ig and ig.vendor is Vendor.INTEL and 6 <= gen <= 10:
        laptop, desktop, headless = _IG_PLATFORM[gen]
        drives_display = not (m.dgpu and m.dgpu.vendor is Vendor.AMD and not m.is_laptop)
        pid = laptop if m.is_laptop else (desktop if drives_display else headless)
        if m.is_laptop:
            why = f"Intel {gen}th-gen laptop iGPU framebuffer"
        elif drives_display:
            why = f"Intel {gen}th-gen desktop iGPU driving the display"
        else:
            why = f"Intel {gen}th-gen iGPU headless - an AMD dGPU drives the display"
        out.append(Decision("DeviceProperties",
                            "PciRoot(0x0)/Pci(0x2,0x0) > AAPL,ig-platform-id",
                            "0x" + pid, why))
        if not drives_display:
            out.append(Decision("DeviceProperties",
                                "PciRoot(0x0)/Pci(0x2,0x0) > framebuffer-unifiedmem",
                                "0x80000000", "headless iGPU still needs a memory stride"))
    out.append(Decision("DeviceProperties",
                        "PciRoot(0x0)/Pci(0x1f,0x3) > layout-id", "1",
                        "generic AppleALC layout - swap for your codec's tested layout-id"))

    # --- ACPI / SSDT -----------------------------------------------------
    for s in plan.ssdts:
        out.append(Decision("ACPI", s.name, "added", s.reason))
    for todo in plan.manual_acpi:
        out.append(Decision("ACPI", todo.split(" ")[0], "manual", todo))

    # --- Kexts --------------------------------------------------------
    baseline = {"Lilu", "VirtualSMC", "WhateverGreen", "AppleALC"}
    picked = {s.kext.name for s in plan.kexts}
    out.append(Decision("Kexts", "base set",
                        ", ".join(n for n in ("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC")
                                  if n in picked),
                        "patch engine, SMC emulation, GPU + audio - always loaded"))
    for s in plan.kexts:
        if s.kext.name in baseline:
            continue
        out.append(Decision("Kexts", s.kext.name, "load",
                            s.comment or "matched to detected hardware"))

    return out
