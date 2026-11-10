"""Assemble an OpenCore config.plist (as a dict, ready for ``plistlib.dump``).

``assemble(plan, smbios)`` returns a complete, ocvalidate-shaped config for
OpenCore 1.0.x. Key ``ExecutablePath`` values are best-guesses here and get
corrected by :func:`ocforge.build.layout.fixup_kext_paths` once the bundles
are on disk.
"""

from __future__ import annotations

import plistlib
from typing import Any

from ocforge.build.plan import BuildPlan
from ocforge.build.smbios import SmbiosData
from ocforge.model import Vendor
from ocforge.probe.base import is_legacy_amd

# Intel iGPU framebuffer ids (AAPL,ig-platform-id), little-endian bytes.
_IG_PLATFORM = {
    # gen: (laptop, desktop-with-display, desktop-connectorless)
    3: ("03006601", "0A006601", "07006201"),  # Ivy Bridge
    4: ("0500260A", "0300220D", "04001204"),  # Haswell
    5: ("06002616", "07002216", None),         # Broadwell
    6: ("00001619", "00001219", "01001219"),  # Skylake
    7: ("00001B59", "00001259", "03001259"),  # Kaby Lake
    8: ("00009B3E", "07009B3E", "0300913E"),  # Coffee Lake / Whiskey Lake
    9: ("00009B3E", "07009B3E", "0300913E"),  # Coffee Lake Refresh
    # Comet Lake uses 0x9B3E for laptops; Ice Lake is set separately below.
    10: ("00009B3E", "00009B3E", "0300C89B"),
}

# Ice Lake is also "10th gen" in Intel's marketing but different silicon
# entirely -- laptop-only, its own platform-id, no desktop counterpart.
_ICE_LAKE_LAPTOP_PLATFORM_ID = "0000528A"

# Haswell/Broadwell/Skylake desktops also want framebuffer-fbmem alongside
# -patch-enable/-stolenmem; Kaby Lake and newer dropped the need for it.
_NEEDS_FBMEM = {4, 5, 6}


def _b(hex_le: str) -> bytes:
    return bytes.fromhex(hex_le)


# Pentium/Celeron aren't in macOS's CPUID whitelist for XCPM / X86PlatformPlugin
# and panic ("Thread 0 crashed") once SSDT-PLUG is present. Spoof CPUID to the
# i3 of the same generation via Emulate. Values are the target i3's CPUID EAX
# (little-endian), padded to 16 bytes; the mask covers only those 4 bytes.
_I3_CPUID_EAX = {
    6:  "e3060500",   # i3-6100  (Skylake,     0x000506E3)
    7:  "e9060900",   # i3-7100  (Kaby Lake,   0x000906E9)
    8:  "ea060900",   # i3-8100  (Coffee Lake, 0x000906EA)
    9:  "ec060900",   # i3-9100  (CFL Refresh, 0x000906EC)
    10: "55060a00",   # i3-10100 (Comet Lake,  0x000A0655)
}


def is_pentium_or_celeron(m) -> bool:
    """Pentium/Celeron by brand string, or — when the brand didn't parse — a
    2-core Coffee/Comet Lake desktop (every 8th-gen+ i3 has 4 cores)."""
    brand = (m.cpu.brand or "").lower()
    if "pentium" in brand or "celeron" in brand:
        return True
    return bool(
        m.cpu.vendor is Vendor.INTEL
        and not m.is_laptop
        and 8 <= m.cpu.intel_gen <= 10
        and 0 < m.cpu.cores <= 2
    )


def _cpu_spoof(m) -> tuple[bytes, bytes]:
    """Cpuid1Data / Cpuid1Mask for a Pentium/Celeron, else empty bytes."""
    if not is_pentium_or_celeron(m):
        return b"", b""
    eax = _I3_CPUID_EAX.get(m.cpu.intel_gen)
    if eax is None:
        return b"", b""
    return bytes.fromhex(eax) + b"\x00" * 12, bytes.fromhex("ffffffff") + b"\x00" * 12


# Sandy/Ivy Bridge: Apple's XCPM doesn't support these well and can panic on
# AppleIntelCPUPowerManagement; drop the firmware's own PM tables the same
# way Dortania's Sandy/Ivy Bridge guides do (ACPI -> Delete). This is only
# half the guide's fix -- the other half, SSDT-PM, needs Pike's separate
# ssdtPRGen.sh and isn't automated here; see catalog.acpi.needs_generation.
_PRE_HASWELL_ACPI_DELETE = [
    {"All": True, "Comment": "Delete CpuPm", "Enabled": True,
     "OemTableId": bytes.fromhex("437075506d000000"), "TableLength": 0,
     "TableSignature": bytes.fromhex("53534454")},
    {"All": True, "Comment": "Delete Cpu0Ist", "Enabled": True,
     "OemTableId": bytes.fromhex("4370753049737400"), "TableLength": 0,
     "TableSignature": bytes.fromhex("53534454")},
]


def _apply_quirk_overrides(quirks: dict[str, Any], overrides: dict[str, bool],
                           applied: set[str], wrong_type: set[str]) -> None:
    """Applies whichever ``overrides`` this particular quirks dict recognizes,
    recording each one in ``applied`` so ``assemble()`` can tell a real quirk
    name from a typo once all four sections have had a turn. A name that
    exists but isn't a boolean toggle (a few Quirks entries are numeric, e.g.
    Booter's ProvideMaxSlide) is recorded in ``wrong_type`` instead of being
    silently coerced."""
    for name, value in overrides.items():
        if name not in quirks:
            continue
        if not isinstance(quirks[name], bool):
            wrong_type.add(name)
            continue
        quirks[name] = value
        applied.add(name)


def _acpi(plan: BuildPlan, add: list[dict[str, Any]] | None = None,
          patch: list[dict[str, Any]] | None = None,
          delete: list[dict[str, Any]] | None = None, *,
          quirk_overrides: dict[str, bool], applied: set[str],
          wrong_type: set[str]) -> dict[str, Any]:
    if add is None:
        add = [
            {"Comment": s.name, "Enabled": True, "Path": f"{s.name}.aml"}
            for s in plan.ssdts
        ]
    delete = list(delete or [])
    m = plan.machine
    if m.cpu.vendor is Vendor.INTEL and 0 < m.cpu.intel_gen < 4:
        delete += _PRE_HASWELL_ACPI_DELETE
    quirks = {
        "FadtEnableReset": False,
        "NormalizeHeaders": False,
        "RebaseRegions": False,
        "ResetHwSig": False,
        "ResetLogoStatus": True,
        "SyncTableIds": False,
    }
    _apply_quirk_overrides(quirks, quirk_overrides, applied, wrong_type)
    return {"Add": add, "Delete": delete, "Patch": patch or [], "Quirks": quirks}


def _boot(plan: BuildPlan, *, legacy_mmap: bool = False,
          quirk_overrides: dict[str, bool], applied: set[str],
          wrong_type: set[str]) -> dict[str, Any]:
    m = plan.machine
    gen = m.cpu.intel_gen
    intel = m.cpu.vendor is Vendor.INTEL
    legacy_amd = is_legacy_amd(m)
    board = m.firmware.board_name.lower()
    z390 = any(x in board for x in ("z390", "z490"))
    threadripper = plan.is_amd and (
        "threadripper" in (m.cpu.brand or "").lower()
        or any(x in board for x in ("trx40", "trx50", "wrx80", "wrx90"))
    )
    newer_amd_board = plan.is_amd and any(x in board for x in ("x570", "b550", "a520", "trx40"))
    modern_mmap = not legacy_mmap and (
        (plan.is_amd and not legacy_amd) or (intel and gen >= 8)
    )
    quirks = {
        "AllowRelocationBlock": False,
        "AvoidRuntimeDefrag": True,
        "ClearTaskSwitchBit": False,
        "DevirtualiseMmio": z390 or threadripper or (intel and not m.is_laptop and gen >= 8),
        "DisableSingleUser": False,
        "DisableVariableWrite": False,
        "DiscardHibernateMap": False,
        "EnableSafeModeSlide": True,
        "EnableWriteUnprotector": not modern_mmap,
        "FixupAppleEfiImages": True,
        "ForceBooterSignature": False,
        "ForceExitBootServices": False,
        "ProtectMemoryRegions": False,
        "ProtectSecureBoot": False,
        "ProtectUefiServices": z390 or gen >= 11,
        "ProvideCustomSlide": True,
        "ProvideMaxSlide": 0,
        "RebuildAppleMemoryMap": modern_mmap,
        "ResizeAppleGpuBars": -1,
        "SetupVirtualMap": not (newer_amd_board or gen >= 11 or z390),
        "SignalAppleOS": False,
        "SyncRuntimePermissions": modern_mmap,
    }
    _apply_quirk_overrides(quirks, quirk_overrides, applied, wrong_type)
    return {"MmioWhitelist": [], "Patch": [], "Quirks": quirks}


# Coffee/Comet Lake desktop UHD 630 device-ids the Apple framebuffer matches
# directly. Anything else in the range gets faked to 0x3E9B.
_CFL_OK_IGPU = {"3e91", "3e92", "3e98", "3e9b", "9bc5", "9bc8"}


def _device_properties(plan: BuildPlan) -> dict[str, Any]:
    add: dict[str, dict[str, Any]] = {}
    m = plan.machine
    ig = m.igpu
    gen = m.cpu.intel_gen
    is_ice_lake = gen == 10 and m.cpu.family == "Ice Lake"
    if ig and ig.vendor is Vendor.INTEL and gen in _IG_PLATFORM:
        laptop, desktop, headless = _IG_PLATFORM[gen]
        if is_ice_lake and m.is_laptop:
            laptop = _ICE_LAKE_LAPTOP_PLATFORM_ID
        drives_display = not (m.dgpu and m.dgpu.vendor is Vendor.AMD and not m.is_laptop)
        pid = laptop if m.is_laptop else (desktop if drives_display else headless)
        if pid is not None:
            props: dict[str, Any] = {"AAPL,ig-platform-id": _b(pid)}
            if not drives_display:
                props["framebuffer-unifiedmem"] = _b("00000080")
            else:
                if not m.is_laptop:
                    props["framebuffer-patch-enable"] = _b("01000000")
                    props["framebuffer-stolenmem"] = _b("00003001")
                    if gen in _NEEDS_FBMEM:
                        props["framebuffer-fbmem"] = _b("00009000")
                dev = (ig.pci.device or "").lower()
                if 8 <= gen and not is_ice_lake and dev and dev not in _CFL_OK_IGPU:
                    props["device-id"] = _b("9b3e0000")
            add["PciRoot(0x0)/Pci(0x2,0x0)"] = props
    add["PciRoot(0x0)/Pci(0x1f,0x3)"] = {"layout-id": _b("01000000")}

    for path, props in plan.spoof_devices.items():
        entry = add.setdefault(path, {})
        for key, value in props.items():
            entry[key] = _b(f"{value & 0xff:02x}{(value >> 8) & 0xff:02x}0000")

    return {"Add": add, "Delete": {}}


# The rest of the original file (kernel, misc, NVRAM, platform-info, UEFI,
# and assemble) is intentionally retained unchanged.
