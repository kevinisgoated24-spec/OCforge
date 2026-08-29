# Changelog

Notable changes per release. Releases are tagged `gui-vX.Y.Z` and carry the
desktop GUI bundles; each entry also covers the CLI changes that shipped with it.

## gui-v0.4.12

- **iGPU-only Coffee Lake desktops now use `Macmini8,1`** instead of
  `iMac19,1`. The iMac SMBIOS assumes a discrete GPU; the 2018 Mac mini runs
  UHD 630 as its only GPU, which matches an iGPU-only build's power
  management and board-id expectations.

## gui-v0.4.11

- **Pentium/Celeron are capped at Monterey.** They have no AVX2 (Intel fuses
  it off), which Ventura and newer require — building for Sequoia was a
  guaranteed *Thread 0 crashed* even with the CPUID spoof. `recommended()`
  now returns Monterey for them; a bare Core i-series with no probed feature
  flags (Windows/macOS probe) is assumed AVX2-capable instead of being
  wrongly capped.
- **New `ocforge bios`** — a BIOS/UEFI checklist for the target machine
  (AHCI, Secure Boot / CSM off, CFG-Lock, Above-4G, …) with per-vendor notes
  for Dell / HP / Lenovo / DIY boards. Also appears as a "BIOS settings"
  section in `ocforge plan` (so the GUI Plan tab shows it).

## gui-v0.4.10

- **Fixed dead kext repos.** `RealtekRTL8111` pointed at a repo that no longer
  exists (`HTTP 404`); it, plus `AppleIGC`, `CpuTopologyRebuild` and
  `ECEnabler`, now point at maintained sources (`Mieze/RTL8111_driver_for_OS_X`,
  `SongXiaoXi/AppleIGC`, `b00t0x/CpuTopologyRebuild`, `averycblack/ECEnabler`).
- **Always pick the RELEASE asset.** When a repo ships both `-DEBUG` and
  `-RELEASE` zips, the shortest-name tiebreak was silently choosing `-DEBUG`
  (affected `ForgedInvariant`, `USBToolBox`, and the newly-fixed repos).

## gui-v0.4.9

- **The GUI now detects a stale `ocforge` CLI.** `ocforge --version` finally
  reports a real number (was frozen at `0.0.1`), and the first-run gate
  compares it to the minimum this build needs — if the CLI is behind (the
  usual cause of "only SSDT-EC / empty Cpuid1Data" after an app update, since
  the gate only ever *installed* the CLI, never upgraded it), it shows an
  **"Update & continue"** button that runs the in-place `pip --upgrade`.

## gui-v0.4.8

More robust Pentium/Celeron and Intel-generation detection — a spec built
before 0.4.6, or one where the OS reported a generic CPUID name instead of a
marketing string, was still coming out as "generation unknown" (only
`SSDT-EC`, empty `Cpuid1Data`):

- **Intel generation is recovered from the iGPU** when the CPU brand can't be
  parsed — the iGPU PCI device id maps cleanly to a generation (UHD 630
  `8086:3E92` → Coffee Lake). Runs in both `probe` and `plan`.
- **The CPUID spoof also triggers for a 2-core Coffee/Comet Lake desktop**
  even without a "Pentium"/"Celeron" brand string (every 8th-gen-and-newer i3
  has 4 cores), so `Cpuid1Data`/`Cpuid1Mask` get filled either way.

## gui-v0.4.7

- Verified `acpi.select()` against every row of the
  [Dortania prebuilt-SSDT matrix](https://dortania.github.io/Getting-Started-With-ACPI/ssdt-methods/ssdt-prebuilt.html)
  (21 configs). One gap fixed: **laptop** Sandy/Ivy Bridge on a mobile PCH
  (HM65/HM67/HM70…HM77 etc.) now gets `SSDT-IMEI` — the chipset list was
  desktop-only.

## gui-v0.4.6

- **Pentium Gold / Celeron support.** These desktop parts have no `i3/i5`
  number, so ocforge was reading them as "generation unknown" — no
  `SSDT-PLUG`, no `ig-platform-id`, and a *Thread 0 crashed* panic at boot
  because macOS doesn't whitelist their CPUID. Now the `G`-series SKU maps to
  the right generation (G5xxx → Coffee Lake, G6xxx → Comet Lake, …) and the
  config gets the `Emulate → Cpuid1Data/Cpuid1Mask` spoof to that gen's i3
  (i3-8100 for Coffee Lake, etc.).

## gui-v0.4.5

AMD fixes, cross-checked against the
[Dortania Zen guide](https://dortania.github.io/OpenCore-Install-Guide/AMD/zen.html):

- **`AppleMCEReporterDisabler`** is now included on every AMD build — a
  plist-only kext that blocks `AppleMCEReporter` (kernel panic on AMD). Kexts
  can now be sourced from a direct URL, not just a GitHub release, and a
  codeless kext gets an empty `ExecutablePath` (a bogus path made OpenCore skip
  the kext at boot).
- `DisableIoMapper` is left **off** on AMD (no VT-d/DMAR — the quirk is
  irrelevant there).
- Threadripper (TRX40/TRX50/WRX80/WRX90, or "Threadripper" in the CPU brand)
  now enables `DevirtualiseMmio`.

## gui-v0.4.4

- **Fixed GitHub API rate-limit failures** on repeat builds. Release lookups
  are now deduped per repo and cached on disk (6 h TTL) in the work dir — a
  rebuild within the window makes **zero** API calls — and a token from
  `GITHUB_TOKEN` / `GH_TOKEN` or an authenticated `gh` CLI is picked up
  automatically (60/hr → 5000/hr). A genuine rate-limit now raises a clear
  message with the reset time instead of a bare `HTTP 403`.

## gui-v0.4.3

- **`ocforge validate`** — runs OpenCore's `ocvalidate` (from the cached
  OpenCore package) against a `config.plist`; `--efi DIR` auto-finds
  `EFI/OC/config.plist`. Wired into the GUI: a "Validate this EFI" button on
  Forge after a build, and a "Validate" button in the editor.
- **`ocforge plist show|save`** — `config.plist` ⇄ JSON with hex `__data__` /
  ISO `__date__` sentinels, key order preserved.
- **GUI "Editor" tab** — an OCAT-style tree editor: open a `config.plist`,
  edit bools (switch), numbers, strings and data (hex), save it back.

## gui-v0.4.2

**ACPI — the full Dortania prebuilt-SSDT matrix.** `ocforge` now selects tables
by CPU family + chassis exactly as the
[prebuilt-SSDT guide](https://dortania.github.io/Getting-Started-With-ACPI/ssdt-methods/ssdt-prebuilt.html)
lays them out:

- `SSDT-EC` vs `SSDT-EC-USBX` split at Skylake (gen 6); AMD and newer HEDT use the USBX table.
- `SSDT-IMEI` for Sandy Bridge + 7-series and Ivy Bridge + 6-series boards.
- `SSDT-AWAC` widened to all Coffee Lake and newer (desktop **and** laptop).
- `SSDT-PMC` refined: desktop gen 8–9, laptop gen 9, Z370 excluded.
- `SSDT-XOSI` for every Intel laptop, carrying the `_OSI → XOSI` ACPI rename it needs.
- `SSDT-RHUB` for Asus 400-series desktops and Ice Lake laptops.
- `SSDT-CPUR` for AMD B550 / A520 / AM5 (X570 and older AM4, and Threadripper, are excluded).
- `SSDT-UNC` and `SSDT-RTC0-RANGE-HEDT` for X79 / X99 / X299 HEDT (new `hedt_family()` detector; HEDT is flagged as partial support).

On the SSDTTime path, tables it can't generate headless (XOSI, IMEI, CPUR, RHUB, UNC, RTC0-RANGE) are still pulled from the prebuilt set.

## gui-v0.4.1

- **SSDT-GPIO auto-generation** for I2C-HID trackpads: decompile the supplied
  DSDT, find the touchpad's interrupt pin and GPIO controller from its `_CRS`,
  and compile a templated `SSDT-GPIO`. One clear candidate → built in;
  otherwise a precise TODO.
- **Broadcom Bluetooth**: `BrcmFirmwareData` + `BrcmPatchRAM3`
  (+ `BrcmBluetoothInjector` pre-Monterey) added whenever Broadcom Wi-Fi is detected.
- Hard limits are now loud: pre-Sandy-Bridge Intel is rejected up front;
  Wi-Fi with no macOS driver (Atheros/MediaTek) warns instead of silently
  building a machine with no Wi-Fi.

## gui-v0.4.0

- **Accent themes**: seven seeded palettes (Violet, Indigo, Emerald, Amber,
  Rose, Cyan, Slate) picked from the nav rail; theme mode + accent persist.
- **macOS and Linux builds**: the release workflow is now a
  Windows/macOS/Linux matrix; each release carries all three bundles.
- Setup gate is platform-aware (winget on Windows; brew/apt guidance elsewhere).

## gui-v0.3.0

- **Config tab** (`ocforge explain`): every hardware-driven `config.plist`
  decision, grouped, each with a reason and a Dortania link.
- On AMD, the live `AMD_Vanilla` patch list is fetched and shown per patch,
  including which one gets the core-count byte.

## gui-v0.2.1

- macOS recovery works when spawned without a console: `ocforge` fetches the
  current `macrecovery.py` from acidanthera master (fixes `WinError 6`) and
  writes `com.apple.recovery.boot` beside `EFI/`.

## gui-v0.2.0

- **First-run setup gate**: checks for Python 3.11+ and the `ocforge` CLI and
  offers to install whatever's missing before continuing; "Skip" → demo mode.
- **macOS recovery toggle** on the Forge tab (on by default); `--recovery` now
  works for folder builds, not just USB.

## gui-v0.1.1

- Fixed the demo-mode install hint — `ocforge` installs from the git repo,
  not PyPI.

## gui-v0.1.0

- First release: Material 3 Expressive Flutter desktop front-end (Detect /
  Plan / Forge tabs) driving the `ocforge` CLI, with a demo mode; Windows
  build workflow.
