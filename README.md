# ocforge

Build a bootable OpenCore EFI for a machine you can describe.

Point it at the machine (or a saved spec of one), and it works out which macOS
releases are viable, what OpenCore + kexts + ACPI it needs, and — eventually —
writes the whole thing to a USB. Runs from Linux, Windows, or macOS as the host.

> Early. `probe` and `plan` work today; the fetch → assemble → write-USB
> pipeline is being built.

## Install

```bash
pipx install .            # or: pip install -e .[dev]
```

Python 3.11+. No runtime dependencies.

## Use

```bash
# detect this machine
ocforge probe

# save the spec, then plan from another computer
ocforge probe --save my-pc.json
ocforge plan --spec my-pc.json
```

`plan` prints the detected hardware, a macOS-compatibility verdict per release,
the recommended target, and (online) the OpenCore / kext versions it would pull.

## Layout

| package            | does |
|-------------------|------|
| `ocforge.model`    | the `Machine` value object everything else reads |
| `ocforge.probe`    | per-OS hardware detection → `Machine` |
| `ocforge.spec`     | `Machine` ⇄ JSON, for off-target planning |
| `ocforge.catalog`  | macOS-version compatibility rules (kexts/ACPI next) |
| `ocforge.fetch`    | GitHub release resolution + resumable downloads |
| `ocforge.build`    | *(next)* config.plist / SMBIOS / ACPI assembly |
| `ocforge.media`    | *(next)* USB enumerate / format / write |

## License

MIT — see [LICENSE](LICENSE).
