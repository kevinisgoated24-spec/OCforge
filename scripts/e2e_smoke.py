"""End-to-end build smoke test: real downloads, real EFI folders, real ocvalidate.

``tests/`` proves the *decision logic* is right (kext/SSDT selection, config
assembly) with the network mocked out -- it can't catch a kext maintainer
renaming their release asset, an API response shape changing, or OpenCore's
own zip layout shifting, because it never actually asks the internet for
anything. This script does exactly that: it drives ocforge's real CLI
entry point against a few representative machines, downloads everything a
real user's build would, and runs the real `ocvalidate` against the result.

Deliberately outside pytest -- this is slow (real network) and not something
that should run on every local `pytest` invocation. Wired into CI as its own
job (see .github/workflows/e2e-build.yml): on push to master, and on a daily
schedule so third-party drift gets caught even on a day nobody pushed.

Run locally with: python scripts/e2e_smoke.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocforge import spec
from ocforge.model import (
    Chassis,
    Cpu,
    Firmware,
    Gpu,
    Machine,
    NetIf,
    PciId,
    Storage,
    Vendor,
)


def _amd_desktop() -> Machine:
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand="AMD Ryzen 5 5600X", vendor=Vendor.AMD, family="Zen 3", cores=6, threads=12),
        dgpu=Gpu(name="RX 6800", vendor=Vendor.AMD, pci=PciId("1002", "73bf"), discrete=True),
        net=[NetIf(name="RTL8125", vendor=Vendor.REALTEK, pci=PciId("10ec", "8125"))],
        storage=Storage(has_nvme=True),
    )


def _intel_laptop() -> Machine:
    return Machine(
        chassis=Chassis.LAPTOP,
        cpu=Cpu(brand="i7-8650U", vendor=Vendor.INTEL, family="Coffee Lake", intel_gen=8,
                cores=4, threads=8, flags=frozenset({"avx2"})),
        igpu=Gpu(name="UHD 620", vendor=Vendor.INTEL, pci=PciId("8086", "5917")),
        net=[NetIf(name="I219-V", vendor=Vendor.INTEL, pci=PciId("8086", "15d8")),
             NetIf(name="Intel 8265", vendor=Vendor.INTEL, wireless=True)],
        storage=Storage(has_nvme=True),
    )


def _hedt_x99() -> Machine:
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand="Intel Core i7-6850K", vendor=Vendor.INTEL, family="Broadwell-E",
                intel_gen=6, cores=6, threads=12, flags=frozenset({"avx2"})),
        dgpu=Gpu(name="RX 580", vendor=Vendor.AMD, pci=PciId("1002", "67df"), discrete=True),
        firmware=Firmware(board_vendor="ASRock", board_name="X99 Taichi"),
        storage=Storage(has_nvme=True),
    )


_MACHINES = {
    "amd-desktop": _amd_desktop,
    "intel-laptop": _intel_laptop,
    "hedt-x99": _hedt_x99,
}


def _run(args: list[str]) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(args)}", flush=True)
    r = subprocess.run(args, capture_output=True, text=True, check=False)
    if r.stdout:
        print(r.stdout)
    if r.stderr:
        print(r.stderr, file=sys.stderr)
    return r


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="ocforge-e2e-") as tmp:
        work = Path(tmp)
        for name, make_machine in _MACHINES.items():
            print(f"\n=== {name} ===", flush=True)
            spec_path = work / f"{name}.json"
            spec.save(make_machine(), spec_path)
            out_dir = work / name

            build = _run([
                sys.executable, "-m", "ocforge", "build",
                "--spec", str(spec_path), "--out", str(out_dir),
                "--work", str(work / f"{name}-work"),
                # These machines are all real, supported combinations today,
                # but forcing through anyway means a future catalog change
                # that makes one newly "unsupported" fails loudly as a real
                # ocvalidate/build problem, not a silent non-interactive
                # sys.exit(3/4) that reads as a false negative here.
                "--force-unsupported-gpu", "--force-unsupported-os",
            ])
            if build.returncode != 0:
                failures.append(f"{name}: build exited {build.returncode}")
                continue

            validate = _run([sys.executable, "-m", "ocforge", "validate", "--efi", str(out_dir)])
            if validate.returncode != 0:
                failures.append(f"{name}: ocvalidate exited {validate.returncode}")

    if failures:
        print("\nFAILURES:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"\nAll {len(_MACHINES)} machines built and validated cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
