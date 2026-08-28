"""Download an Apple macOS recovery image.

Uses ``macrecovery.py`` (acidanthera) for the osrecovery.apple.com session
dance — we just pick the right board-id for the target release. We prefer the
*master* copy of the script (fetched fresh, cached under the work dir) over the
one bundled in the OpenCore release zip: the bundled one still calls
``os.get_terminal_size()`` in its progress printer and crashes with
``OSError: [WinError 6]`` when run without a console (e.g. from the GUI).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ocforge.fetch import macrecovery as fetch_macrecovery

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


def _resolve_script(opencore_dir: Path, work: Path | None) -> Path:
    if work is not None:
        try:
            return fetch_macrecovery.fetch(work)
        except fetch_macrecovery.MacrecoveryUnavailable:
            pass  # fall back to the bundled (older) copy
    return macrecovery_script(opencore_dir)


def download(major: int, opencore_dir: Path, dest: Path, *, latest: bool = False,
             work: Path | None = None) -> Path:
    """Fetch recovery into ``dest/com.apple.recovery.boot`` and return that
    directory. macrecovery writes straight into its ``-o`` dir, so we point it
    at the ``com.apple.recovery.boot`` folder itself."""
    board = _BOARD.get(major)
    if board is None:
        raise RecoveryError(f"no recovery board-id known for macOS {major}")
    script = _resolve_script(opencore_dir, work)
    boot = dest / "com.apple.recovery.boot"
    boot.mkdir(parents=True, exist_ok=True)

    argv = [sys.executable, str(script), "-b", board, "-m", _MLB]
    argv += ["-os", "latest"] if latest else []
    argv += ["download", "-o", str(boot)]

    # Force a sane terminal width and unbuffered UTF-8 so the script's progress
    # printer never touches a missing console.
    env = {**os.environ, "COLUMNS": "80", "LINES": "24",
           "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

    proc = subprocess.run(
        argv, capture_output=True, text=True, timeout=60 * 30, check=False,
        stdin=subprocess.DEVNULL, env=env,
    )
    if proc.returncode != 0:
        raise RecoveryError(
            f"macrecovery exited {proc.returncode}\n{(proc.stdout + proc.stderr)[-1200:]}"
        )
    if not (boot / "BaseSystem.dmg").exists() and not (boot / "RecoveryImage.dmg").exists():
        raise RecoveryError(f"macrecovery finished but no image landed in {boot}")
    return boot
