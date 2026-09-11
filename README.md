# OCforge

<img src="docs/icon.webp" alt="OCforge icon" width="80" align="right">

Make a Bootable OpenCore EFI For Any Laptop/PC You Got.

🎉 **v1.0.0 "Bromine" — our first public release!** See [CHANGELOG.md](CHANGELOG.md) for what's new. Want to help test what's next? Join the beta channel (toggle in the GUI) or the Discord.

## Heres how it works

* Point it at the machine (or a saved spec of one)
* It works out which macOS release is compatible with your hardware, resolves OpenCore + the right kexts + SSDTs, 
* Assembles a `config.plist`, and writes the whole EFI 
* Written efi optionally straight onto a USB with the macOS recovery staged. Runs from Linux, Windows, or macOS as the host.

## Guide

[Guide Link](https://kevinisgoated24-spec.github.io/OCforge/)
> This Guide Is The Tutorial To How Use OCForge Such As (How to use it, Making USB Mapping, Offline Installer, Etc)

Changelog: [CHANGELOG.md](CHANGELOG.md), now with Linux and macOS support.
> Made from public OpenCore / Dortania documentation; MIT, see [LICENSE](LICENSE).

Supported Device And Tested Devices List [SupportedDevice.md](https://github.com/kevinisgoated24-spec/OCforge/blob/master/SupportedDevice.md)
> This is the list of tested and supported devices if you actually managed to get your EFI to work please join in the discord group to tell us:D 

## Install

For Windows:

- Get The Exe From The Release (OCForge) (OCForge-GUI-windows-x64.zip) 

- Open The Exe You Will Be Prompted To Install OCForge-CLI Install It

- If Your Having Issues With The Exe Such As This Error: The code execution cannot proceed because MSVCP140.dll was not found. Please Install This To Fix It: https://aka.ms/vs/16/release/vc_redist.x64.exe

- Go On Detect, Press Detect This PC It Will Show You Your Specs About The PC Such As: CPU, GPU, Network, Board, Storage

- Then Go To Plan Press On The MacOS That You Want To Install And Then Press Generate Plan It Will Show You Everything SMBIOS, Kexts, SSDT, And The Warnings Please Scroll Down On That Page To See If Anything Is Not Working

- Press Config, Generate Config

- Finally Then Press Forge It Will Ask You To Where The EFI To Go (Just do a folder on the desktop copy the location of the folder on the desktop) Put it inside of the textbox then there will be some options:

1. Get The Recovery Image For That MacOS (it will be kinda slow only 600mb or higher)

2. Build SSDT'S From Your Machine (works on Linux and Windows now. macOS still needs you to supply a DSDT folder)

3. Use The Opencore Debug Build (i would keep that off)

4. Get The Offline Image For That MacOS (i would keep that off it will take ages please read on the guide) 

For Linux:

- Same As Windows But This Time You Will Need To Install The Linux Version

- After Unzipping You Will Find The Flutter Open It

- After Opening The Flutter You Will Be Prompted To Install OCForge-CLI Install It

- Go On Detect, Press Detect This PC It Will Show You Your Specs About The PC Such As: CPU, GPU, Network, Board, Storage

- Then Go To Plan Press On The MacOS That You Want To Install And Then Press Generate Plan It Will Show You Everything SMBIOS, Kexts, SSDT, And The Warnings Please Scroll Down On That Page To See If Anything Is Not Working

- Press Config, Generate Config

- Finally Then Press Forge It Will Ask You To Where The EFI To Go (Just do a folder on the desktop copy the location of the folder on the desktop) Put it inside of the textbox then there will be some options:

1. Get The Recovery Image For That MacOS (it will be kinda slow only 600mb or higher)

2. Build SSDT'S From Your Machine (works on Linux and Windows. macOS still needs you to supply a DSDT folder)

3. Use The Opencore Debug Build (i would keep that off)

4. Get The Offline Image For That MacOS (i would keep that off it will take ages please read on the guide) 


For MacOS:
- Adding This Later.

## Manual Use

For Manual Use Commands Check This Link [Manual-Use](https://github.com/kevinisgoated24-spec/OCforge/blob/master/Manual-Use.md)

### Other commands
[Other-Commands](https://github.com/kevinisgoated24-spec/OCforge/blob/master/Other-Commands.md)
> If You Want Read This Part By Clicking On The Link

### Expert mode

Everything above is ocforge deciding for you. If you'd rather do it yourself
— the way the [Dortania guide](https://dortania.github.io/OpenCore-Install-Guide/)
walks through it, decision by decision — a few manual overrides sit on top of
the same detection/build pipeline:

- **ACPI source** — `--dsdt PATH` (a DSDT/folder of tables you already have)
  or `--dump-dsdt` (dump this host's own live tables) instead of Dortania's
  precompiled SSDT set.
- **Force through an unsupported build** — `--force-unsupported-gpu` /
  `--force-unsupported-os` skip the "continue anyway?" prompt outright,
  instead of only being reachable after a build fails once.
- **Kext overrides** — `--exclude-kext NAME` drops a kext ocforge would
  otherwise add; `--include-kext NAME` forces one in that it wouldn't
  otherwise pick (both repeatable — see the table above). Unknown
  `--include-kext` names are rejected with an error rather than silently
  ignored, and any override adds a warning to `ocforge plan`'s output so
  it's clear the pick was manual.
- **SSDT overrides** — `--exclude-ssdt NAME` drops one of the precompiled
  SSDTs ocforge would otherwise add (repeatable), e.g. `--exclude-ssdt
  SSDT-PLUG` if you're handling XCPM some other way. There's no
  `--include-ssdt` — an arbitrary SSDT name doesn't map onto a real
  Dortania asset the way a kext name maps onto a real kext, so adding one
  ocforge doesn't already know about still means supplying it yourself
  (drop the `.aml` into the built `EFI/OC/ACPI/` folder and add it to
  `config.plist`'s `ACPI → Add` by hand, or via `ocforge plist save`).
- **SMBIOS override** — `--smbios MODEL` (e.g. `iMac19,1`) replaces
  ocforge's own board-generation pick outright. Only checked for the right
  *shape* (`Name123,4`) up front; `macserial` is the real authority and
  fails loudly during the build if the model doesn't actually exist.
- **Quirk overrides** — `--quirk NAME=true|false` (repeatable) flips one
  ACPI/Booter/Kernel/UEFI Quirks toggle directly, e.g. `--quirk
  DevirtualiseMmio=false`. On/off toggles only — a handful of Quirks
  entries are numeric settings (a slide count, a timeout) rather than
  booleans, and those are rejected rather than silently coerced. Only
  `build`/`offline-installer` actually apply quirks (there's no
  `config.plist` to apply them to yet at `plan`/`explain` time).
- **Device ID spoof** — `--spoof-device PATH=[VENDOR:]DEVICE` (repeatable)
  presents a different PCI device to macOS at that OpenCore device path,
  e.g. `--spoof-device "PciRoot(0x0)/Pci(0x3,0x0)=1002:73AF"` to spoof an
  unsupported GPU as a supported one — the same DeviceProperties edit
  Hackintosh users already do by hand for hardware without a real macOS
  driver, tied into ocforge as an override. Merges into whatever ocforge
  already computed at that path (a GPU's own `AAPL,ig-platform-id` survives
  a device-id override there) instead of replacing the whole entry, and
  forces the OpenCore DEBUG build on automatically so it's easier to tell
  whether the spoof actually took effect.
- **Review before you trust it** — `ocforge validate --efi ./EFI` runs
  `ocvalidate` on the assembled `config.plist`, and `ocforge plist show` /
  `plist save` round-trip it to JSON for hand editing. The desktop GUI wraps
  both behind a "Validate this EFI" / "Review in Editor" pair right after a
  build finishes.

None of this changes what ocforge *detects* — only what it does with that
detection. If a manual pick makes a machine unbootable, that's on you; the
warning in `plan`'s output is there so you know which parts were manual
before you go looking for what to fix.

### Diagnosing a failed boot

`ocforge logcheck --log PATH` (`--json` for machine-readable output; the
desktop GUI's **Diagnose** tab wraps this) scans an OpenCore boot log or a
macOS panic report against a small, curated list of known trouble
signatures straight from [Dortania's own troubleshooting
guide](https://github.com/dortania/OpenCore-Install-Guide/blob/master/troubleshooting/boot.md):
kernel panics, `Couldn't allocate runtime area` (a KASLR-slide issue, common
on Z390/X99/X299), `Cannot perform kext summary`, `Invalid frame pointer`,
and stalls at `IOConsoleUsers` (no display handoff), `AppleACPICPU` (a
missing SMC key), waiting for the root device, or early PCI/ACPI
enumeration. Each hit comes with an explanation and, where one applies, a
suggested `ocforge` flag to try. Stall-type signatures are lines that are
completely normal on *any* boot — they're only flagged when they're the
last thing the log printed (i.e. the boot actually stopped there), not
wherever they happen to appear. This is a small, hand-picked list, not an
exhaustive parser — a clean scan means none of *these* signatures showed
up, not that the boot definitely succeeded.

## Offline Installer
To Do The Offline Installer Here's A Guide

1.Get gibMacOS From corpnewt [Link For gibMacOS Github](https://github.com/corpnewt/gibmacos) 

2.Unzip It And You Will Find Some Files For Us It's Important To Use The gibMacOS.bat You Will Need Python.

3.After Opening It You Will Find A Lot Of Versions Of MacOS Please Scroll Down To Check The Recovery Option Is Disabled "R. Toggle Recovery-Only (Currently Off)" Then Get Your Build Of MacOS

4.After Waiting To Download It You Will Find Those Files (com_apple_MobileAsset_MacSoftwareUpdate, InstallAssistant.pkg, InstallInfo, MajorOSInfo, UpdateBrain) The File That We Need Will Be The File Called InstallAssistant.pkg Get An Other Usb That Has At Least 20gb Or Less (FORMAT THE USB IN EXFAT!!!) Place That File On The Usb And Then We Will Get The UnPlugged.command Here's Where To Get The File [Link For UnPlugged.command](https://github.com/corpnewt/UnPlugged) As Always Credits To corpnewt for this UnPlugged.command

5. After Placing Those Files On The USB Boot To MacOS Installer Before Go On Disk Utility Format The Disk Or Partiton To APFS And Place A Nice Name I Used The Disk Name As "OCForge Is Cool" But You Can Use Other Names, After Formatting The Disk Go To Utilities > Terminal Type Those Commands Inside Of Your Terminal: cd /Volumes/ ls (for example the ls will show this Untiled 1 Untitled 2, OCForge Is Cool, yourusbname) When You See The Name Of Your USB do this cd /Volumes/yourusbname then do this ./UnPlugged.command You will be ask to confirm to use this MacOS version do y then do Choose a locally discovered Install [macOS version].app Continue It Will Ask You Where Do You Want To Install MacOS Find Your Disk Name And Number And Type The Number And Enter Do Not Touch Anything On The Terminal It Will Show Some Stuff Doing Then It Will Show The MacOS Installer Thats It You Made It:D

## Terminal Offline Installer

```bash
ocforge offline-installer --spec my-pc.json --out ./offline-installer
```

For installing where the *target* machine shouldn't (or can't) touch the
internet mid-install. Downloads the full macOS installer via
[gibMacOS](https://github.com/corpnewt/gibMacOS) and stages
[corpnewt/UnPlugged](https://github.com/corpnewt/UnPlugged) alongside your
EFI — both large, this is the slow part, and it needs *your* internet, once,
on the machine running ocforge.

UnPlugged itself has to run from inside a booted macOS Recovery — that's a
bash script using APIs (`diskutil`, `installer`, `asr`) nothing outside a
real macOS environment has, so ocforge can't run it for you. What it does
handle is getting everything into the two-partition layout UnPlugged
expects:

```
./offline-installer/EFI/                        — your usual EFI, unchanged
./offline-installer/com.apple.recovery.boot/     — the boot environment
./offline-installer/ExFAT/InstallAssistant.pkg   — the actual installer
./offline-installer/ExFAT/UnPlugged.command
```

Format your USB with a FAT32 partition (~1 GB — `EFI/` +
`com.apple.recovery.boot/`) and an ExFAT partition (the rest — everything
under `ExFAT/`), boot it, open Terminal in Recovery, `cd` to the ExFAT
volume, and run `./UnPlugged.command` — it walks you through picking the
target disk from there. Or skip the manual formatting and pass `--usb
/dev/sdX` to have ocforge partition + write both for you (destructive, asks
to confirm first; needs `exfatprogs` on Linux — `sudo apt install
exfatprogs` — macOS and Windows format ExFAT natively).

On macOS Sonoma (14) and newer, Recovery can't mount FAT32/ExFAT itself, so
the *boot* environment deliberately uses an older BaseSystem (Monterey) even
when the *install payload* targets something newer — ocforge does this
automatically and says so; it's expected, not a bug.

## Reporting a problem

`ocforge report` (also a bug icon in the GUI's nav rail) opens a GitHub "New
issue" pre-filled with your ocforge version and hardware; you just describe
what happened and hit submit. It's not a bot with write access to the repo:
there's no shared credential to leak or abuse, it fills in
[the bug-report form](.github/ISSUE_TEMPLATE/bug_report.yml) client-side and
you submit it yourself under your own (free) GitHub account, same as filing
one by hand. Attach whatever you have: a panic photo, the `opencore-*.txt`
from the EFI partition, your `spec.json`, the relevant bit of `config.plist`.

Are you In the discord server? type /report to automatically submit a report!

# iCloud Fix For Unable To Sign In Nor Log In

If iCloud, iMessage, or FaceTime fail to authenticate, the most common cause is a
**burned SMBIOS identity** — a serial number that's already been used to sign into
iCloud on another machine (real Mac, VM, or another Hackintosh).

**Fix checklist:**
- Use a Mac model (SMBIOS) that actually matches your CPU generation ([check Dortania's guide](https://dortania.github.io/OpenCore-Install-Guide/) for your CPU and confirm it supports your macOS version)
- Generate a **fresh** Serial Number, Board Serial (MLB), and System UUID — never reuse one from a guide, video, or old config
- Set `ROM` to your real network adapter's MAC address (not random)
- Sign out of Apple ID, clear iCloud/account caches, and reset NVRAM before signing in again
- Confirm system date/time is correct and set to automatic
- Once sign-in succeeds, keep this identity permanently — don't regenerate it on reinstall

- GenSMBIOS Download Page: [GenSMBIOS](https://github.com/corpnewt/gensmbios)
- ProperTree Download Page: [ProperTree](https://github.com/corpnewt/propertree)

## Where to put the SMBIOS values

All SMBIOS values live inside your **EFI/OC/config.plist**, under: PlatformInfo → Generic

The relevant fields are:

| Field | What it is |
|---|---|
| `SystemProductName` | The Mac model you're spoofing (e.g. `iMac19,1`) |
| `SystemSerialNumber` | The fresh Serial Number |
| `MLB` | The Board Serial |
| `SystemUUID` | The fresh System UUID |
| `ROM` | Your real network adapter's MAC address (as raw hex) |

**How to edit them:**
- Open `config.plist` with **ProperTree** (GUI plist editor) or **OpenCore Configurator**
- Navigate to `PlatformInfo → Generic`
- Paste in the freshly generated Serial, MLB, UUID, and your real ROM value
- Save the file, then copy the updated `config.plist` back onto your EFI partition (`EFI/OC/`)
- Reboot for the new identity to take effect

OCForge generates a unique, valid SMBIOS + ROM pairing per build and writes it directly into `config.plist` for you, so this step is handled automatically when using OCForge.
Not Always OCForge Can Get A Imei Or Smtg Work

## Desktop GUI

[`gui/`](gui/) is a Flutter front-end (Windows / macOS / Linux): Material 3
Expressive, light/dark + seven accent themes, tabs for Detect / Plan / Config
(the `explain` view) / Forge. It drives this CLI; on first run it offers to
install Python + `ocforge` for you, and falls back to a demo mode otherwise.
Prebuilt bundles are attached to each `gui-v*` [release](https://github.com/kevinisgoated24-spec/OCforge/releases);
see [`gui/README.md`](gui/README.md).

**Beta channel:** the flask icon in the bottom-left of the GUI (next to
Theme and Report-a-bug) opts into `gui-beta-v*` releases — builds off the
[`beta`](https://github.com/kevinisgoated24-spec/OCforge/tree/beta) branch,
for testers trying things out before they land in a regular `gui-v*`
release. Off by default; toggling it re-checks for an update immediately.

## Layout
[Layout](https://github.com/kevinisgoated24-spec/OCforge/blob/master/Layout-UIRead.md)
