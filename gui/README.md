# OCForge GUI

A Material 3 Expressive desktop front-end for the [`ocforge`](../) OpenCore EFI
builder — vivid dynamic-colour theme, fully-rounded components, springy page
transitions. Runs on **Windows, macOS and Linux**.

Five tabs:

| tab | runs | shows |
|-----|------|-------|
| **Detect** | `ocforge probe --save …` | parsed CPU / GPU / NIC / board cards |
| **Plan**   | `ocforge plan --spec … [--macos N]` | target, SMBIOS, kext & SSDT counts, full plan text |
| **Config** | `ocforge explain --spec … [--macos N] --json` | every hardware-driven config.plist edit, grouped, each with a reason and a Dortania link; on AMD, the live AMD_Vanilla patch list too |
| **Forge**  | `ocforge build --spec … --out … [--recovery] [--dump-dsdt] [--debug]` | live build log, "open folder" and "validate this EFI" when done |
| **Editor** | `ocforge plist show/save`, `ocforge validate` | OCAT-style config.plist tree editor (bools / numbers / strings / hex data), save back, run ocvalidate |

Plus a sixth, **Assistant**, that only shows up in a local `flutter run` debug
build — see below.

### Assistant (dev-only)

Gated behind `kDebugMode` (`if (kDebugMode) ...` around both the nav
destination and the page in `app.dart`) — Flutter sets that `false` for
every `flutter build --release`, which is what CI packages for every
download, so this tab is compiled out of shipped builds entirely, not just
hidden behind a flag someone could flip. Run `flutter run -d <platform>`
from source to see it.

A plain question-and-answer helper, not a running agent — each message is one
independent request, using the current machine spec and plan text as context.
It has no tool access: it can't run commands, edit files, or touch your build,
only suggest what to try. Two backends, auto-detected on open (`assistant.dart`):

1. **A local Claude Code CLI**, if `claude` is on `PATH` — no key needed,
   billed to whatever account you're already signed into there. Verified
   against a real `claude -p "<prompt>"` call (prompt as a plain argument,
   plain stdout, clean exit code).
2. **The Anthropic API directly**, if no CLI is found — paste a key into the
   gear icon on the Assistant tab. It's saved in the same plaintext
   `prefs.json` as your theme/accent; this app has no OS-keychain
   integration (no native plugins at all, by design), so treat that file
   accordingly if you use this path.

The Forge tab's **"Offline installer (UnPlugged)"** toggle swaps in
`ocforge offline-installer` instead of `build` — downloads the full macOS
installer + stages [corpnewt/UnPlugged](https://github.com/corpnewt/UnPlugged)
next to the EFI, for installing without the target machine touching the
internet. Big and slow (Apple's full installer is 10+ GB); see the main
[README's "Offline installer" section](../README.md#offline-installer) for
the two-partition USB layout it expects.

The bug icon at the bottom of the nav rail is **OCforgeReporter**: it opens a
GitHub "New issue" with your ocforge version and hardware already filled in —
no bot, no server, no shared credential; you review and submit it yourself.
Same as `ocforge report` on the CLI.

## Look

The nav rail carries two controls, both persisted (a small `prefs.json` in the
platform config dir):

* **Theme** — cycles light / dark / follow-system.
* **Accent** — seven seeded palettes (Violet, Indigo, Emerald, Amber, Rose,
  Cyan, Slate); each reseeds the whole Material 3 scheme, including the app
  glyph.

## Checking for updates

Every launch, the app quietly checks GitHub for a newer `gui-v*` release
than the one you're running. If one exists, a banner appears with an
**Update** button. Confirming it updates *both* halves in one go:

1. **CLI** — `pip install --upgrade` against the repo, same mechanism as
   the setup screen's "Update & continue" (`cli.dart`'s `installOcforge`).
   A failure here is logged but doesn't block the GUI half — the two are
   independent.
2. **GUI** — downloads this platform's release asset, extracts it into a
   temp dir, and hands off to a small platform-native relauncher script
   (PowerShell on Windows, `sh` on macOS/Linux) launched detached. The app
   then exits; the relauncher waits for that exit, renames the current
   install dir aside, moves the new one into its place, and starts the new
   executable — restoring the old install instead if the swap doesn't fully
   complete, so a failed update never leaves the app unable to launch
   (`self_update.dart`).

A **running `.exe` can't overwrite itself** — that's exactly why this needs
the detached relauncher-plus-exit dance rather than doing the swap in
process. If the self-update can't complete for any reason (no `unzip`/`tar`
found, a permissions error, offline mid-download, …), it falls back to just
opening the release page, same as the old behaviour. The version check
itself still fails silently (offline, rate-limited, etc.) and never blocks
startup either way.

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
