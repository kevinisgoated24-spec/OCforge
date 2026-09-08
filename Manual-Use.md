## Manual Use

Three commands take you from bare hardware to a bootable EFI.

**1. Scan this machine.** Writes the specs to `my-pc.json`.

```bash
ocforge probe --save my-pc.json
```

**2. See what it'll build.** macOS version, kexts, SSDTs, each with a reason.

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
at build time. The tool tells you when that happens.
