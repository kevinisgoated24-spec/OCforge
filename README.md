# OCforge

<img src="docs/icon.webp" alt="OCforge icon" width="80" align="right">

Build a bootable OpenCore EFI for a machine you can describe.

Point it at the machine (or a saved spec of one), and it works out which macOS
release is viable, resolves OpenCore + the right kexts + SSDTs, assembles a
`config.plist`, and writes the whole EFI — optionally straight onto a USB with
the macOS recovery staged. Runs from Linux, Windows, or macOS as the host.

Changelog: [CHANGELOG.md](CHANGELOG.md) — now with Linux and macOS support.

> derived from public OpenCore / Dortania documentation; MIT — see [LICENSE](LICENSE).

## Install

```bash
pipx install "git+https://github.com/kevinisgoated24-spec/OCforge.git"
# from a clone:  pipx install .   (or: pip install -e .[dev])
```

Python 3.11+. No runtime dependencies.

Downloads come from GitHub releases. Unauthenticated that's 60 API calls/hour;
ocforge caches release lookups per work-dir (6 h) so rebuilds are nearly free,
and it will use a token from `GITHUB_TOKEN` / `GH_TOKEN` or an authenticated
`gh` automatically to lift the ceiling to 5000/hour.

## Use

```bash
# 1. detect this machine (or run it on the target and save the spec)
ocforge probe --save my-pc.json

# 2. see the plan: macOS target, kexts, SSDTs, SMBIOS, boot-args, caveats
ocforge plan --spec my-pc.json

# 2b. or the config.plist decisions themselves, each with a reason + a
#     Dortania link (on AMD: also the live AMD_Vanilla patch list)
ocforge explain --spec my-pc.json          # --json for machine-readable, --offline to skip the fetch

# 3a. assemble an EFI/ folder (downloads OpenCore, kexts, SSDTs; no USB touched)
ocforge build --spec my-pc.json --out ./EFI

# …with SSDTs compiled from the target's own ACPI by SSDTTime
ocforge build --spec my-pc.json --out ./EFI --dsdt ./my-pc-acpi   # folder or DSDT.aml
ocforge build --out ./EFI --dump-dsdt                             # dump this host's tables (Linux)

# 3b. …or write a bootable USB, macOS recovery included
ocforge usb                              # list writable USB disks first
ocforge build --spec my-pc.json --usb /dev/sdX --recovery

# 4. check / tweak an existing EFI
ocforge validate --efi ./EFI                       # OpenCore's ocvalidate on the config
ocforge plist show ./EFI/OC/config.plist           # config.plist -> JSON (hex data sentinels)
ocforge plist save ./EFI/OC/config.plist < edited.json
```

The assembled `config.plist` validates clean against `ocvalidate` for the
current OpenCore. Always re-run `ocvalidate` yourself before booting, map your
USB ports after first boot, and fill in a real SMBIOS serial if `macserial`
wasn't available at build time (the tool tells you).

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

Not yet: Wi-Fi chips with no macOS driver at all (Atheros/MediaTek — ocforge
warns and carries on), pre-Sandy-Bridge Intel (rejected up front with a clear
message), and HEDT (X79/X99/X299) — the SSDTs are selected but the MacPro
SMBIOS and HEDT-specific quirks aren't fully modelled, so cross-check the
Dortania HEDT guide.

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
