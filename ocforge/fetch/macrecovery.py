"""Fetch the current ``macrecovery.py`` from acidanthera.

The copy bundled in the OpenCore *release* zip lags master and still calls
``os.get_terminal_size()`` in its progress printer, which throws
``OSError: [WinError 6]`` when stdout isn't a real console (e.g. spawned from a
GUI). Master switched to ``shutil.get_terminal_size()``, which falls back to
80x24 instead of raising. This is the same trick corpnewt's gibMacRecovery
uses — pull the script straight from master.
"""

from __future__ import annotations

from pathlib import Path

from ocforge.fetch.http import DownloadError, get_bytes

_MASTER = (
    "https://raw.githubusercontent.com/acidanthera/OpenCorePkg/master/"
    "Utilities/macrecovery/macrecovery.py"
)


class MacrecoveryUnavailable(RuntimeError):
    pass


def fetch(work: Path) -> Path:
    """Download (and cache) ``macrecovery.py`` under ``work``; return its path."""
    dest = work / "macrecovery" / "macrecovery.py"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = get_bytes(_MASTER, timeout=30)
    except DownloadError as exc:  # offline / GitHub down
        raise MacrecoveryUnavailable(str(exc)) from exc
    if b"action_download" not in data:
        raise MacrecoveryUnavailable("fetched file doesn't look like macrecovery.py")
    dest.write_bytes(data)
    return dest
