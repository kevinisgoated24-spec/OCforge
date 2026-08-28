# ocforge

Build a bootable OpenCore EFI for a machine you can describe.

Point it at the machine (or a saved spec of one), and it works out which macOS
release is viable, resolves OpenCore + the right kexts + SSDTs, assembles a
`config.plist`, and writes the whole EFI — optionally straight onto a USB with
the macOS recovery staged. Runs from Linux, Windows, or macOS as the host.

> derived from public OpenCore / Dortania documentation; MIT — see [LICENSE](LICENSE).

## Install

```bash
pipx install .            # or: pip install -e .[dev]
```

Python 3.11+. No runtime dependencies.

## Use

```bash
# 1. detect this machine (or run it on the target and save the spec)
ocforge probe --save my-pc.json

# 2. see the plan: macOS target, kexts, SSDTs, SMBIOS, boot-args, caveats
ocforge plan --spec my-pc.json

# 3a. assemble an EFI/ folder (downloads OpenCore, kexts, SSDTs; no USB touched)
ocforge build --spec my-pc.json --out ./EFI

# 3b. …or write a bootable USB, macOS recovery included
ocforge usb                              # list writable USB disks first
ocforge build --spec my-pc.json --usb /dev/sdX --recovery
```

The assembled `config.plist` validates clean against `ocvalidate` for the
current OpenCore. Always re-run `ocvalidate` yourself before booting, map your
USB ports after first boot, and fill in a real SMBIOS serial if `macserial`
wasn't available at build time (the tool tells you).

Not yet: DSDT-derived SSDTs (I2C-HID trackpad GPIO pinning is flagged as a
manual step), Wi-Fi beyond Intel/Broadcom, and pre-Sandy-Bridge hosts.

## Layout

| package            | does |
|-------------------|------|
| `ocforge.model`    | the `Machine` value object everything reads |
| `ocforge.probe`    | per-OS hardware detection → `Machine` |
| `ocforge.spec`     | `Machine` ⇄ JSON, for off-target planning |
| `ocforge.catalog`  | macOS compatibility, kext selection, SSDT selection |
| `ocforge.fetch`    | OpenCore / OcBinaryData / kexts / SSDTs / recovery downloads |
| `ocforge.build`    | `BuildPlan` → SMBIOS, config.plist, AMD_Vanilla splice, EFI layout, pipeline |
| `ocforge.media`    | USB enumerate / GPT+FAT32 format / write |
