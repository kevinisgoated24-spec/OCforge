### Other commands

| command | what it does |
|---|---|
| `ocforge explain --spec my-pc.json` | every `config.plist` decision with a Dortania link (`--json`, `--offline`) |
| `ocforge bios --spec my-pc.json` | BIOS/UEFI settings to change for this box |
| `ocforge validate --efi ./EFI` | run OpenCore's `ocvalidate` on the config |
| `ocforge plist show ./EFI/OC/config.plist` | `config.plist` → JSON |
| `ocforge plist save ./EFI/OC/config.plist < edited.json` | write edited JSON back |
| `ocforge build --spec my-pc.json --out ./EFI --dsdt ./my-pc-acpi` | compile SSDTs from the target's own ACPI |
| `ocforge build --out ./EFI --dump-dsdt` | dump this host's ACPI tables (Linux, Windows) |
| `ocforge report --spec my-pc.json` | file a bug with version + hardware pre-filled |
| `ocforge offline-installer --spec my-pc.json --out ./offline` | stage a [corpnewt/UnPlugged](https://github.com/corpnewt/UnPlugged) offline installer |
| `ocforge build --spec my-pc.json --out ./EFI --exclude-kext USBToolBox` | drop a kext ocforge would normally include (repeatable) |
| `ocforge build --spec my-pc.json --out ./EFI --include-kext VoodooPS2Controller` | force in a kext ocforge wouldn't normally pick (repeatable) |
| `ocforge build --spec my-pc.json --out ./EFI --exclude-ssdt SSDT-PLUG` | drop an SSDT ocforge would normally include (repeatable) |
| `ocforge build --spec my-pc.json --out ./EFI --smbios iMac19,1` | use this SMBIOS model instead of ocforge's own pick |
| `ocforge build --spec my-pc.json --out ./EFI --quirk DevirtualiseMmio=false` | override one Quirks on/off toggle (repeatable) |
| `ocforge build --spec my-pc.json --out ./EFI --spoof-device "PciRoot(0x0)/Pci(0x3,0x0)=1002:73AF"` | present a different PCI device to macOS (repeatable) |
| `ocforge logcheck --log opencore-2026-01-01-120000.txt` | scan a boot log / panic report for known trouble signatures |

Without `--dsdt` / `--dump-dsdt` the SSDTs come from Dortania's precompiled
hotpatch set, following the [prebuilt-SSDT matrix](https://dortania.github.io/Getting-Started-With-ACPI/ssdt-methods/ssdt-prebuilt.html)
row for your CPU family and chassis: `SSDT-EC` vs `SSDT-EC-USBX` by generation,
`SSDT-PLUG` (Haswell–Comet Lake), `SSDT-AWAC`/`SSDT-PMC` (Coffee Lake+ / true
300-series), `SSDT-PNLF` + `SSDT-XOSI` (Intel laptops, with the `_OSI→XOSI`
rename), `SSDT-IMEI` (Sandy+7-series / Ivy+6-series), `SSDT-RHUB` (Asus
400-series / Ice Lake laptops), `SSDT-CPUR` (AMD B550/A520/AM5), and
`SSDT-UNC` / `SSDT-RTC0-RANGE-HEDT` for X79/X99/X299 HEDT. With them, ocforge
fetches [SSDTTime](https://github.com/corpnewt/SSDTTime), runs the
non-interactive ops your machine needs (FakeEC, USBX, PluginType, PMC, RTCAWAC,
PNLF), and fills the rest (XOSI/IMEI/CPUR/…) from the prebuilt set. `--dump-dsdt`
reads `/sys/firmware/acpi/tables` on Linux (usually no root); on Windows it
fetches the [ACPICA project](https://github.com/open-acpica/acpica)'s
`acpidump.exe` and dumps from there — also fully automatic, no separate tool
to install. macOS has no automatic path at all (nothing in ocforge or in
SSDTTime itself implements one there — reading live ACPI tables needs macOS
already booted, which is the chicken-and-egg problem this whole tool exists
to get you past); pass `--dsdt` with a folder of tables dumped some other way.
For an I2C-HID trackpad, ocforge also decompiles the DSDT and best-effort
generates **SSDT-GPIO**: the interrupt pin and GPIO controller read straight
from the touchpad's `_CRS`. **On Linux or Windows, a laptop with an I2C-HID
trackpad triggers this automatically** — no `--dsdt`/`--dump-dsdt` needed;
without it (macOS, or a host that genuinely can't dump), SSDT-GPIO silently
never gets generated otherwise — just an easy-to-miss manual-TODO note.
Verify the trackpad after first boot; if it's dead, that pin was wrong and
needs doing by hand.

Networking: Intel/Realtek/Atheros(Killer)/I225-6 Ethernet, Intel Wi-Fi
(`AirportItlwm`) and Broadcom Wi-Fi + Bluetooth (`AirportBrcmFixup`,
`BrcmFirmwareData` + `BrcmPatchRAM3`); laptops on macOS 12+ also get
`BlueToolFixup`.

GPU: an Intel iGPU or an AMD dGPU always drives the display; **NVIDIA has no
macOS driver at all** (Maxwell and newer — Apple dropped even the old Kepler
web-driver path after High Sierra). With an iGPU present, an NVIDIA dGPU
just gets disabled (`nv_disable=1`) and ocforge warns about it — the iGPU
carries the display, no acceleration/CUDA from the NVIDIA card in macOS. With
**no** iGPU and only an NVIDIA (or no) dGPU, there's nothing to show a
display with once macOS hands off from the boot picker. `ocforge plan` /
`explain` / `build` / `offline-installer` catch this and ask **"Sorry, this
build is unsupported. Would you still like to continue?"** — `y` proceeds
(with a loud warning that the target has no display path), anything else
backs out; `--macos N` doesn't skip the question either, since forcing a
version doesn't change what the hardware can do. Not at a terminal (the
GUI shows its own dialog with the same choice) or scripting this? Pass
`--force-unsupported-gpu` to skip straight to yes.

An explicit `--macos N` gets the same treatment against the CPU-generation/
AVX2/AMD rules a target normally has to clear to be *recommended* — forcing
Tahoe on a 7th-gen Kaby Lake iGPU (no Tahoe driver; needs 8th-gen+) asks the
same "continue anyway?" question instead of silently building a real install
that reaches a desktop with corrupted/garbled graphics. `--force-unsupported-os`
is the scripting/GUI equivalent of `--force-unsupported-gpu` for this case.

Older Intel desktops (Sandy Bridge through Kaby Lake, cross-checked against
Dortania's own guide for each) get generation-correct treatment, not one
generic profile: the right SMBIOS per generation and macOS target — bumped
to a newer sibling once a generation's own model is dropped (e.g. Skylake's
iMac17,1 → Kaby Lake's iMac18,1 for Ventura+), or a dGPU-driven MacPro6,1
once a generation's iGPU driver is gone entirely (Ivy Bridge past Big Sur,
Sandy Bridge everywhere ocforge targets); `AppleCpuPmCfgLock` instead of
`AppleXcpmCfgLock` before Haswell (no XCPM that far back); `IgnoreInvalidFlexRatio`
before Skylake; the right `AAPL,ig-platform-id` (+ `framebuffer-fbmem` on
Haswell/Broadwell/Skylake specifically) for each generation's iGPU; and the
stock `CpuPm`/`Cpu0Ist` ACPI tables dropped before Haswell, the other half of
Dortania's fix for XCPM panicking on those CPUs (the replacement, SSDT-PM,
needs Pike's separate `ssdtPRGen.sh` — flagged as a manual step, not
automated here). Sandy Bridge/Ivy Bridge CPU power management is still
rougher than Haswell+ as a result; cross-check the Dortania guide for your
board if you hit `AppleIntelCPUPowerManagement` panics.

Laptops get the same generation-by-generation treatment (Sandy Bridge
through Comet/Ice Lake, again cross-checked against Dortania's own guide for
each) — MacBook/MacBookAir/MacBookPro SMBIOS per generation instead of one
flat pick, bumped the same way desktop's is once a generation's own models
are dropped (e.g. Haswell's MacBookPro11,1 → 11,4/11,5 for Monterey), and
the right laptop `AAPL,ig-platform-id` per generation. **Ice Lake and Comet
Lake are both "10th Gen" in Intel's own marketing but need completely
different SMBIOS/DeviceProperties** — ocforge tells them apart by CPU model
number (Ice Lake's `1065G7`-style 4-digit-plus-graphics-tier naming vs Comet
Lake's plain 5-digit `10510U`), or by iGPU PCI id as a fallback. A real
laptop panel/GPU/chassis splits far more finely than ocforge tracks (exact
screen resolution, precise iGPU sub-model) — each generation's value here is
that guide's own "start here, normally enough" pick, not an exhaustive
per-SKU match; if you get a black screen or 7&nbsp;MB VRAM with no
acceleration, check that generation's Dortania page for the alternate
`ig-platform-id` values it lists.

AMD (Ryzen / Threadripper, following the
[Dortania Zen guide](https://dortania.github.io/OpenCore-Install-Guide/AMD/zen.html)):
`AMD_Vanilla` kernel patches spliced to the core count, `SMCAMDProcessor` +
`AMDRyzenCPUPowerManagement`, `ForgedInvariant` for TSC sync, and
`AppleMCEReporterDisabler` (a plist-only kext; `AppleMCEReporter` panics on
AMD). Quirks: `DummyPowerManagement`, `ProvideCurrentCpuInfo`,
`AppleXcpmCfgLock` off, `DisableIoMapper` off (no VT-d), modern memory map
(`RebuildAppleMemoryMap`/`SyncRuntimePermissions`); `SetupVirtualMap` is on by
default and only turned off on X570/B550/A520/TRx40 boards, per the guide's
own exception list. Threadripper (TRX40/TRX50/WRX80/WRX90) also gets
`DevirtualiseMmio`. The `npci=0x3000` boot-arg is the guide's fallback for
"Above 4G Decoding" unavailable in firmware — not `npci=0x2000`, which does
something different (skips PCI enumeration past config space).

Pre-Zen AMD — Bulldozer/Piledriver/Steamroller/Excavator (Family 15h) and
Jaguar/Puma (Family 16h), following the
[Dortania Bulldozer/Jaguar guide](https://dortania.github.io/OpenCore-Install-Guide/AMD/bulldozer-jaguar.html) —
is also supported: same `AMD_Vanilla` kernel-patch source (spliced to core
count, no CPUID spoof), but none of the three Ryzen-only kexts
(`AMDRyzenCPUPowerManagement`/`SMCAMDProcessor`/`ForgedInvariant`) since
`DummyPowerManagement` is that generation's entire power-management story;
`AppleMCEReporterDisabler` still applies. It also gets the legacy memory map
(`EnableWriteUnprotector` on, `RebuildAppleMemoryMap`/`SyncRuntimePermissions`
off) by default, not the modern-mmap default Ryzen/Threadripper gets — this
is the guide's own default for that era, not the `--legacy-mmap` OEM-firmware
fallback. ocforge can't reliably name every FX-/A-series/E-series/GX- SKU
across that decade of reused branding, so it detects this family as the
inverse of the reliable signal: genuinely-AMD hardware whose brand string
`amd_family()` didn't recognize as some Zen generation.

Pentium Gold / Celeron desktop parts are detected by their `G`-series SKU
(macOS doesn't whitelist their CPUID; without a spoof you get a *Thread 0
crashed* panic once `SSDT-PLUG` loads), and ocforge injects the matching
`Emulate → Cpuid1Data/Cpuid1Mask` spoof to the same-generation i3. They also
have **no AVX2** (Intel fuses it off), so the target is capped at **Monterey**;
Ventura and newer require AVX2 and will not boot.

`ocforge bios` (also folded into `ocforge plan`) prints the BIOS/UEFI settings
to change (AHCI, Secure Boot / CSM off, CFG-Lock, Above-4G) with per-vendor
notes for Dell / HP / Lenovo / the DIY board makers.

Not yet: Wi-Fi chips with no macOS driver at all (Atheros/MediaTek; ocforge
warns and carries on), pre-Sandy-Bridge Intel (rejected up front with a clear
message), and HEDT (X79/X99/X299), where the SSDTs are selected but the MacPro
SMBIOS and HEDT-specific quirks aren't fully modelled, so cross-check the
Dortania HEDT guide.
