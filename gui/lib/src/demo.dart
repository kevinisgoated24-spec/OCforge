/// Canned data so the packaged .exe is fully explorable without the Python
/// CLI installed. Shape matches `ocforge.spec.to_json`.
const String demoSpecJson = '''
{
  "chassis": "desktop",
  "cpu": {
    "brand": "AMD Ryzen 5 5600X",
    "vendor": "amd",
    "family": "Zen 3",
    "intel_gen": 0,
    "cores": 6,
    "threads": 12,
    "flags": ["sse4_2", "avx2"]
  },
  "igpu": null,
  "dgpu": {
    "name": "Radeon RX 6800",
    "vendor": "amd",
    "pci": {"vendor": "1002", "device": "73bf", "sub": ""},
    "discrete": true
  },
  "net": [
    {"name": "RTL8125 2.5GbE", "vendor": "realtek",
     "pci": {"vendor": "10ec", "device": "8125", "sub": ""}, "wireless": false}
  ],
  "storage": {"has_nvme": true, "nvme_pci": null},
  "inputs": {"has_touchpad": false, "touchpad_bus": ""},
  "firmware": {"board_vendor": "ASUS", "board_name": "TUF GAMING B550-PLUS", "bios_vendor": "AMI"}
}
''';

const String demoPlanText = '''
target    macOS Sequoia (15)  darwin 24
smbios    MacPro7,1
boot-args -v debug=0x100 keepsyms=1 -no_compat_check npci=0x2000 agdpmod=pikera -lilubetaall

kexts (15)
  Lilu
  VirtualSMC
  WhateverGreen
  AppleALC
  RealtekRTL8125  [.. ]  - 2.5GbE
  SMCAMDProcessor  - AMD power/temp
  AMDRyzenCPUPowerManagement
  ForgedInvariant  - TSC sync for Ryzen
  ... and 7 more

SSDTs (1)
  SSDT-EC-USBX  - fake EC + USB power properties (USBX)

manual ACPI (needs the target's DSDT)
  ! SSDT-GPIO only if this were an I2C-HID trackpad laptop

warnings
  ! AMD build: kernel patches are spliced from AMD_Vanilla; verify the core count
''';

const String demoExplainJson = '''
[
  {
    "section": "macOS",
    "setting": "target",
    "value": "Tahoe 26 (darwin 25)",
    "reason": "newest release this hardware runs cleanly",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/"
  },
  {
    "section": "SMBIOS",
    "setting": "PlatformInfo > Generic > SystemProductName",
    "value": "MacPro7,1",
    "reason": "AMD desktop with an AMD dGPU - MacPro7,1 expects discrete AMD graphics, no iGPU",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "boot-args",
    "setting": "-v",
    "value": "on",
    "reason": "verbose boot - shows the log instead of the Apple logo; drop it once stable",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "boot-args",
    "setting": "debug=0x100",
    "value": "on",
    "reason": "don't reboot on a kernel panic - keep the panic screen up to read it",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "boot-args",
    "setting": "keepsyms=1",
    "value": "on",
    "reason": "print symbol names in panic backtraces",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "boot-args",
    "setting": "-no_compat_check",
    "value": "on",
    "reason": "MacPro7,1 isn't the Mac this hardware matches - skip the model/OS compatibility gate",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "boot-args",
    "setting": "npci=0x2000",
    "value": "on",
    "reason": "skip PCI enumeration past the config stage - avoids early hangs on AMD",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "boot-args",
    "setting": "agdpmod=pikera",
    "value": "on",
    "reason": "patch the board-id check that black-screens Navi (RX 5000+) GPUs",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "boot-args",
    "setting": "-lilubetaall",
    "value": "on",
    "reason": "macOS is newer than Lilu's whitelist - let Lilu + plugins run anyway",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "Booter",
    "setting": "Quirks > RebuildAppleMemoryMap",
    "value": "True",
    "reason": "AMD firmware hands over a clean memory map",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "Booter",
    "setting": "Quirks > EnableWriteUnprotector",
    "value": "False",
    "reason": "not needed with a modern memory map - safer left off",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "Booter",
    "setting": "Quirks > SyncRuntimePermissions",
    "value": "True",
    "reason": "realign runtime page permissions after the rebuild",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "Booter",
    "setting": "Quirks > SetupVirtualMap",
    "value": "False",
    "reason": "AMD / Z390 / 11th-gen+ firmware maps runtime services correctly",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "Kernel",
    "setting": "Quirks > ProvideCurrentCpuInfo",
    "value": "True",
    "reason": "AMD chips don't expose topology macOS can read - inject it",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "Kernel",
    "setting": "Quirks > AppleXcpmCfgLock",
    "value": "False",
    "reason": "no XCPM path on AMD",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "Kernel",
    "setting": "Emulate > DummyPowerManagement",
    "value": "True",
    "reason": "AMD has no AppleIntelCPUPowerManagement - stub it",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "Kernel",
    "setting": "Quirks > DisableIoMapper",
    "value": "True",
    "reason": "disable VT-d unless you've added a DMAR/-remap SSDT",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "Kernel",
    "setting": "Patch (AMD_Vanilla)",
    "value": "spliced to 6 cores",
    "reason": "AMD_Vanilla core-count patches rewritten for this CPU - see the AMD_Vanilla section below",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "DeviceProperties",
    "setting": "PciRoot(0x0)/Pci(0x1f,0x3) > layout-id",
    "value": "1",
    "reason": "generic AppleALC layout - swap for your codec's tested layout-id",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/AMD/"
  },
  {
    "section": "ACPI",
    "setting": "SSDT-EC-USBX",
    "value": "added",
    "reason": "fake EC + USB power properties (USBX)",
    "doc": "https://dortania.github.io/Getting-Started-With-ACPI/"
  },
  {
    "section": "Kexts",
    "setting": "base set",
    "value": "Lilu, VirtualSMC, WhateverGreen, AppleALC",
    "reason": "patch engine, SMC emulation, GPU + audio - always loaded",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/"
  },
  {
    "section": "Kexts",
    "setting": "SMCProcessor",
    "value": "load",
    "reason": "matched to detected hardware",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/"
  },
  {
    "section": "Kexts",
    "setting": "SMCSuperIO",
    "value": "load",
    "reason": "matched to detected hardware",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/"
  },
  {
    "section": "Kexts",
    "setting": "RestrictEvents",
    "value": "load",
    "reason": "matched to detected hardware",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/"
  },
  {
    "section": "Kexts",
    "setting": "NVMeFix",
    "value": "load",
    "reason": "matched to detected hardware",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/"
  },
  {
    "section": "Kexts",
    "setting": "FeatureUnlock",
    "value": "load",
    "reason": "matched to detected hardware",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/"
  },
  {
    "section": "Kexts",
    "setting": "CryptexFixup",
    "value": "load",
    "reason": "Metal cryptex on AMD / pre-AVX2",
    "doc": "https://dortania.github.io/OpenCore-Install-Guide/"
  },
  {
    "section": "AMD_Vanilla",
    "setting": "patch set (live)",
    "value": "25 patches from AMD_Vanilla master",
    "reason": "the community kernel patch set - macOS will not boot on Ryzen/Threadripper without it; ocforge fetches it fresh at build time",
    "doc": "https://github.com/AMD-OSX/AMD_Vanilla"
  },
  {
    "section": "AMD_Vanilla",
    "setting": "algrey | Force cpuid_cores_per_package to constant (user-specified) | 10.13-10.14",
    "value": "darwin 17..18.99.99",
    "reason": "CPU topology patch - Replace byte 1 set to 6 (your physical core count)",
    "doc": "https://github.com/AMD-OSX/AMD_Vanilla"
  },
  {
    "section": "AMD_Vanilla",
    "setting": "algrey | Force cpuid_cores_per_package to constant (user-specified) | 10.15-11.0",
    "value": "darwin 19..20.99.99",
    "reason": "CPU topology patch - Replace byte 1 set to 6 (your physical core count)",
    "doc": "https://github.com/AMD-OSX/AMD_Vanilla"
  },
  {
    "section": "AMD_Vanilla",
    "setting": "algrey | Force cpuid_cores_per_package to constant (user-specified) | 12.0-13.2",
    "value": "darwin 21..22.3.99",
    "reason": "CPU topology patch - Replace byte 1 set to 6 (your physical core count)",
    "doc": "https://github.com/AMD-OSX/AMD_Vanilla"
  },
  {
    "section": "AMD_Vanilla",
    "setting": "algrey | Force cpuid_cores_per_package to constant (user-specified) | 13.3+",
    "value": "darwin 22.4.0..25.99.99",
    "reason": "CPU topology patch - Replace byte 1 set to 6 (your physical core count)",
    "doc": "https://github.com/AMD-OSX/AMD_Vanilla"
  },
  {
    "section": "AMD_Vanilla",
    "setting": "algrey | _commpage_populate | Remove rdmsr | 10.13+",
    "value": "darwin 17..25.99.99",
    "reason": "AMD kernel patch",
    "doc": "https://github.com/AMD-OSX/AMD_Vanilla"
  },
  {
    "section": "AMD_Vanilla",
    "setting": "algrey | _cpuid_set_cache_info | Set CPUID proper instead of 4 | 10.13+",
    "value": "darwin 17..25.99.99",
    "reason": "AMD kernel patch",
    "doc": "https://github.com/AMD-OSX/AMD_Vanilla"
  },
  {
    "section": "AMD_Vanilla",
    "setting": "algrey | _cpuid_set_generic_info | Remove wrmsr(0x8B) | 10.13+",
    "value": "darwin 17..25.99.99",
    "reason": "AMD kernel patch",
    "doc": "https://github.com/AMD-OSX/AMD_Vanilla"
  }
]
''';

const String demoConfigJson = '''
{
  "ACPI": {
    "Add": [
      {
        "Comment": "SSDT-EC-USBX",
        "Enabled": true,
        "Path": "SSDT-EC-USBX.aml"
      },
      {
        "Comment": "SSDT-PLUG",
        "Enabled": true,
        "Path": "SSDT-PLUG.aml"
      }
    ],
    "Quirks": {
      "FadtEnableReset": false,
      "NormalizeHeaders": false,
      "RebaseRegions": false,
      "ResetHwSig": false,
      "ResetLogoStatus": true,
      "SyncTableIds": false
    }
  },
  "Booter": {
    "Quirks": {
      "AllowRelocationBlock": false,
      "AvoidRuntimeDefrag": true,
      "ClearTaskSwitchBit": false,
      "DevirtualiseMmio": false,
      "DisableSingleUser": false,
      "DisableVariableWrite": false
    }
  },
  "Kernel": {
    "Quirks": {
      "AppleXcpmCfgLock": true,
      "DisableIoMapper": true,
      "PanicNoKextDump": true
    },
    "Emulate": {
      "Cpuid1Data": {
        "__data__": ""
      },
      "Cpuid1Mask": {
        "__data__": ""
      },
      "DummyPowerManagement": false,
      "MaxKernel": "",
      "MinKernel": ""
    }
  },
  "NVRAM": {
    "Add": {
      "7C436110-AB2A-4BBB-A880-FE41995C9F82": {
        "boot-args": "-v debug=0x100 keepsyms=1 igfxonln=1 -lilubetaall",
        "csr-active-config": {
          "__data__": "00000000"
        },
        "prev-lang:kbd": {
          "__data__": "656e2d55533a30"
        },
        "run-efi-updater": "No"
      }
    }
  },
  "PlatformInfo": {
    "Generic": {
      "SystemProductName": "MacBookPro16,1",
      "SystemSerialNumber": "C02Y20U8MD6N",
      "MLB": "C02901404GUN9PRAD",
      "ROM": {
        "__data__": "8863dfac69ba"
      },
      "SystemUUID": "392EAAA9-26A0-4D8B-BD6C-51281C89D9F2"
    }
  },
  "UEFI": {
    "Quirks": {
      "ActivateHpetSupport": false,
      "DisableSecurityPolicy": false,
      "EnableVectorAcceleration": true,
      "EnableVmx": false,
      "ExitBootServicesDelay": 0
    }
  }
}
''';

const List<String> demoValidateOutput = <String>[
  'NOTE: This version of ocvalidate is only compatible with OpenCore 1.0.x.',
  '',
  'Completed validating config.plist in 1 ms. No issues found.',
];

const List<String> demoBuildLog = <String>[
  'fetching OpenCore 1.0.7 ...',
  'fetching OcBinaryData ...',
  'scaffolding EFI/ ...',
  'fetching 15 kexts ...',
  '  Lilu 1.7.1  ok',
  '  VirtualSMC 1.3.7  ok',
  '  WhateverGreen 1.7.0  ok',
  '  AppleALC 1.9.5  ok',
  '  SMCAMDProcessor 0.7.0  ok',
  'splicing AMD_Vanilla kernel patches (12 threads) ...',
  'generating SMBIOS (macserial) ...',
  '  SystemProductName  MacPro7,1',
  '  board-id           Mac-27AD2F918AE68F61',
  'assembling config.plist ...',
  'wrote EFI/OC/config.plist',
  '',
  'run ocvalidate against the config before booting.',
  '',
  'done — EFI folder ready.',
];
