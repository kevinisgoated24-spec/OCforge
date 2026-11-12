"""Fetch a standalone ``iasl.exe`` (the ACPI compiler/decompiler) for Windows.

SSDTTime bootstraps its own copy on first run, from this same ACPICA repo --
but as a versioned zip (``iasl-win-YYYYMMDD.zip``) it maintains its own
blacklist against, falling back to a bundled "legacy" zip when the current
one is blacklisted. That fallback has a bug: it extracts and places
``iasl-legacy.exe`` into ``Scripts/``, then still fails its own "does
``iasl.exe`` exist" check and aborts -- producing zero SSDTs with no menu
ever run, on every affected version, not something specific to one machine.

ACPICA's own releases also publish ``iasl.exe`` directly as a bare asset (see
``fetch/acpidump.py``, which pulls ``acpidump.exe`` the same way) -- no zip,
no blacklist, no legacy-fallback bug to trip over. Pre-placing it in
SSDTTime's ``Scripts/`` before ever invoking ``SSDTTime.py`` means its
bootstrap sees a working ``iasl.exe`` already there and never touches its
own fetch path at all.
"""

from __future__ import annotations

from pathlib import Path

from ocforge.fetch.acpidump import _find_asset
from ocforge.fetch.http import download


def fetch(work: Path) -> Path:
    dest = work / "iasl" / "iasl.exe"
    if dest.is_file():
        return dest
    asset = _find_asset(r"^iasl\.exe$")
    download(asset.url, dest, sha256=asset.sha256, expected_size=asset.size)
    return dest
