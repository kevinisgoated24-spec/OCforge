# OCForge GUI

A Material 3 Expressive desktop front-end for the [`ocforge`](../) OpenCore EFI
builder — vivid dynamic-colour theme, fully-rounded components, springy page
transitions.

Three steps, matching the CLI:

| tab | runs | shows |
|-----|------|-------|
| **Detect** | `ocforge probe --save …` | parsed CPU / GPU / NIC / board cards |
| **Plan**   | `ocforge plan --spec … [--macos N]` | target, SMBIOS, kext & SSDT counts, full plan text |
| **Forge**  | `ocforge build --spec … --out … [--dump-dsdt] [--debug]` | live build log, "open folder" when done |

The GUI shells out to the `ocforge` Python CLI (tries `ocforge` on `PATH`, then
`py -3 -m ocforge`, `python -m ocforge`, `python3 -m ocforge`). If none answers,
it runs in **demo mode** with sample data so the packaged `.exe` is still fully
explorable.

## Build locally

```bash
cd gui
flutter create --platforms=windows --project-name ocforge_gui .   # one-time: platform scaffold
flutter run -d windows
```

## Windows .exe

Pushed by CI — see `.github/workflows/gui-windows.yml`. It regenerates the
`windows/` scaffold, runs `flutter build windows --release`, zips
`build/windows/x64/runner/Release/`, and (on a `gui-v*` tag) attaches the zip to
a GitHub Release.

```bash
git tag gui-v0.1.0 && git push origin gui-v0.1.0
```

Only `pubspec.yaml`, `analysis_options.yaml` and `lib/` are tracked; the
generated platform folders are recreated on every build.
