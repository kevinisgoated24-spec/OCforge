"""Get the target's ACPI tables so SSDTTime has something to work on.

Linux exposes them under ``/sys/firmware/acpi/tables`` with no root needed on
most distros — read directly, no extra tool needed.

Windows has a driver-free, admin-free native path since Vista:
``GetSystemFirmwareTable`` / ``EnumSystemFirmwareTables`` with the ``'ACPI'``
provider hand back raw table bytes straight from the OS. SSDTTime's own
``Scripts/dsdt.py`` never uses this — it shells out to ``acpidump.exe`` and
only *checks* for that file locally, never downloads it — so ocforge does the
native call itself (:func:`_dump_windows_native`). The one catch is that the
Win32 API returns only the *first* table for a repeated signature, so a
machine with several SSDTs yields DSDT + one SSDT. That's enough for the
DSDT-driven renames/GPRW/AWAC work; for the complete SSDT set, ocforge falls
back to the ACPICA project's ``acpidump.exe`` (fetched by ``fetch/acpidump.py``).

macOS (Intel) exposes the tables in the IORegistry: the
``AppleACPIPlatformExpert`` node carries an ``ACPI Tables`` dictionary of raw
table data — the same source MaciASL's "New from ACPI" reads. ``ioreg -a``
hands it back as a plist, no root needed (:func:`_dump_darwin`). SSDTTime's
own ``dsdt.py`` has no macOS path, so this is ocforge's. Two caveats: on a
Hackintosh these are the tables *as OpenCore delivered them* (DSDT renames
applied, its own SSDTs injected) — see :func:`opencore_booted`; and Apple
Silicon has no ACPI at all, so :func:`can_dump` is simply False there.
"""

from __future__ import annotations

import ctypes
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

_SYS_TABLES = Path("/sys/firmware/acpi/tables")

# 'ACPI' as the DWORD Windows' firmware-table APIs expect (MSDN: 0x41435049).
_ACPI_PROVIDER = 0x41435049


class DsdtUnavailable(RuntimeError):
    pass


def can_dump() -> bool:
    """True if this host can dump its own ACPI tables with nothing beyond
    what's already local. Linux reads ``/sys/firmware/acpi/tables``; Windows
    uses the native ``GetSystemFirmwareTable`` call (no ``acpidump.exe``
    download needed just to get a DSDT); Intel macOS reads the IORegistry."""
    if sys.platform == "win32":
        return True
    if sys.platform == "darwin":
        return b"DSDT" in _darwin_tables()
    return sys.platform.startswith("linux") and _SYS_TABLES.is_dir()


# --- macOS: IORegistry ---------------------------------------------------------

# OpenCore publishes its version under its own NVRAM GUID; present => the
# running tables went through OpenCore's ACPI patching first.
_OC_NVRAM_VAR = "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102:opencore-version"


def _ioreg_acpi_raw() -> bytes:
    try:
        return subprocess.run(
            ["ioreg", "-a", "-r", "-c", "AppleACPIPlatformExpert", "-d", "1"],
            capture_output=True, timeout=30, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return b""


def parse_ioreg_acpi(raw: bytes) -> dict[bytes, list[bytes]]:
    """``ioreg -a`` plist -> {signature: [table bytes, ...]} for every table in
    the ``ACPI Tables`` dict, keyed by the table's *own* 4-byte signature
    (the dict keys are "SSDT", "SSDT-1", "SSDT-CpuPm"... and not reliable).
    Identical payloads are dropped."""
    from xml.parsers.expat import ExpatError

    if not raw.strip():
        return {}
    try:
        root = plistlib.loads(raw)
    except (plistlib.InvalidFileException, ValueError, ExpatError):
        return {}

    def find(node):
        if isinstance(node, dict):
            if isinstance(node.get("ACPI Tables"), dict):
                return node["ACPI Tables"]
            children = node.values()
        elif isinstance(node, list):
            children = node
        else:
            return None
        for v in children:
            hit = find(v)
            if hit is not None:
                return hit
        return None

    tables = find(root) or {}
    out: dict[bytes, list[bytes]] = {}
    for key in sorted(tables, key=lambda k: (k != "DSDT", len(k), k)):
        data = tables[key]
        if not isinstance(data, bytes) or len(data) < 36:  # shorter than an ACPI header
            continue
        bucket = out.setdefault(data[:4], [])
        if data not in bucket:
            bucket.append(data)
    return out


def _darwin_tables() -> dict[bytes, list[bytes]]:
    return parse_ioreg_acpi(_ioreg_acpi_raw())


def opencore_booted() -> bool:
    """True when this macOS was booted by OpenCore (i.e. a Hackintosh), so the
    IORegistry tables are post-patch, not what the firmware shipped."""
    if sys.platform != "darwin":
        return False
    try:
        p = subprocess.run(["nvram", _OC_NVRAM_VAR], capture_output=True,
                           timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return p.returncode == 0


def _dump_darwin(dest: Path) -> Path:
    tables = _darwin_tables()
    if b"DSDT" not in tables:
        raise DsdtUnavailable(
            "no ACPI tables in the IORegistry (Apple Silicon has no ACPI) — pass "
            "--dsdt with a folder of tables from the target PC"
        )
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "DSDT.aml").write_bytes(tables[b"DSDT"][0])
    for i, data in enumerate(tables.get(b"SSDT", []), 1):
        (dest / f"SSDT-{i}.aml").write_bytes(data)
    return dest


def _sig_dword(sig: bytes) -> int:
    """4-char ACPI signature -> the little-endian DWORD the Win32 table APIs
    key on (``b"DSDT"`` -> ``0x54445344``)."""
    return int.from_bytes(sig, "little")


def _get_acpi_table(sig: bytes) -> bytes | None:
    """Raw bytes of one ACPI table by signature via ``GetSystemFirmwareTable``,
    or ``None`` if the OS won't hand it over. Windows only."""
    k32 = ctypes.windll.kernel32
    table_id = _sig_dword(sig)
    size = k32.GetSystemFirmwareTable(_ACPI_PROVIDER, table_id, None, 0)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    got = k32.GetSystemFirmwareTable(_ACPI_PROVIDER, table_id, buf, size)
    if not got or got > size:
        return None
    return buf.raw[:got]


def _enum_acpi_tables() -> list[bytes]:
    """Every ACPI table signature the OS reports, in order, duplicates kept
    (a machine with three SSDTs lists ``b"SSDT"`` three times). Windows only."""
    k32 = ctypes.windll.kernel32
    size = k32.EnumSystemFirmwareTables(_ACPI_PROVIDER, None, 0)
    if not size:
        return []
    buf = ctypes.create_string_buffer(size)
    got = k32.EnumSystemFirmwareTables(_ACPI_PROVIDER, buf, size)
    raw = buf.raw[: min(got, size)]
    return [raw[i:i + 4] for i in range(0, len(raw) - 3, 4)]


def _dump_windows_native(dest: Path) -> Path:
    """Dump DSDT + whatever SSDT(s) the Win32 API will give (only the first
    per repeated signature) into ``dest``. No external tool, no admin."""
    dsdt = _get_acpi_table(b"DSDT")
    if not dsdt or dsdt[:4] != b"DSDT":
        raise DsdtUnavailable(
            "GetSystemFirmwareTable returned no DSDT on this host — "
            "fall back to acpidump.exe (see fetch.acpidump.fetch)"
        )
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "DSDT.aml").write_bytes(dsdt)

    # EnumSystemFirmwareTables lists every SSDT, but GetSystemFirmwareTable
    # can only return the first for a repeated signature. Pull the other
    # distinct-signature tables we understand; dedup identical payloads.
    seen: set[bytes] = {dsdt}
    idx = 0
    for sig in _enum_acpi_tables():
        if sig != b"SSDT":
            continue
        data = _get_acpi_table(sig)
        if not data or data in seen or data[:4] != b"SSDT":
            continue
        seen.add(data)
        idx += 1
        (dest / f"SSDT-{idx}.aml").write_bytes(data)
    return dest


def dump_tables(dest: Path, *, acpidump_exe: Path | None = None) -> Path:
    """Copy DSDT + every SSDT into ``dest`` and return it. SSDTTime works best
    with the whole set, not DSDT alone.

    On Windows the native ``GetSystemFirmwareTable`` path is tried first (no
    download); ``acpidump_exe``, if given, is used as a fallback and for the
    complete SSDT set. Ignored on Linux/macOS (macOS reads the IORegistry)."""
    if sys.platform.startswith("linux"):
        return _dump_linux(dest)
    if sys.platform == "win32":
        try:
            return _dump_windows_native(dest)
        except (DsdtUnavailable, OSError, AttributeError) as native_exc:
            if acpidump_exe is None:
                raise DsdtUnavailable(
                    f"native ACPI dump failed ({native_exc}); pass acpidump.exe "
                    "for a fallback (see fetch.acpidump.fetch)"
                ) from native_exc
            return _dump_windows(dest, acpidump_exe)
    if sys.platform == "darwin":
        return _dump_darwin(dest)
    raise DsdtUnavailable(f"no ACPI table dump path on {sys.platform} — pass --dsdt")


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
