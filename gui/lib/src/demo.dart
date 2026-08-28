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
