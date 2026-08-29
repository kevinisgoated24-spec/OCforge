"""Assemble an OpenCore config.plist (as a dict, ready for ``plistlib.dump``).

``assemble(plan, smbios)`` returns a complete, ocvalidate-shaped config for
OpenCore 1.0.x. Kext ``ExecutablePath`` values are best-guesses here and get
corrected by :func:`ocforge.build.layout.fixup_kext_paths` once the bundles
are on disk.
"""

from __future__ import annotations

import plistlib
from typing import Any

from ocforge.build.plan import BuildPlan
from ocforge.build.smbios import SmbiosData
from ocforge.model import Vendor

# Intel iGPU framebuffer ids (AAPL,ig-platform-id), little-endian bytes.
_IG_PLATFORM = {
    # gen: (laptop, desktop-with-display, desktop-connectorless)
    6: ("00001619", "00001219", "03001219"),
    7: ("00001659", "00001259", "03001259"),
    8: ("0000C087", "07009B3E", "0300913E"),
    9: ("0000C087", "07009B3E", "0300913E"),
    10: ("0000528A", "07009B3E", "0300C89B"),
}


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


def _acpi(plan: BuildPlan, add: list[dict[str, Any]] | None = None,
         patch: list[dict[str, Any]] | None = None,
         delete: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if add is None:
        add = [
            {"Comment": s.name, "Enabled": True, "Path": f"{s.name}.aml"} for s in plan.ssdts
        ]
    return {
        "Add": add,
        "Delete": delete or [],
        "Patch": patch or [],
        "Quirks": {
            "FadtEnableReset": False,
            "NormalizeHeaders": False,
            "RebaseRegions": False,
            "ResetHwSig": False,
            "ResetLogoStatus": True,
            "SyncTableIds": False,
        },
    }


def _booter(plan: BuildPlan) -> dict[str, Any]:
    m = plan.machine
    modern_mmap = plan.is_amd or (m.cpu.vendor is Vendor.INTEL and m.cpu.intel_gen >= 8)
    board = m.firmware.board_name.lower()
    z390 = any(x in board for x in ("z390", "z490"))
    # Threadripper (TRX40/TRX50/WRX80/WRX90) needs DevirtualiseMmio per the AMD guide
    threadripper = plan.is_amd and (
        "threadripper" in (m.cpu.brand or "").lower()
        or any(x in board for x in ("trx40", "trx50", "wrx80", "wrx90"))
    )
    return {
        "MmioWhitelist": [],
        "Patch": [],
        "Quirks": {
            "AllowRelocationBlock": False,
            "AvoidRuntimeDefrag": True,
            "ClearTaskSwitchBit": False,
            "DevirtualiseMmio": z390 or threadripper or (not plan.is_amd and m.cpu.intel_gen >= 11),
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
            "ProtectUefiServices": z390 or m.cpu.intel_gen >= 11,
            "ProvideCustomSlide": True,
            "ProvideMaxSlide": 0,
            "RebuildAppleMemoryMap": modern_mmap,
            "ResizeAppleGpuBars": -1,
            "SetupVirtualMap": not (plan.is_amd or m.cpu.intel_gen >= 11 or z390),
            "SignalAppleOS": False,
            "SyncRuntimePermissions": modern_mmap,
        },
    }


# Coffee/Comet Lake desktop UHD 630 device-ids the Apple framebuffer matches
# directly. Anything else in the range gets faked to 0x3E9B.
_CFL_OK_IGPU = {"3e91", "3e92", "3e98", "3e9b", "9bc5", "9bc8"}


def _device_properties(plan: BuildPlan) -> dict[str, Any]:
    add: dict[str, dict[str, Any]] = {}
    m = plan.machine
    ig = m.igpu
    if ig and ig.vendor is Vendor.INTEL and 6 <= m.cpu.intel_gen <= 10:
        laptop, desktop, headless = _IG_PLATFORM[m.cpu.intel_gen]
        drives_display = not (m.dgpu and m.dgpu.vendor is Vendor.AMD and not m.is_laptop)
        pid = laptop if m.is_laptop else (desktop if drives_display else headless)
        props: dict[str, Any] = {"AAPL,ig-platform-id": _b(pid)}
        if not drives_display:
            props["framebuffer-unifiedmem"] = _b("00000080")
        elif not m.is_laptop:
            # desktop iGPU driving the display: WhateverGreen patching + a 19MB
            # stolen-mem floor, for boards with DVMT locked in firmware (most
            # OEM boxes). Dortania Coffee Lake -> DeviceProperties.
            props["framebuffer-patch-enable"] = _b("01000000")
            props["framebuffer-stolenmem"] = _b("00003001")
            dev = (ig.pci.device or "").lower()
            if 8 <= m.cpu.intel_gen and dev and dev not in _CFL_OK_IGPU:
                props["device-id"] = _b("9b3e0000")  # -> 0x3E9B (UHD 630 desktop)
        add["PciRoot(0x0)/Pci(0x2,0x0)"] = props
    # onboard audio: AppleALC layout-id 1 is the safest generic starting point
    add["PciRoot(0x0)/Pci(0x1f,0x3)"] = {"layout-id": _b("01000000")}
    return {"Add": add, "Delete": {}}


def _kernel(plan: BuildPlan, amd_patches: list[dict[str, Any]] | None) -> dict[str, Any]:
    adds = []
    for s in plan.kexts:
        entry = {
            "Arch": "x86_64",
            "BundlePath": s.kext.bundle_path().split("/")[-1],
            "Comment": s.comment or s.kext.name,
            "Enabled": True,
            # a plist-only kext has no binary; pointing ExecutablePath at a
            # missing file makes OpenCore skip the kext at boot.
            "ExecutablePath": "" if s.kext.codeless else f"Contents/MacOS/{s.kext.name}",
            "MaxKernel": f"{s.max_darwin}.99.99" if s.max_darwin else "",
            "MinKernel": f"{s.min_darwin}.0.0" if s.min_darwin else "",
            "PlistPath": "Contents/Info.plist",
        }
        adds.append(entry)

    quirks = {
        "AppleCpuPmCfgLock": False,
        "AppleXcpmCfgLock": True,
        "AppleXcpmExtraMsrs": False,
        "AppleXcpmForceBoost": False,
        "CustomPciSerialDevice": False,
        "CustomSMBIOSGuid": False,
        "DisableIoMapper": not plan.is_amd,   # AMD has no VT-d/DMAR — irrelevant there
        "DisableIoMapperMapping": False,
        "DisableLinkeditJettison": True,
        "DisableRtcChecksum": False,
        "ExtendBTFeatureFlags": False,
        "ExternalDiskIcons": False,
        "ForceAquantiaEthernet": False,
        "ForceSecureBootScheme": False,
        "IncreasePciBarSize": False,
        "LapicKernelPanic": False,
        "LegacyCommpage": False,
        "PanicNoKextDump": True,
        "PowerTimeoutKernelPanic": True,
        "ProvideCurrentCpuInfo": plan.is_amd,
        "SetApfsTrimTimeout": -1,
        "ThirdPartyDrives": False,
        "XhciPortLimit": False,
    }
    if plan.is_amd:
        quirks["AppleXcpmCfgLock"] = False

    spoof_data, spoof_mask = _cpu_spoof(plan.machine)
    emulate = {
        "Cpuid1Data": spoof_data,
        "Cpuid1Mask": spoof_mask,
        "DummyPowerManagement": plan.is_amd,
        "MaxKernel": "",
        "MinKernel": "",
    }

    return {
        "Add": adds,
        "Block": [],
        "Emulate": emulate,
        "Force": [],
        "Patch": amd_patches or [],
        "Quirks": quirks,
        "Scheme": {"CustomKernel": False, "FuzzyMatch": True, "KernelArch": "x86_64", "KernelCache": "Auto"},
    }


def _misc(plan: BuildPlan) -> dict[str, Any]:
    return {
        "BlessOverride": [],
        "Boot": {
            "ConsoleAttributes": 0,
            "HibernateMode": "None",
            "HibernateSkipsPicker": False,
            "HideAuxiliary": True,
            "InstanceIdentifier": "",
            "LauncherOption": "Disabled",
            "LauncherPath": "Default",
            "PickerAttributes": 17,
            "PickerAudioAssist": False,
            "PickerMode": "External",
            "PickerVariant": "Auto",
            "PollAppleHotKeys": True,
            "ShowPicker": True,
            "TakeoffDelay": 0,
            "Timeout": 8,
        },
        "Debug": {
            "AppleDebug": True,
            "ApplePanic": True,
            "DisableWatchDog": True,
            "DisplayDelay": 0,
            "DisplayLevel": 2147483650,
            "LogModules": "*",
            "SysReport": False,
            "Target": 67,
        },
        "Entries": [],
        "Security": {
            "AllowSetDefault": True,
            "ApECID": 0,
            "AuthRestart": False,
            "BlacklistAppleUpdate": True,
            "DmgLoading": "Signed",
            "EnablePassword": False,
            "ExposeSensitiveData": 6,
            "HaltLevel": 2147483648,
            "PasswordHash": b"",
            "PasswordSalt": b"",
            "ScanPolicy": 0,
            "SecureBootModel": "Disabled",
            "Vault": "Optional",
        },
        "Serial": {"Init": False, "Override": False},
        "Tools": [],
    }


_NV_BOOT = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
_NV_UI = "4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14"


def _nvram(plan: BuildPlan) -> dict[str, Any]:
    return {
        "Add": {
            _NV_UI: {
                "DefaultBackgroundColor": _b("00000000"),
            },
            _NV_BOOT: {
                "boot-args": " ".join(plan.boot_args),
                "csr-active-config": _b("00000000"),
                "prev-lang:kbd": b"en-US:0",
                "run-efi-updater": "No",
            },
        },
        "Delete": {
            _NV_UI: ["DefaultBackgroundColor"],
            _NV_BOOT: ["boot-args"],
        },
        "LegacyOverwrite": False,
        "LegacySchema": {},
        "WriteFlash": True,
    }


def _platform_info(sm: SmbiosData) -> dict[str, Any]:
    return {
        "Automatic": True,
        "CustomMemory": False,
        "Generic": {
            "AdviseFeatures": False,
            "MLB": sm.mlb,
            "MaxBIOSVersion": False,
            "ProcessorType": 0,
            "ROM": sm.rom,
            "SpoofVendor": True,
            "SystemMemoryStatus": "Auto",
            "SystemProductName": sm.model,
            "SystemSerialNumber": sm.serial,
            "SystemUUID": sm.uuid,
        },
        "UpdateDataHub": True,
        "UpdateNVRAM": True,
        "UpdateSMBIOS": True,
        "UpdateSMBIOSMode": "Create",
        "UseRawUuidEncoding": False,
    }


def _uefi(plan: BuildPlan) -> dict[str, Any]:
    return {
        "APFS": {
            "EnableJumpstart": True,
            "GlobalConnect": False,
            "HideVerbose": False,
            "JumpstartHotPlug": False,
            "MinDate": 0,
            "MinVersion": 0,
        },
        "AppleInput": {
            "AppleEvent": "Builtin",
            "CustomDelays": False,
            "GraphicsInputMirroring": True,
            "KeyInitialDelay": 0,
            "KeySubsequentDelay": 5,
            "PointerDwellClickTimeout": 0,
            "PointerDwellDoubleClickTimeout": 0,
            "PointerDwellRadius": 0,
            "PointerPollMax": 0,
            "PointerPollMin": 0,
            "PointerPollMask": -1,
            "PointerSpeedDiv": 1,
            "PointerSpeedMul": 1,
        },
        "Audio": {
            "AudioCodec": 0,
            "AudioDevice": "",
            "AudioOutMask": 1,
            "AudioSupport": False,
            "DisconnectHda": False,
            "MaximumGain": -15,
            "MinimumAssistGain": -30,
            "MinimumAudibleGain": -55,
            "PlayChime": "Auto",
            "ResetTrafficClass": False,
            "SetupDelay": 0,
        },
        "ConnectDrivers": True,
        "Drivers": [
            {"Arguments": "", "Comment": "", "Enabled": True, "LoadEarly": False, "Path": "OpenRuntime.efi"},
            {"Arguments": "", "Comment": "", "Enabled": True, "LoadEarly": False, "Path": "HfsPlus.efi"},
            {"Arguments": "", "Comment": "", "Enabled": True, "LoadEarly": False, "Path": "ResetNvramEntry.efi"},
        ],
        "Input": {
            "KeyFiltering": False,
            "KeyForgetThreshold": 5,
            "KeySupport": True,
            "KeySupportMode": "Auto",
            "KeySwap": False,
            "PointerSupport": False,
            "PointerSupportMode": "ASUS",
            "TimerResolution": 50000,
        },
        "Output": {
            "ClearScreenOnModeSwitch": False,
            "ConsoleFont": "",
            "ConsoleMode": "",
            "DirectGopRendering": False,
            "ForceResolution": False,
            "GopBurstMode": False,
            "GopPassThrough": "Disabled",
            "IgnoreTextInGraphics": False,
            "InitialMode": "Auto",
            "ProvideConsoleGop": True,
            "ReconnectGraphicsOnConnect": False,
            "ReconnectOnResChange": False,
            "ReplaceTabWithSpace": False,
            "Resolution": "Max",
            "SanitiseClearScreen": False,
            "TextRenderer": "BuiltinGraphics",
            "UIScale": 0,
            "UgaPassThrough": False,
        },
        "ProtocolOverrides": {
            "AppleAudio": False,
            "AppleBootPolicy": False,
            "AppleDebugLog": False,
            "AppleEg2Info": False,
            "AppleFramebufferInfo": False,
            "AppleImageConversion": False,
            "AppleImg4Verification": False,
            "AppleKeyMap": False,
            "AppleRtcRam": False,
            "AppleSecureBoot": False,
            "AppleSmcIo": False,
            "AppleUserInterfaceTheme": False,
            "DataHub": False,
            "DeviceProperties": False,
            "FirmwareVolume": False,
            "HashServices": False,
            "OSInfo": False,
            "PciIo": False,
            "UnicodeCollation": False,
        },
        "Quirks": {
            "ActivateHpetSupport": False,
            "DisableSecurityPolicy": False,
            "EnableVectorAcceleration": True,
            "EnableVmx": False,
            "ExitBootServicesDelay": 0,
            "ForceOcWriteFlash": False,
            "ForgeUefiSupport": False,
            "IgnoreInvalidFlexRatio": False,
            "ReleaseUsbOwnership": True,
            "ReloadOptionRoms": False,
            "RequestBootVarRouting": True,
            "ResizeGpuBars": -1,
            "ResizeUsePciRbIo": False,
            "ShimRetainProtocol": False,
            "TscSyncTimeout": 0,
            "UnblockFsConnect": False,
        },
        "ReservedMemory": [],
        "Unload": [],
    }


def assemble(plan: BuildPlan, sm: SmbiosData, *,
             amd_patches: list[dict[str, Any]] | None = None,
             acpi_add: list[dict[str, Any]] | None = None,
             acpi_patch: list[dict[str, Any]] | None = None,
             acpi_delete: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "ACPI": _acpi(plan, acpi_add, acpi_patch, acpi_delete),
        "Booter": _booter(plan),
        "DeviceProperties": _device_properties(plan),
        "Kernel": _kernel(plan, amd_patches),
        "Misc": _misc(plan),
        "NVRAM": _nvram(plan),
        "PlatformInfo": _platform_info(sm),
        "UEFI": _uefi(plan),
    }


def dump(config: dict[str, Any]) -> bytes:
    return plistlib.dumps(config, fmt=plistlib.FMT_XML, sort_keys=False)
