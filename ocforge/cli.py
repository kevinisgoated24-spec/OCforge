"""Command-line entry point.

    ocforge probe   [--save FILE]                  detect this machine
    ocforge plan    [--spec FILE] [--macos N]      compatibility + full build plan
    ocforge usb                                    list writable USB disks
    ocforge build   [--spec FILE] [--macos N] \\
                    [--out DIR | --usb DEV] [--recovery]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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


def _print_plan(p) -> None:
    print(f"\ntarget    macOS {p.target.name} ({p.target.major})  darwin {p.target.darwin}")
    print(f"smbios    {p.smbios_model}")
    print(f"boot-args {' '.join(p.boot_args)}")
    print(f"\nkexts ({len(p.kexts)})")
    for s in p.kexts:
        krange = ""
        if s.min_darwin or s.max_darwin:
            krange = f"  [{s.min_darwin or ''}..{s.max_darwin or ''}]"
        note = f"  — {s.comment}" if s.comment else ""
        print(f"  {s.kext.name}{krange}{note}")
    print(f"\nSSDTs ({len(p.ssdts)})")
    for s in p.ssdts:
        print(f"  {s.name}  — {s.reason}")
    if p.manual_acpi:
        print("\nmanual ACPI (needs the target's DSDT)")
        for t in p.manual_acpi:
            print(f"  ! {t}")
    if p.warnings:
        print("\nwarnings")
        for w in p.warnings:
            print(f"  ! {w}")


# --- commands --------------------------------------------------------------


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
    from ocforge.build.plan import make

    m = _load_machine(args.spec)
    _print_machine(m)
    try:
        plan = make(m, target_major=args.macos)
    except ValueError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    _print_plan(plan)
    return 0


def cmd_usb(_args: argparse.Namespace) -> int:
    from ocforge.media.devices import list_usb

    disks = list_usb()
    if not disks:
        print("no removable USB disks found")
        return 1
    for d in disks:
        print(d)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    from ocforge.build.pipeline import build_efi, build_usb
    from ocforge.build.plan import make

    if not args.out and not args.usb:
        print("give --out DIR (assemble an EFI folder) or --usb DEVICE (write a USB)", file=sys.stderr)
        return 2

    m = _load_machine(args.spec)
    try:
        plan = make(m, target_major=args.macos)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    _print_machine(m)
    _print_plan(plan)
    print()

    work = Path(args.work or "ocforge-work").resolve()

    if args.usb:
        if input(f"\nERASE {args.usb} and write a bootable USB? [y/N] ").strip().lower() != "y":
            return 130
        rec = plan.target.major if args.recovery else None
        report = build_usb(plan, work, args.usb, recovery_major=rec, log=print)
    else:
        report = build_efi(plan, work, Path(args.out).resolve(), log=print, debug=args.debug)
        print(f"\nEFI folder: {report.efi_dir}")

    _print_build_report(report)
    return 0 if report.ok else 1


def _print_build_report(r) -> None:
    if r.used_placeholder_smbios:
        print("\n! macserial unavailable — SMBIOS serial/MLB are PLACEHOLDERS, not usable. "
              "Re-run where the OpenCore Utilities are present, or fill them by hand.")
    if r.kext_failures:
        print("\nkexts that did not download:")
        for f in r.kext_failures:
            print(f"  ! {f}")
    if r.ssdt_failures:
        print("\nSSDTs that did not download:")
        for f in r.ssdt_failures:
            print(f"  ! {f}")
    if r.manual_todo:
        print("\nstill to do by hand:")
        for t in r.manual_todo:
            print(f"  ! {t}")
    if r.ok:
        print("\nrun ocvalidate against the config before booting.")


# --- parser --------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ocforge", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"ocforge {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("probe", help="detect this machine")
    pp.add_argument("--save", metavar="FILE")
    pp.set_defaults(func=cmd_probe)

    pl = sub.add_parser("plan", help="compatibility + build plan")
    pl.add_argument("--spec", metavar="FILE")
    pl.add_argument("--macos", type=int, metavar="N", help="force a macOS major (e.g. 14)")
    pl.set_defaults(func=cmd_plan)

    pu = sub.add_parser("usb", help="list writable USB disks")
    pu.set_defaults(func=cmd_usb)

    pb = sub.add_parser("build", help="assemble an EFI folder or write a bootable USB")
    pb.add_argument("--spec", metavar="FILE")
    pb.add_argument("--macos", type=int, metavar="N")
    pb.add_argument("--out", metavar="DIR", help="write EFI/ into this folder")
    pb.add_argument("--usb", metavar="DEVICE", help="ERASE this disk and write a bootable USB")
    pb.add_argument("--recovery", action="store_true", help="also download + stage macOS recovery (USB only)")
    pb.add_argument("--work", metavar="DIR", help="download/scratch dir (default: ./ocforge-work)")
    pb.add_argument("--debug", action="store_true", help="use the OpenCore DEBUG build")
    pb.set_defaults(func=cmd_build)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except (RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
