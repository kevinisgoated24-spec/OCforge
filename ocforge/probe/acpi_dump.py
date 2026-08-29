"""Get the target's ACPI tables so SSDTTime has something to work on.

Linux exposes them under ``/sys/firmware/acpi/tables`` with no root needed on
most distros — read directly, no extra tool needed. Windows has no clean read
either, but the ACPICA project's own ``acpidump.exe`` (fetched separately —
see ``fetch/acpidump.py``; SSDTTime's own dumper only *checks* for this file
locally, it never downloads it, so ocforge can't just reuse the SSDTTime tree
here) does exactly this — see :func:`dump_tables`'s ``acpidump_exe``.

macOS has no automatic path at all, from ocforge or from SSDTTime itself (its
own ``dsdt.py`` only implements Windows and Linux) — pass ``--dsdt`` with a
folder of tables dumped some other way.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_SYS_TABLES = Path("/sys/firmware/acpi/tables")


class DsdtUnavailable(RuntimeError):
    pass


def can_dump() -> bool:
    """True if this host can dump its own ACPI tables with nothing beyond
    what's already local — Linux only. Windows *can* dump too, but needs
    ``acpidump.exe`` fetched first (see ``fetch/acpidump.py``); callers that
    already have it should just try :func:`dump_tables` with
    ``acpidump_exe`` set and catch :class:`DsdtUnavailable`."""
    return sys.platform.startswith("linux") and _SYS_TABLES.is_dir()


def dump_tables(dest: Path, *, acpidump_exe: Path | None = None) -> Path:
    """Copy DSDT + every SSDT into ``dest`` and return it. SSDTTime works best
    with the whole set, not DSDT alone.

    ``acpidump_exe`` is required on Windows (see ``fetch.acpidump.fetch``)
    and ignored elsewhere."""
    if sys.platform.startswith("linux"):
        return _dump_linux(dest)
    if sys.platform == "win32":
        return _dump_windows(dest, acpidump_exe)
    raise DsdtUnavailable(
        "ACPI table dump has no automatic path on macOS — pass --dsdt with "
        "a folder of tables dumped some other way"
    )


def _dump_linux(dest: Path) -> Path:
    if not _SYS_TABLES.is_dir():
        raise DsdtUnavailable(f"no {_SYS_TABLES} on this host")
    dest.mkdir(parents=True, exist_ok=True)
    for tbl in _SYS_TABLES.iterdir():
        if tbl.name == "DSDT" or tbl.name.startswith("SSDT"):
            data = tbl.read_bytes()
            (dest / f"{tbl.name}.aml").write_bytes(data)
    if not (dest / "DSDT.aml").exists():
        raise DsdtUnavailable(f"no DSDT under {_SYS_TABLES}")
    return dest


def _dump_windows(dest: Path, acpidump_exe: Path | None) -> Path:
    if acpidump_exe is None or not acpidump_exe.is_file():
        raise DsdtUnavailable("Windows ACPI dump needs acpidump.exe (see fetch.acpidump.fetch)")
    dest.mkdir(parents=True, exist_ok=True)

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run([str(acpidump_exe), *args], cwd=str(dest), capture_output=True,
                              text=True, timeout=60, check=False)

    p = run("-b")
    if p.returncode != 0:
        raise DsdtUnavailable(f"acpidump.exe -b failed: {(p.stdout + p.stderr)[-500:]}")
    if not any(f.name.lower().startswith("dsdt.") for f in dest.iterdir()):
        # Some OEM firmware needs the DSDT dumped by signature explicitly —
        # SSDTTime's own dumper has this same fallback.
        p = run("-b", "-n", "DSDT")
        if p.returncode != 0:
            raise DsdtUnavailable(f"acpidump.exe -b -n DSDT failed: {(p.stdout + p.stderr)[-500:]}")

    # acpidump -b dumps *every* table (FACP, APIC, MCFG, …), not just what we
    # want. Normalize DSDT/SSDT names the way SSDTTime's own dumper does
    # (UPPERCASE table name, .aml not the default .dat) and drop the rest —
    # matching what the Linux path hands back.
    for f in list(dest.iterdir()):
        name = f.name.upper()
        if name.endswith(".DAT"):
            name = name[:-4] + ".aml"
        if not (name == "DSDT.aml" or name.startswith("SSDT")):
            f.unlink()
            continue
        if name != f.name:
            f.rename(dest / name)

    if not (dest / "DSDT.aml").exists():
        raise DsdtUnavailable("acpidump.exe ran but produced no DSDT")
    return dest


def stage_supplied(dsdt_path: Path, dest: Path) -> Path:
    """Copy a user-supplied DSDT (or a folder of tables) into ``dest``."""
    dest.mkdir(parents=True, exist_ok=True)
    src = Path(dsdt_path)
    if src.is_dir():
        for f in src.iterdir():
            if f.suffix.lower() in (".aml", ".dsl", ".dat") or f.name in ("DSDT", "SSDT"):
                shutil.copy2(f, dest / f.name)
    else:
        shutil.copy2(src, dest / "DSDT.aml")
    return dest
