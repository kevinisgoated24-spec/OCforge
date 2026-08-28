# Changelog

Notable changes per release. Releases are tagged `gui-vX.Y.Z` and carry the
desktop GUI bundles; each entry also covers the CLI changes that shipped with it.

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
