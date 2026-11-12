"""Fetch a standalone ``acpidump.exe`` for Windows ACPI table dumping.

SSDTTime's own ``Scripts/dsdt.py`` *checks* for ``acpidump.exe`` next to
itself but never downloads it — confirmed by actually fetching the SSDTTime
tree and finding it absent. The real upstream is the ACPICA project itself
(``open-acpica/acpica`` — the same repo SSDTTime's own code points its
Windows ``iasl`` fetch at), which publishes real, versioned GitHub releases
with ``acpidump.exe`` as a bare asset, no zip needed.

ACPICA doesn't publish Windows binaries on every release -- as of their
``20260930`` release, ``.exe`` assets (acpidump, iasl, everything) are gone
entirely, Unix-only. ``20260408`` is the last release with the full set, so
that's the pinned fallback once "latest" comes up empty -- not because
_this_ release is special, just the newest one known to actually have them.
A future ACPICA release resuming Windows builds is tried first, automatically.
"""

from __future__ import annotations

from pathlib import Path

from ocforge.fetch import github
from ocforge.fetch.http import download

REPO = "open-acpica/acpica"

# Last known-good release with Windows .exe assets (see module docstring).
_PINNED_FALLBACK_TAG = "20260408"


def _find_asset(pattern: str) -> github.Asset:
    try:
        return github.latest_asset(REPO, pattern)
    except LookupError:
        return github.latest_asset(REPO, pattern, tag=_PINNED_FALLBACK_TAG)


def fetch(work: Path) -> Path:
    dest = work / "acpidump" / "acpidump.exe"
    if dest.is_file():
        return dest
    asset = _find_asset(r"^acpidump\.exe$")
    download(asset.url, dest, sha256=asset.sha256, expected_size=asset.size)
    return dest
