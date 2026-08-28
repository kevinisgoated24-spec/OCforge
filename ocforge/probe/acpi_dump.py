"""Get the target's ACPI tables so SSDTTime has something to work on.

Linux exposes them under ``/sys/firmware/acpi/tables`` with no root needed on
most distros. Windows and macOS have no clean read here — pass ``--dsdt`` or
let SSDTTime's own dumper handle it when ocforge runs on the target.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

_SYS_TABLES = Path("/sys/firmware/acpi/tables")


class DsdtUnavailable(RuntimeError):
    pass


def can_dump() -> bool:
    return sys.platform.startswith("linux") and _SYS_TABLES.is_dir()


def dump_tables(dest: Path) -> Path:
    """Copy DSDT + every SSDT into ``dest`` and return it. SSDTTime works best
    with the whole set, not DSDT alone."""
    if not can_dump():
        raise DsdtUnavailable("ACPI table dump is only automatic on Linux")
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for tbl in _SYS_TABLES.iterdir():
        if tbl.name == "DSDT" or tbl.name.startswith("SSDT"):
            data = tbl.read_bytes()
            (dest / f"{tbl.name}.aml").write_bytes(data)
            copied += 1
    if not (dest / "DSDT.aml").exists():
        raise DsdtUnavailable(f"no DSDT under {_SYS_TABLES}")
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
