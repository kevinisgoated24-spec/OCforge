# OCForge

Build a bootable OpenCore EFI for a machine you can describe.

Point it at the machine (or a saved spec of one), and it works out which macOS
release is viable, resolves OpenCore + the right kexts + SSDTs, assembles a
`config.plist`, and writes the whole EFI — optionally straight onto a USB with
the macOS recovery staged. Runs from Linux, Windows, or macOS as the host.

Changelog: New Update Now OCForge Has Linux / MacOS Support You Can Try Everywhere OCForge

> derived from public OpenCore / Dortania documentation; MIT — see [LICENSE](LICENSE).

## Install

```bash
pipx install "git+https://github.com/kevinisgoated24-spec/OCforge.git"
# from a clone:  pipx install .   (or: pip install -e .[dev])
```

Python 3.11+. No runtime dependencies.

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
```

The assembled `config.plist` validates clean against `ocvalidate` for the
current OpenCore. Always re-run `ocvalidate` yourself before booting, map your
USB ports after first boot, and fill in a real SMBIOS serial if `macserial`
wasn't available at build time (the tool tells you).

Without `--dsdt` / `--dump-dsdt` the SSDTs come from Dortania's precompiled
hotpatch set. With them, ocforge fetches [SSDTTime](https://github.com/corpnewt/SSDTTime),
runs the non-interactive ops your machine needs (FakeEC, USBX, PluginType,
PMC, RTCAWAC, PNLF), and merges the compiled `.aml` + any ACPI renames into
the config. `--dump-dsdt` reads `/sys/firmware/acpi/tables` (Linux only,
usually no root); on Windows/macOS pass `--dsdt` with a folder of tables you
dumped.

Networking: Intel/Realtek/Atheros(Killer)/I225-6 Ethernet, Intel Wi-Fi
(`AirportItlwm`) and Broadcom Wi-Fi (`AirportBrcmFixup`); laptops on macOS 12+
also get `BlueToolFixup` for Bluetooth.

Not yet: SSDT-GPIO for I2C-HID trackpads (board-specific, still a manual
SSDTTime step), Wi-Fi other than Intel/Broadcom (Atheros, MediaTek), Broadcom
Bluetooth firmware upload (`BrcmPatchRAM`), and pre-Sandy-Bridge hosts.

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
| `ocforge.build`    | `BuildPlan` → SMBIOS, config.plist, AMD_Vanilla splice, SSDTTime, `rationale` (the "why"), EFI layout, pipeline |
| `ocforge.media`    | USB enumerate / GPT+FAT32 format / write |
