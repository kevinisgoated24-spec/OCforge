# Changelog

Notable changes per release. Releases are tagged `gui-vX.Y.Z` and carry the
desktop GUI bundles; each entry also covers the CLI changes that shipped with it.

## gui-v0.4.26

- **The GUI now checks for its own updates.** On launch it quietly checks
  GitHub for a newer `gui-v*` release; if one exists, a banner offers a
  **Download** button that opens that release's page. It does *not*
  download or replace the running app itself — self-updating a native
  desktop app safely (the running `.exe` can't overwrite itself on
  Windows, a half-swapped install is worse than a missed update) is a much
  bigger, riskier feature than this. The existing **"Update & continue"**
  on the setup screen is unrelated — that updates the `ocforge` CLI, not
  the GUI app.

## gui-v0.4.25

- **Sandy Bridge through Kaby Lake desktop: cross-checked against
  Dortania's own guide for each generation, several real bugs fixed.**
  Every Intel desktop gen 2-7 was previously falling back to a single
  generic SMBIOS/quirk profile meant for Coffee Lake — genuinely wrong for
  that much older hardware. Fixed:
  - **SMBIOS is now per-generation and per-target**, bumped to a newer
    sibling once a generation's own model is dropped for a later macOS
    (Skylake's iMac17,1 → Kaby Lake's iMac18,1 for Ventura+), or to a
    dGPU-driven MacPro6,1 once a generation's iGPU driver support ends
    entirely (Ivy Bridge past Big Sur; Sandy Bridge everywhere ocforge
    targets). Also fixed a regression-in-place: Coffee Lake Refresh (9th
    gen) with a dGPU was getting Comet Lake's iMac20,1 instead of Coffee
    Lake's own iMac19,1.
  - **`AppleCpuPmCfgLock` instead of `AppleXcpmCfgLock` before Haswell** —
    XCPM doesn't exist that far back; using its CFG-Lock quirk on Sandy/Ivy
    Bridge did nothing, so a board that can't disable CFG-Lock in BIOS
    would panic on boot regardless.
  - **`IgnoreInvalidFlexRatio`** was hardcoded off; now on for every
    pre-Skylake system, per Dortania.
  - **`AAPL,ig-platform-id` DeviceProperties extended to Ivy
    Bridge/Haswell/Broadwell** (previously only Skylake+ got any iGPU
    DeviceProperties at all) — plus `framebuffer-fbmem`, which Haswell/
    Broadwell/Skylake specifically need alongside the stolen-mem fix.
    Also fixed Skylake's own headless (dGPU-driven) platform-id, which was
    wrong (had Kaby Lake's value instead of Skylake's).
  - **Sandy/Ivy Bridge**: the stock `CpuPm`/`Cpu0Ist` ACPI tables are now
    dropped (`ACPI → Delete`), the other half of Dortania's fix for XCPM
    panicking on those CPUs. The replacement, SSDT-PM, needs Pike's
    separate `ssdtPRGen.sh` and isn't automated — flagged as a manual step
    instead (same treatment as the existing HEDT caveat).
  - Verified end-to-end: a real Ivy Bridge build (`i5-3570`, targeting Big
    Sur) produced a `config.plist` that passes `ocvalidate` clean, with
    every value above confirmed correct in the actual output, not just
    tested in isolation.

## gui-v0.4.24

- **Fixed stale wording in `ocforge plan`'s SSDT-GPIO note.** It still said
  "auto-generated ... when you pass --dsdt / --dump-dsdt" — true before
  gui-v0.4.21, misleading since (Linux/Windows laptops with an I2C-HID
  trackpad auto-generate it with no flag needed now). Reworded to say so.

## gui-v0.4.23

- **Fixed missing I2C-HID trackpad detection on Windows** — a real Device
  Manager check on an actual affected laptop (a Synaptics I2C-HID trackpad
  showing plainly as its own "I2C HID Device" entry) confirmed the probe's
  `PNP0C50`/`ACPI0C50` match only looked at `Win32_PnPEntity.HardwareID`.
  For a device Windows shows under a *generic* name (no vendor-specific
  driver installed) — exactly what "I2C HID Device" means — that class ID
  usually only appears in the separate `CompatibleID` property, which
  wasn't checked at all. The probe now checks both. This is what was
  silently blocking the gui-v0.4.21/0.4.22 SSDT-GPIO auto-dump on some
  Windows laptops — `has_touchpad`/`touchpad_bus` came back empty even
  though a real I2C-HID device existed.

## gui-v0.4.22

- **`--dump-dsdt` (and the auto SSDT-GPIO from gui-v0.4.21) now works on
  Windows too**, not just Linux. Turns out SSDTTime's own dumper only
  *checks* for a local `acpidump.exe` next to itself — it never fetches
  one, confirmed by actually pulling the SSDTTime tree and finding it
  missing. ocforge now fetches the real thing straight from its upstream,
  the [ACPICA project](https://github.com/open-acpica/acpica) (the same
  repo SSDTTime's own code already points its Windows `iasl` download at),
  and runs it the same way SSDTTime would have. Verified end-to-end against
  this machine's real firmware — a genuine 47&nbsp;KB DSDT plus 10 SSDTs,
  correct ACPI headers throughout.
- **macOS still has no automatic path**, and won't — this isn't ocforge
  cutting a corner, SSDTTime itself has never implemented one either (its
  `dsdt.py` only branches on Windows and Linux). Reading a machine's own
  live ACPI tables needs macOS already booted there, which is the
  chicken-and-egg problem a hackintosh-prep tool exists to get you past in
  the first place. `--dsdt` with a folder dumped some other way still works
  fine on macOS, same as before.

## gui-v0.4.21

- **Unsupported-GPU builds now ask instead of just refusing.** `gui-v0.4.20`
  made `ocforge plan`/`build` hard-fail when there's no supported display
  path; that was too blunt for the rare case someone really does want to
  proceed anyway (an eGPU, a card arriving later, testing). Now it's a
  prompt — *"Sorry, this build is unsupported. Would you still like to
  continue?"* — `y` proceeds with a loud warning attached to the plan,
  anything else backs out. `--macos N` still doesn't skip the question. New
  `--force-unsupported-gpu` flag jumps straight to yes (also fixed a crash:
  an EOFError from `input()` when a shell reports a tty that isn't really
  attached to anything no longer produces a raw traceback). The GUI shows
  its own "Continue anyway" dialog for the same case and retries with the
  flag on Continue.
- **Laptops with an I2C-HID trackpad now auto-generate SSDT-GPIO** on a
  Linux host that can dump its own ACPI tables — no `--dsdt`/`--dump-dsdt`
  needed. Without a DSDT to read, SSDT-GPIO silently never got built before
  (just an easy-to-miss manual-TODO note); ocforge now dumps automatically
  for exactly this case, same as if you'd passed `--dump-dsdt` yourself.

## gui-v0.4.20

- **Unsupported GPU-only machines are now refused, not silently built.**
  NVIDIA (Maxwell and newer) has no macOS driver at all — with an Intel
  iGPU or an AMD dGPU also present, ocforge already disabled it
  (`nv_disable=1`) and the other GPU carried the display; that part still
  works and now also gets a clear warning explaining the NVIDIA card is
  inert in macOS. What was missing: a machine with **no iGPU** and only an
  NVIDIA (or no) dGPU has nothing to show a display with once macOS hands
  off from the boot picker — `ocforge plan`/`build`/`offline-installer` now
  reject that case outright with a clear reason, instead of handing over an
  EFI that boots to a black screen. Applies even with `--macos N` forced.
  This also fixed a pre-existing gap where an AMD build with no dGPU at all
  was wrongly marked "supported" on Big Sur/Monterey/Ventura (only
  Sonoma+'s Metal requirement was checked before).

## gui-v0.4.19

- **Offline installer, via [corpnewt/UnPlugged](https://github.com/corpnewt/UnPlugged).**
  New `ocforge offline-installer` (CLI) / "Offline installer (UnPlugged)"
  toggle on the Forge tab (GUI): downloads the full macOS installer with
  [gibMacOS](https://github.com/corpnewt/gibMacOS) and stages
  `InstallAssistant.pkg` + `UnPlugged.command` next to your EFI, laid out
  for the FAT32+ExFAT USB split UnPlugged expects — for installing macOS
  where the target machine shouldn't touch the internet mid-install.
  `--usb DEVICE` partitions and writes both partitions for you (needs
  `exfatprogs` on Linux). On Sonoma+ the boot environment automatically
  uses an older (Monterey) BaseSystem, since Sonoma+ Recovery can't mount
  FAT32/ExFAT itself — ocforge handles that split and says so. Actually
  running the installer is still done by hand in Recovery Terminal
  (`./UnPlugged.command`) — see the README for why.

## gui-v0.4.18

- **Fixed the GUI's first-run setup on Debian/Ubuntu (PEP 668).** Newer
  Debian/Ubuntu ship a "externally managed" system Python that refuses
  `pip install --user` outside a venv — the setup gate's ocforge-CLI
  install would fail with that error and stop there. It now retries with
  `--break-system-packages` when that specific error is seen. (Reported via
  OCforgeReporter/Discord, our first bug filed through it — thanks
  @gam1ngn0t.)

## gui-v0.4.17

- **Added Support For Offline Installer** New Option To Make A Offline Installer With gibMacOS Inside Of OCForge How Does It Work?
First Your Going To Selected What Build Of MacOS Your Going To Get OCForge Will Installed It Get The installassistant.pkg Place It Inside Of The USB With Unplugged (tuto will show on the guide that is in progress)

  (This was a plan, never actually built/tagged. It shipped for real in
  **gui-v0.4.19** below.)

## gui-v0.4.16

- **OCforgeReporter.** `ocforge report` (CLI) and a bug icon in the GUI's nav
  rail open a GitHub "New issue" pre-filled with your ocforge version and
  detected hardware, using the new bug-report issue form
  (`.github/ISSUE_TEMPLATE/bug_report.yml`). No bot account, no server, no
  shared write-access credential — the fields are filled client-side and you
  submit the issue yourself under your own GitHub account.

## gui-v0.4.15

- The GUI now **cleans up the temp spec file** it writes on "Detect this PC"
  (`%TEMP%/ocforge_spec_*.json`) — deleted when you detect/open another spec
  and on app exit. A spec you opened from disk is never touched.

## gui-v0.4.14

- **`DevirtualiseMmio` is now ON for every Coffee/Comet Lake desktop**, not
  just Z390 — matches the Dortania Coffee Lake Booter table and fixes early
  MMIO / slide-allocation panics.
- **New `--legacy-mmap`** (CLI flag + Forge toggle): swaps
  `RebuildAppleMemoryMap` for `EnableWriteUnprotector` (+ `SyncRuntimePermissions`
  off), the fallback for OEM firmware (Dell / HP / Lenovo) that lacks the MAT
  table and panics early otherwise. `ocforge plan` warns OEM boxes to try it.

## gui-v0.4.13

- **Coffee/Comet Lake desktop iGPU: added `framebuffer-patch-enable` +
  `framebuffer-stolenmem` (0x3001 / 19 MB)** when the iGPU drives the display,
  per the Dortania Coffee Lake DeviceProperties section — the fix for OEM
  boards (Dell/HP/Lenovo) that lock DVMT. A non-standard CFL desktop iGPU
  device-id is also faked to 0x3E9B.

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
