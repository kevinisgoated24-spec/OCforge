"""Fetch a standalone ``acpidump.exe`` for Windows ACPI table dumping.

SSDTTime's own ``Scripts/dsdt.py`` *checks* for ``acpidump.exe`` next to
itself but never downloads it — confirmed by actually fetching the SSDTTime
tree and finding it absent. The real upstream is the ACPICA project itself
(``open-acpica/acpica`` — the same repo SSDTTime's own code points its
Windows ``iasl`` fetch at), which publishes real, versioned GitHub releases
with ``acpidump.exe`` as a bare asset, no zip needed.
"""

from __future__ import annotations

from pathlib import Path

from ocforge.fetch import github
from ocforge.fetch.http import download

REPO = "open-acpica/acpica"


def fetch(work: Path) -> Path:
    dest = work / "acpidump" / "acpidump.exe"
    if dest.is_file():
        return dest
    asset = github.latest_asset(REPO, r"^acpidump\.exe$")
    download(asset.url, dest, sha256=asset.sha256, expected_size=asset.size)
    return dest
