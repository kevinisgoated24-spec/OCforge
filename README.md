<img src="docs/icon.webp" alt="OCforge icon" width="80" align="right">

# OCforge

**Build a bootable OpenCore EFI for any laptop or PC you own.**

This is the **beta branch** — for what's next after v1.2.0, ahead of the
following stable release. Join the Discord OCForge For Beta Testers to help
test it.

⚙️ **v1.2.0 "Tungsten" is out.**
See [CHANGELOG.md](CHANGELOG.md) for what's new. Want to help test what's next? Join the beta channel (toggle in the GUI) or hop into the Discord.

---

## Table of contents

- [How it works](#how-it-works)
- [Guide](#guide)
- [Supported devices](#supported-devices)
- [Installation](#installation)
- [Manual use](#manual-use)
- [Expert mode](#expert-mode)
- [Diagnosing a failed boot](#diagnosing-a-failed-boot)
- [Offline installer](#offline-installer)
- [Reporting a problem](#reporting-a-problem)
- [iCloud sign-in fix](#icloud-fix-for-unable-to-sign-in--log-in)
- [Desktop GUI](#desktop-gui)
- [Layout](#layout)

---

## How it works

1. Point OCforge at your machine (live scan, or a saved hardware spec).
2. It works out which macOS releases are compatible with your hardware, then resolves the right OpenCore version, kexts, and SSDTs.
3. It assembles a `config.plist` and writes the full EFI folder.
4. Optionally, it writes the EFI straight onto a USB drive with the macOS recovery image staged and ready to boot.

Runs on Linux, Windows, or macOS as the host.

## Guide

📖 **[Read the full guide](https://kevinisgoated24-spec.github.io/OCforge/)** — covers everything from first-time setup to USB mapping and offline installers.

**Changelog:** [CHANGELOG.md](CHANGELOG.md) — now with Linux and macOS support.

**License:** MIT, built on public OpenCore / Dortania documentation. See [LICENSE](LICENSE).

## Supported devices

See [SupportedDevice.md](https://github.com/kevinisgoated24-spec/OCforge/blob/master/SupportedDevice.md) for the list of tested and supported hardware.

Got it working on something not listed? Let us know on Discord so we can add it.

---

## Installation

### Windows

1. Download `OCForge-GUI-windows-x64.zip` from the [Releases](../../releases) page.
2. Run the executable — you'll be prompted to install **OCForge-CLI** as well. Install it.
3. If you hit an error like *"The code execution cannot proceed because MSVCP140.dll was not found"*, install the [VC++ Redistributable](https://aka.ms/vs/16/release/vc_redist.x64.exe) to fix it.
4. Go to **Detect** → **Detect This PC**. It scans your specs (CPU, GPU, network, motherboard, storage).
5. Go to **Plan**, pick the macOS version you want to install, and press **Generate Plan**. This shows your SMBIOS, kexts, SSDTs, and any warnings — scroll down to check for issues.
6. Go to **Config** → **Generate Config**.
7. Go to **Forge**. You'll be asked where to write the EFI (e.g. a folder on your desktop — copy that folder's path into the textbox). You'll then see a few options:
   - **Get the recovery image** for that macOS version (~600 MB+, can be slow).
   - **Build SSDTs from your machine** (works on Linux and Windows; on macOS you'll still need to supply a DSDT folder).
   - **Use the OpenCore debug build** (recommended off).
   - **Get the offline image** for that macOS version (recommended off — see the guide, it takes a while).

### Linux

Same flow as Windows, but grab the Linux build instead:

1. Unzip the release and open the app (a Flutter build).
2. You'll be prompted to install **OCForge-CLI** — install it.
3. Go to **Detect** → **Detect This PC** to scan your specs (CPU, GPU, network, motherboard, storage).
4. Go to **Plan**, pick your target macOS version, and press **Generate Plan** to review SMBIOS, kexts, SSDTs, and warnings.
5. Go to **Config** → **Generate Config**.
6. Go to **Forge**, choose your EFI output folder, and pick from the same options as Windows above (recovery image, SSDT building — supported on Linux — debug build, offline image).

### macOS

Coming soon.

---

## Manual use

For manual-use commands, see [Manual-Use.md](https://github.com/kevinisgoated24-spec/OCforge/blob/master/Manual-Use.md).

### Other commands

See [Other-Commands.md](https://github.com/kevinisgoated24-spec/OCforge/blob/master/Other-Commands.md).

### Expert mode

Everything above is OCforge deciding for you. If you'd rather do it yourself — the way the [Dortania guide](https://dortania.github.io/OpenCore-Install-Guide/) walks through it, decision by decision — a few manual overrides sit on top of the same detection/build pipeline:

- **ACPI source** — `--dsdt PATH` (a DSDT/folder of tables you already have) or `--dump-dsdt` (dump this host's own live tables) instead of Dortania's precompiled SSDT set.
- **Force through an unsupported build** — `--force-unsupported-gpu` / `--force-unsupported-os` skip the "continue anyway?" prompt outright, instead of only being reachable after a build fails once.
- **Kext overrides** — `--exclude-kext NAME` drops a kext OCforge would otherwise add; `--include-kext NAME` forces one in that it wouldn't otherwise pick (both repeatable). Unknown `--include-kext` names are rejected with an error rather than silently ignored, and any override adds a warning to `ocforge plan`'s output so it's clear the pick was manual.
- **SSDT overrides** — `--exclude-ssdt NAME` drops one of the precompiled SSDTs OCforge would otherwise add (repeatable), e.g. `--exclude-ssdt SSDT-PLUG` if you're handling XCPM some other way. There's no `--include-ssdt` — an arbitrary SSDT name doesn't map onto a real Dortania asset the way a kext name maps onto a real kext, so adding one OCforge doesn't already know about still means supplying it yourself (drop the `.aml` into the built `EFI/OC/ACPI/` folder and add it to `config.plist`'s `ACPI → Add` by hand, or via `ocforge plist save`).
- **SMBIOS override** — `--smbios MODEL` (e.g. `iMac19,1`) replaces OCforge's own board-generation pick outright. Only checked for the right *shape* (`Name123,4`) up front; `macserial` is the real authority and fails loudly during the build if the model doesn't actually exist.
- **Quirk overrides** — `--quirk NAME=true|false` (repeatable) flips one ACPI/Booter/Kernel/UEFI Quirks toggle directly, e.g. `--quirk DevirtualiseMmio=false`. On/off toggles only — a handful of Quirks entries are numeric settings (a slide count, a timeout) rather than booleans, and those are rejected rather than silently coerced. Only `build`/`offline-installer` actually apply quirks (there's no `config.plist` to apply them to yet at `plan`/`explain` time).
- **Device ID spoof** — `--spoof-device PATH=[VENDOR:]DEVICE` (repeatable) presents a different PCI device to macOS at that OpenCore device path, e.g. `--spoof-device "PciRoot(0x0)/Pci(0x3,0x0)=1002:73AF"` to spoof an unsupported GPU as a supported one — the same DeviceProperties edit Hackintosh users already do by hand for hardware without a real macOS driver, tied into OCforge as an override. Merges into whatever OCforge already computed at that path (a GPU's own `AAPL,ig-platform-id` survives a device-id override there) instead of replacing the whole entry, and forces the OpenCore DEBUG build on automatically so it's easier to tell whether the spoof actually took effect.
- **Review before you trust it** — `ocforge validate --efi ./EFI` runs `ocvalidate` on the assembled `config.plist`, and `ocforge plist show` / `plist save` round-trip it to JSON for hand editing. The desktop GUI wraps both behind a "Validate this EFI" / "Review in Editor" pair right after a build finishes.

None of this changes what OCforge *detects* — only what it does with that detection. If a manual pick makes a machine unbootable, that's on you; the warning in `plan`'s output is there so you know which parts were manual before you go looking for what to fix.

### Diagnosing a failed boot

`ocforge logcheck --log PATH` (`--json` for machine-readable output; the desktop GUI's **Diagnose** tab wraps this) scans an OpenCore boot log or a macOS panic report against a small, curated list of known trouble signatures straight from [Dortania's own troubleshooting guide](https://github.com/dortania/OpenCore-Install-Guide/blob/master/troubleshooting/boot.md): kernel panics, `Couldn't allocate runtime area` (a KASLR-slide issue, common on Z390/X99/X299), `Cannot perform kext summary`, `Invalid frame pointer`, and stalls at `IOConsoleUsers` (no display handoff), `AppleACPICPU` (a missing SMC key), waiting for the root device, or early PCI/ACPI enumeration.

Each hit comes with an explanation and, where one applies, a suggested `ocforge` flag to try. Stall-type signatures are lines that are completely normal on *any* boot — they're only flagged when they're the last thing the log printed (i.e. the boot actually stopped there), not wherever they happen to appear. This is a small, hand-picked list, not an exhaustive parser — a clean scan means none of *these* signatures showed up, not that the boot definitely succeeded.

---

## Offline installer

### Manual guide

1. Get **gibMacOS** from corpnewt: [github.com/corpnewt/gibmacos](https://github.com/corpnewt/gibmacos)
2. Unzip it. You'll need Python to run `gibMacOS.bat`.
3. Once it's open, scroll to the recovery toggle and make sure **"R. Toggle Recovery-Only"** is set to **Off**, then pick the macOS build you want.
4. Once the download finishes you'll have several files (`com_apple_MobileAsset_MacSoftwareUpdate`, `InstallAssistant.pkg`, `InstallInfo`, `MajorOSInfo`, `UpdateBrain`). The one you need is **`InstallAssistant.pkg`**.
   - Grab a second USB drive, at least 20 GB, formatted as **ExFAT**.
   - Copy `InstallAssistant.pkg` onto it.
   - Also grab **UnPlugged.command** from corpnewt: [github.com/corpnewt/UnPlugged](https://github.com/corpnewt/UnPlugged) (credit to corpnewt for this tool) and copy it onto the same USB.
5. Boot into the macOS installer. Before anything else, open **Disk Utility** and format the target disk/partition as **APFS**, giving it a name of your choice.
   Then go to **Utilities → Terminal** and run:

   ```bash
   cd /Volumes/
   ls
   ```

   This lists your mounted volumes (e.g. `Untitled 1`, `Untitled 2`, your target disk name, your USB name). Find your USB's name, then:

   ```bash
   cd /Volumes/yourusbname
   ./UnPlugged.command
   ```

   Confirm you want to use this macOS version (`y`), choose **"Choose a locally discovered Install [macOS version].app"**, continue, then pick the disk you formatted earlier by number and press Enter. Don't touch the terminal after that — it'll do its thing and drop you into the macOS installer. That's it, you're done.

### Terminal offline installer

```bash
ocforge offline-installer --spec my-pc.json --out ./offline-installer
```

For installing where the *target* machine shouldn't (or can't) touch the internet mid-install. Downloads the full macOS installer via [gibMacOS](https://github.com/corpnewt/gibMacOS) and stages [corpnewt/UnPlugged](https://github.com/corpnewt/UnPlugged) alongside your EFI — both large, this is the slow part, and it needs *your* internet, once, on the machine running OCforge.

UnPlugged itself has to run from inside a booted macOS Recovery — it's a bash script using APIs (`diskutil`, `installer`, `asr`) nothing outside a real macOS environment has, so OCforge can't run it for you. What it does handle is getting everything into the two-partition layout UnPlugged expects:

```
./offline-installer/EFI/                        — your usual EFI, unchanged
./offline-installer/com.apple.recovery.boot/     — the boot environment
./offline-installer/ExFAT/InstallAssistant.pkg   — the actual installer
./offline-installer/ExFAT/UnPlugged.command
```

Format your USB with a FAT32 partition (~1 GB — `EFI/` + `com.apple.recovery.boot/`) and an ExFAT partition (the rest — everything under `ExFAT/`), boot it, open Terminal in Recovery, `cd` to the ExFAT volume, and run `./UnPlugged.command` — it walks you through picking the target disk from there.

Or skip the manual formatting and pass `--usb /dev/sdX` to have OCforge partition + write both for you (destructive, asks to confirm first; needs `exfatprogs` on Linux — `sudo apt install exfatprogs` — macOS and Windows format ExFAT natively).

> **Note:** On macOS Sonoma (14) and newer, Recovery can't mount FAT32/ExFAT itself, so the *boot* environment deliberately uses an older BaseSystem (Monterey) even when the *install payload* targets something newer. OCforge does this automatically — it's expected, not a bug.

---

## Reporting a problem

`ocforge report` (also a bug icon in the GUI's nav rail) opens a GitHub "New issue" pre-filled with your OCforge version and hardware — you just describe what happened and hit submit. It's not a bot with write access to the repo: there's no shared credential to leak or abuse. It fills in [the bug-report form](.github/ISSUE_TEMPLATE/bug_report.yml) client-side and you submit it yourself under your own (free) GitHub account, same as filing one by hand.

Attach whatever you have: a panic photo, the `opencore-*.txt` from the EFI partition, your `spec.json`, the relevant bit of `config.plist`.

In the Discord server, you can also type `/report` to submit one automatically.

---

## iCloud fix for unable to sign in / log in

If iCloud, iMessage, or FaceTime fail to authenticate, the most common cause is a **burned SMBIOS identity** — a serial number that's already been used to sign into iCloud on another machine (real Mac, VM, or another Hackintosh).

**Fix checklist:**

- Use a Mac model (SMBIOS) that actually matches your CPU generation — check [Dortania's guide](https://dortania.github.io/OpenCore-Install-Guide/) for your CPU and confirm it supports your macOS version.
- Generate a **fresh** Serial Number, Board Serial (MLB), and System UUID — never reuse one from a guide, video, or old config.
- Set `ROM` to your real network adapter's MAC address (not random).
- Sign out of your Apple ID, clear iCloud/account caches, and reset NVRAM before signing in again.
- Confirm the system date/time is correct and set to automatic.
- Once sign-in succeeds, keep this identity permanently — don't regenerate it on reinstall.

**Tools:**
- [GenSMBIOS](https://github.com/corpnewt/gensmbios)
- [ProperTree](https://github.com/corpnewt/propertree)

### Where to put the SMBIOS values

All SMBIOS values live inside your **`EFI/OC/config.plist`**, under `PlatformInfo → Generic`:

| Field | What it is |
|---|---|
| `SystemProductName` | The Mac model you're spoofing (e.g. `iMac19,1`) |
| `SystemSerialNumber` | The fresh Serial Number |
| `MLB` | The Board Serial |
| `SystemUUID` | The fresh System UUID |
| `ROM` | Your real network adapter's MAC address (as raw hex) |

**How to edit them:**

1. Open `config.plist` with **ProperTree** (GUI plist editor) or **OpenCore Configurator**.
2. Navigate to `PlatformInfo → Generic`.
3. Paste in the freshly generated Serial, MLB, UUID, and your real ROM value.
4. Save the file, then copy the updated `config.plist` back onto your EFI partition (`EFI/OC/`).
5. Reboot for the new identity to take effect.

OCforge generates a unique, valid SMBIOS + ROM pairing per build and writes it directly into `config.plist` for you, so this step is handled automatically when using OCforge. That said, it isn't a silver bullet — some auxiliary identifiers (e.g. baseband/IMEI-style fields tied to certain services) may still need manual attention on specific setups.

---

## Desktop GUI

[`gui/`](gui/) is a Flutter front-end (Windows / macOS / Linux): Material 3 Expressive, light/dark + seven accent themes, tabs for Detect / Plan / Config (the `explain` view) / Forge. It drives this CLI; on first run it offers to install Python + `ocforge` for you, and falls back to a demo mode otherwise.

Prebuilt bundles are attached to each `gui-v*` [release](https://github.com/kevinisgoated24-spec/OCforge/releases); see [`gui/README.md`](gui/README.md).

**Beta channel:** the flask icon in the bottom-left of the GUI (next to Theme and Report-a-bug) opts into `gui-beta-v*` releases — builds off the [`beta`](https://github.com/kevinisgoated24-spec/OCforge/tree/beta) branch, for testers trying things out before they land in a regular `gui-v*` release. Off by default; toggling it re-checks for an update immediately.

## Layout

See [Layout-UIRead.md](https://github.com/kevinisgoated24-spec/OCforge/blob/master/Layout-UIRead.md).
