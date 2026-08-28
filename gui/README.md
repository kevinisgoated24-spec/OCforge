# OCForge GUI

A Material 3 Expressive desktop front-end for the [`ocforge`](../) OpenCore EFI
builder — vivid dynamic-colour theme, fully-rounded components, springy page
transitions. Runs on **Windows, macOS and Linux**.

Four tabs, matching the CLI:

| tab | runs | shows |
|-----|------|-------|
| **Detect** | `ocforge probe --save …` | parsed CPU / GPU / NIC / board cards |
| **Plan**   | `ocforge plan --spec … [--macos N]` | target, SMBIOS, kext & SSDT counts, full plan text |
| **Config** | `ocforge explain --spec … [--macos N] --json` | every hardware-driven config.plist edit, grouped, each with a reason and a Dortania link; on AMD, the live AMD_Vanilla patch list too |
| **Forge**  | `ocforge build --spec … --out … [--recovery] [--dump-dsdt] [--debug]` | live build log, "open folder" and "validate this EFI" when done |
| **Editor** | `ocforge plist show/save`, `ocforge validate` | OCAT-style config.plist tree editor (bools / numbers / strings / hex data), save back, run ocvalidate |

## Look

The nav rail carries two controls, both persisted (a small `prefs.json` in the
platform config dir):

* **Theme** — cycles light / dark / follow-system.
* **Accent** — seven seeded palettes (Violet, Indigo, Emerald, Amber, Rose,
  Cyan, Slate); each reseeds the whole Material 3 scheme, including the app
  glyph.

## First-run setup

On first launch a **setup gate** checks for Python 3.11+ and the `ocforge` CLI.
If either is missing it offers to install them and then continues:

* **Python** — `winget install Python.Python.3.12` on Windows; on macOS / Linux
  it points you at `brew install python` / `sudo apt install python3` and waits
  for a relaunch.
* **ocforge** — `pip install --user` the repo zipball (no `git` needed).

"Skip" drops into **demo mode** with sample data, so the app is fully
explorable without the CLI.

Otherwise the GUI shells out to `ocforge` (tries `ocforge` on `PATH`, then
`py -3 -m ocforge`, `python -m ocforge`, `python3 -m ocforge`).

## macOS recovery

The Forge tab stages a macOS recovery image (`com.apple.recovery.boot` beside
`EFI/`) by default — toggle it off with the switch to skip the download.

## Install the CLI

```bash
pipx install "git+https://github.com/kevinisgoated24-spec/OCforge.git"
# or, from a clone:  pip install -e .
```

Python 3.11+ (and `git` only for the `pipx`/`git+` form).

## Build locally

```bash
cd gui
flutter create --platforms=windows,macos,linux --project-name ocforge_gui .   # one-time scaffold
flutter run -d windows        # or: -d macos / -d linux
```

Linux also needs the GTK dev headers:
`sudo apt install clang cmake ninja-build pkg-config libgtk-3-dev liblzma-dev`.

## Releases

`.github/workflows/gui-build.yml` builds all three desktops in a matrix on a
`gui-v*` tag (or manual dispatch): regenerates each platform scaffold, runs
`flutter build <target> --release`, packages, and attaches to one GitHub
Release —

| platform | asset |
|----------|-------|
| Windows  | `OCForge-GUI-windows-x64.zip` (unzip, run `ocforge_gui.exe`) |
| macOS    | `OCForge-GUI-macos.zip` (unzip `ocforge_gui.app`; unsigned — right-click → Open) |
| Linux    | `OCForge-GUI-linux-x64.tar.gz` (extract, run `./ocforge_gui`) |

```bash
git tag gui-v0.4.0 && git push origin gui-v0.4.0
```

Only `pubspec.yaml`, `analysis_options.yaml` and `lib/` are tracked; the
generated platform folders are recreated on every build.
