"""Command-line entry point.

    ocforge probe   [--save FILE]        detect this machine, print / save it
    ocforge plan    [--spec FILE]        show macOS compatibility + the build plan
    ocforge build   [--spec FILE] ...    (wip) assemble a bootable EFI USB
"""

from __future__ import annotations

import argparse
import sys

from ocforge import __version__
from ocforge.model import Machine


def _load_machine(spec: str | None) -> Machine:
    if spec:
        from ocforge.spec import load

        return load(spec)
    from ocforge.probe import probe

    return probe()


def _fmt_gpu(g) -> str:
    kind = "dGPU" if g.discrete else "iGPU"
    pci = f"  [{g.pci}]" if not g.pci.empty else ""
    return f"{kind}: {g.name} ({g.vendor.value}){pci}"


def _print_machine(m: Machine) -> None:
    print(f"chassis   {m.chassis.value}")
    c = m.cpu
    fam = f" / {c.family}" if c.family else ""
    gen = f" (Intel gen {c.intel_gen})" if c.intel_gen else ""
    print(f"cpu       {c.brand or '?'}  [{c.vendor.value}{fam}{gen}]  {c.cores}c/{c.threads}t")
    for g in m.gpus:
        print(f"gpu       {_fmt_gpu(g)}")
    for n in m.net:
        tag = "wifi" if n.wireless else "eth "
        pci = f"  [{n.pci}]" if not n.pci.empty else ""
        print(f"{tag}      {n.name or '?'} ({n.vendor.value}){pci}")
    print(f"storage   nvme={'yes' if m.storage.has_nvme else 'no'}")
    if m.inputs.has_touchpad:
        print(f"touchpad  {m.inputs.touchpad_bus or 'unknown bus'}")
    if m.firmware.board_name:
        print(f"board     {m.firmware.board_vendor} {m.firmware.board_name}".strip())


def cmd_probe(args: argparse.Namespace) -> int:
    from ocforge.probe import probe

    m = probe()
    _print_machine(m)
    if args.save:
        from ocforge.spec import save

        save(m, args.save)
        print(f"\nsaved -> {args.save}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    from ocforge.catalog import macos

    m = _load_machine(args.spec)
    _print_machine(m)

    print("\nmacOS compatibility")
    for c in macos.evaluate(m):
        mark = "ok  " if c.supported else "no  "
        note = f"  — {c.note}" if c.note else ""
        print(f"  {mark}{c.release.name} ({c.release.major}){note}")

    target = macos.recommended(m)
    if target is None:
        print("\nno supported macOS release for this hardware.")
        return 1
    print(f"\nrecommended target: macOS {target.name} ({target.major})")

    if args.offline:
        return 0

    print("\nresolving downloads…")
    from ocforge.fetch.github import latest_asset
    from ocforge.fetch.http import DownloadError

    try:
        oc = latest_asset("acidanthera/OpenCorePkg", r"^OpenCore-[\d.]+-RELEASE\.zip$")
        print(f"  OpenCore   {oc.release_tag}  {oc.name}  ({oc.size / 1_048_576:.1f} MB)")
        lilu = latest_asset("acidanthera/Lilu", r"^Lilu-[\d.]+-RELEASE\.zip$")
        print(f"  Lilu       {lilu.release_tag}  {lilu.name}")
    except (OSError, LookupError, DownloadError) as exc:  # offline / rate-limited — plan still stands
        print(f"  (skipped: {exc})")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    print("build: the fetch → assemble → write-USB pipeline isn't implemented yet.")
    print("`ocforge plan` covers detection + target selection today.")
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ocforge", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"ocforge {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("probe", help="detect this machine")
    pp.add_argument("--save", metavar="FILE", help="write the detected machine spec to FILE")
    pp.set_defaults(func=cmd_probe)

    pl = sub.add_parser("plan", help="show compatibility + build plan")
    pl.add_argument("--spec", metavar="FILE", help="load a machine spec instead of probing")
    pl.add_argument("--offline", action="store_true", help="skip resolving downloads")
    pl.set_defaults(func=cmd_plan)

    pb = sub.add_parser("build", help="(wip) assemble a bootable EFI USB")
    pb.add_argument("--spec", metavar="FILE")
    pb.set_defaults(func=cmd_build)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
