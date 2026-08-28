"""Download an Apple macOS recovery image.

Uses ``macrecovery.py`` from the OpenCore release (``Utilities/macrecovery/``)
— it does the osrecovery.apple.com session dance that would be tedious to
re-implement. We just pick the right board-id for the target release.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# board-id understood by macrecovery's `-b`. Zeros for `-m` (MLB).
_BOARD = {
    26: "Mac-937A206F2EE63C01",   # Sequoia board also serves Tahoe recovery
    15: "Mac-937A206F2EE63C01",
    14: "Mac-827FAC58A8FDFA22",
    13: "Mac-4B682C642B45593E",
    12: "Mac-E43C1C25D4880AD6",
    11: "Mac-2BD1B31983FE1663",
}
_MLB = "00000000000000000"


class RecoveryError(RuntimeError):
    pass


def macrecovery_script(opencore_dir: Path) -> Path:
    p = opencore_dir / "Utilities" / "macrecovery" / "macrecovery.py"
    if not p.exists():
        raise RecoveryError(f"macrecovery.py not found under {opencore_dir}")
    return p


def download(major: int, opencore_dir: Path, dest: Path, *, latest: bool = False) -> Path:
    """Fetch recovery into ``dest`` (a ``com.apple.recovery.boot`` dir is
    created there). Returns that directory."""
    board = _BOARD.get(major)
    if board is None:
        raise RecoveryError(f"no recovery board-id known for macOS {major}")
    script = macrecovery_script(opencore_dir)
    dest.mkdir(parents=True, exist_ok=True)

    argv = [sys.executable, str(script), "-b", board, "-m", _MLB]
    argv += ["-os", "latest"] if latest else []
    argv += ["download", "-o", str(dest)]

    proc = subprocess.run(argv, capture_output=True, text=True, timeout=60 * 30, check=False)
    if proc.returncode != 0:
        raise RecoveryError(
            f"macrecovery exited {proc.returncode}\n{(proc.stdout + proc.stderr)[-1000:]}"
        )
    boot = dest / "com.apple.recovery.boot"
    if not (boot / "BaseSystem.dmg").exists() and not (boot / "RecoveryImage.dmg").exists():
        raise RecoveryError(f"macrecovery finished but no image landed in {boot}")
    return boot
