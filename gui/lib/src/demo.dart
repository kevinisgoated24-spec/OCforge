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
  {"section":"macOS","setting":"target","value":"Tahoe 26 (darwin 25)",
   "reason":"newest release this hardware runs cleanly"},
  {"section":"SMBIOS","setting":"PlatformInfo > Generic > SystemProductName","value":"MacPro7,1",
   "reason":"AMD desktop with an AMD dGPU - MacPro7,1 expects discrete AMD graphics, no iGPU"},
  {"section":"boot-args","setting":"-v","value":"on",
   "reason":"verbose boot - shows the log instead of the Apple logo; drop it once stable"},
  {"section":"boot-args","setting":"debug=0x100","value":"on",
   "reason":"don't reboot on a kernel panic - keep the panic screen up to read it"},
  {"section":"boot-args","setting":"keepsyms=1","value":"on",
   "reason":"print symbol names in panic backtraces"},
  {"section":"boot-args","setting":"-no_compat_check","value":"on",
   "reason":"MacPro7,1 isn't the Mac this hardware matches - skip the model/OS compatibility gate"},
  {"section":"boot-args","setting":"npci=0x2000","value":"on",
   "reason":"skip PCI enumeration past the config stage - avoids early hangs on AMD"},
  {"section":"boot-args","setting":"agdpmod=pikera","value":"on",
   "reason":"patch the board-id check that black-screens Navi (RX 5000+) GPUs"},
  {"section":"boot-args","setting":"-lilubetaall","value":"on",
   "reason":"macOS is newer than Lilu's whitelist - let Lilu + plugins run anyway"},
  {"section":"Booter","setting":"Quirks > RebuildAppleMemoryMap","value":"True",
   "reason":"AMD firmware hands over a clean memory map"},
  {"section":"Booter","setting":"Quirks > EnableWriteUnprotector","value":"False",
   "reason":"not needed with a modern memory map - safer left off"},
  {"section":"Booter","setting":"Quirks > SyncRuntimePermissions","value":"True",
   "reason":"realign runtime page permissions after the rebuild"},
  {"section":"Booter","setting":"Quirks > SetupVirtualMap","value":"False",
   "reason":"AMD / Z390 / 11th-gen+ firmware maps runtime services correctly"},
  {"section":"Kernel","setting":"Quirks > ProvideCurrentCpuInfo","value":"True",
   "reason":"AMD chips don't expose topology macOS can read - inject it"},
  {"section":"Kernel","setting":"Quirks > AppleXcpmCfgLock","value":"False",
   "reason":"no XCPM path on AMD"},
  {"section":"Kernel","setting":"Emulate > DummyPowerManagement","value":"True",
   "reason":"AMD has no AppleIntelCPUPowerManagement - stub it"},
  {"section":"Kernel","setting":"Quirks > DisableIoMapper","value":"True",
   "reason":"disable VT-d unless you've added a DMAR/-remap SSDT"},
  {"section":"Kernel","setting":"Patch (AMD_Vanilla)","value":"spliced to 6 cores",
   "reason":"AMD_Vanilla core-count patches rewritten for this CPU"},
  {"section":"DeviceProperties","setting":"PciRoot(0x0)/Pci(0x1f,0x3) > layout-id","value":"1",
   "reason":"generic AppleALC layout - swap for your codec's tested layout-id"},
  {"section":"ACPI","setting":"SSDT-EC-USBX","value":"added",
   "reason":"fake EC + USB power properties (USBX)"},
  {"section":"Kexts","setting":"base set","value":"Lilu, VirtualSMC, WhateverGreen, AppleALC",
   "reason":"patch engine, SMC emulation, GPU + audio - always loaded"},
  {"section":"Kexts","setting":"AMDRyzenCPUPowerManagement","value":"load",
   "reason":"matched to detected hardware"},
  {"section":"Kexts","setting":"SMCAMDProcessor","value":"load",
   "reason":"matched to detected hardware"},
  {"section":"Kexts","setting":"ForgedInvariant","value":"load","reason":"TSC sync for AMD"},
  {"section":"Kexts","setting":"LucyRTL8125Ethernet","value":"load","reason":"2.5GbE Realtek NIC"},
  {"section":"Kexts","setting":"USBToolBox","value":"load",
   "reason":"USB mapping (map ports after first boot)"}
]
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
