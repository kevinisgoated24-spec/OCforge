# OCforge

<img src="docs/icon.webp" alt="OCforge icon" width="80" align="right">

make a bootable OpenCore EFI for any laptop/pc you got.

## heres how it works

* point it at the machine (or a saved spec of one)
* it works out which macOS release is compatible with your hardware, resolves OpenCore + the right kexts + SSDTs, 
* assembles a `config.plist`, and writes the whole EFI 
* written efi optionally straight onto a USB with the macOS recovery staged. Runs from Linux, Windows, or macOS as the host.

Changelog: [CHANGELOG.md](CHANGELOG.md) — now with Linux and macOS support.

> made from public OpenCore / Dortania documentation; MIT — see [LICENSE](LICENSE).

## Install

```bash
pipx install "git+https://github.com/kevinisgoated24-spec/OCforge.git"
# from a clone:  pipx install .   (or: pip install -e .[dev])
```

Python 3.11+. No runtime dependencies.

Downloads come from GitHub releases.

## Use

Three commands take you from bare hardware to a bootable EFI.

**1. Scan this machine.** Writes the specs to `my-pc.json`.

```bash
ocforge probe --save my-pc.json
```

**2. See what it'll build** — macOS version, kexts, SSDTs, each with a reason.

```bash
ocforge plan --spec my-pc.json
```

**3. Build it.** Either an `EFI/` folder you copy onto the drive yourself:

```bash
ocforge build --spec my-pc.json --out ./EFI
```

…or written straight onto a USB stick with the macOS recovery included. Run
`ocforge usb` first to get the disk name, then:

```bash
ocforge build --spec my-pc.json --usb /dev/sdX --recovery
```

That's the whole flow. Copy the `EFI` folder to your drive's EFI partition and boot.

Before you boot: re-run `ocvalidate` yourself (see below), map your USB ports
after first boot, and set a real SMBIOS serial if `macserial` wasn't available
at build time — the tool tells you when that happens.

### Other commands

| command | what it does |
|---|---|
| `ocforge explain --spec my-pc.json` | every `config.plist` decision with a Dortania link (`--json`, `--offline`) |
| `ocforge bios --spec my-pc.json` | BIOS/UEFI settings to change for this box |
| `ocforge validate --efi ./EFI` | run OpenCore's `ocvalidate` on the config |
| `ocforge plist show ./EFI/OC/config.plist` | `config.plist` → JSON |
| `ocforge plist save ./EFI/OC/config.plist < edited.json` | write edited JSON back |
| `ocforge build --spec my-pc.json --out ./EFI --dsdt ./my-pc-acpi` | compile SSDTs from the target's own ACPI |
| `ocforge build --out ./EFI --dump-dsdt` | dump this host's ACPI tables (Linux) |
| `ocforge report --spec my-pc.json` | file a bug with version + hardware pre-filled |

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
PNLF), and fills the rest (XOSI/IMEI/CPUR/…) from the prebuilt set. `--dump-dsdt` reads
`/sys/firmware/acpi/tables` (Linux only,
usually no root); on Windows/macOS pass `--dsdt` with a folder of tables you
dumped. For an I2C-HID trackpad, ocforge also decompiles the DSDT and
best-effort generates **SSDT-GPIO** — the interrupt pin and GPIO controller
read straight from the touchpad's `_CRS`. Verify the trackpad after first boot;
if it's dead, that pin was wrong and needs doing by hand.

Networking: Intel/Realtek/Atheros(Killer)/I225-6 Ethernet, Intel Wi-Fi
(`AirportItlwm`) and Broadcom Wi-Fi + Bluetooth (`AirportBrcmFixup`,
`BrcmFirmwareData` + `BrcmPatchRAM3`); laptops on macOS 12+ also get
`BlueToolFixup`.

AMD (Ryzen / Threadripper, following the
[Dortania Zen guide](https://dortania.github.io/OpenCore-Install-Guide/AMD/zen.html)):
`AMD_Vanilla` kernel patches spliced to the core count, `SMCAMDProcessor` +
`AMDRyzenCPUPowerManagement`, `ForgedInvariant` for TSC sync, and
`AppleMCEReporterDisabler` (a plist-only kext — `AppleMCEReporter` panics on
AMD). Quirks: `DummyPowerManagement`, `ProvideCurrentCpuInfo`,
`AppleXcpmCfgLock` off, `DisableIoMapper` off (no VT-d), `SetupVirtualMap` off;
Threadripper (TRX40/TRX50/WRX80) also gets `DevirtualiseMmio`.

Pentium Gold / Celeron desktop parts are detected by their `G`-series SKU
(macOS doesn't whitelist their CPUID — without a spoof you get a *Thread 0
crashed* panic once `SSDT-PLUG` loads), and ocforge injects the matching
`Emulate → Cpuid1Data/Cpuid1Mask` spoof to the same-generation i3. They also
have **no AVX2** (Intel fuses it off), so the target is capped at **Monterey**
— Ventura and newer require AVX2 and will not boot.

`ocforge bios` (also folded into `ocforge plan`) prints the BIOS/UEFI settings
to change — AHCI, Secure Boot / CSM off, CFG-Lock, Above-4G — with per-vendor
notes for Dell / HP / Lenovo / the DIY board makers.

Not yet: Wi-Fi chips with no macOS driver at all (Atheros/MediaTek — ocforge
warns and carries on), pre-Sandy-Bridge Intel (rejected up front with a clear
message), and HEDT (X79/X99/X299) — the SSDTs are selected but the MacPro
SMBIOS and HEDT-specific quirks aren't fully modelled, so cross-check the
Dortania HEDT guide.

## Reporting a problem

`ocforge report` (also a bug icon in the GUI's nav rail) opens a GitHub "New
issue" pre-filled with your ocforge version and hardware — you just describe
what happened and hit submit. It's not a bot with write access to the repo:
there's no shared credential to leak or abuse, it fills in
[the bug-report form](.github/ISSUE_TEMPLATE/bug_report.yml) client-side and
you submit it yourself under your own (free) GitHub account, same as filing
one by hand. Attach whatever you have — a panic photo, the `opencore-*.txt`
from the EFI partition, your `spec.json`, the relevant bit of `config.plist`.

Running a Discord server for this? [`discordbot/`](discordbot/) is a
self-hosted `/report` slash command that opens the same kind of form and
*does* file the issue directly, via a GitHub token scoped to just
`Issues: write` on this repo. That's a real (if narrow) credential, so it's
opt-in and self-hosted — see [`discordbot/README.md`](discordbot/README.md)
for the trade-off and setup.

## Desktop GUI

[`gui/`](gui/) is a Flutter front-end (Windows / macOS / Linux) — Material 3
Expressive, light/dark + seven accent themes, tabs for Detect / Plan / Config
(the `explain` view) / Forge. It drives this CLI; on first run it offers to
install Python + `ocforge` for you, and falls back to a demo mode otherwise.
Prebuilt bundles are attached to each `gui-v*` [release](https://github.com/kevinisgoated24-spec/OCforge/releases);
see [`gui/README.md`](gui/README.md).

## Layout

| package            | does |
|-------------------|------|
| `ocforge.model`    | the `Machine` value object everything reads |
| `ocforge.probe`    | per-OS hardware detection → `Machine`; ACPI-table dump for SSDTTime |
| `ocforge.spec`     | `Machine` ⇄ JSON, for off-target planning |
| `ocforge.catalog`  | macOS compatibility, kext selection, SSDT selection |
| `ocforge.fetch`    | OpenCore / OcBinaryData / kexts / SSDTs / SSDTTime / recovery downloads |
| `ocforge.build`    | `BuildPlan` → SMBIOS, config.plist, AMD_Vanilla splice, SSDTTime, SSDT-GPIO from the DSDT, `rationale` (the "why"), EFI layout, pipeline |
| `ocforge.media`    | USB enumerate / GPT+FAT32 format / write |
