"""Fetch corpnewt/UnPlugged.command.

UnPlugged is a single self-contained bash script meant to be run *inside*
macOS Recovery — it builds and launches the offline installer app from the
InstallAssistant.pkg it finds sitting next to it. ocforge just stages it
onto the ExFAT payload; the user runs it themselves in Recovery Terminal
(see the README for why: it needs a real macOS environment, which nothing
running the host-side build can provide or fake).
"""

from __future__ import annotations

from pathlib import Path

from ocforge.fetch.http import open_url

SCRIPT_URL = "https://raw.githubusercontent.com/corpnewt/UnPlugged/master/UnPlugged.command"


def fetch(work: Path) -> Path:
    out = work / "UnPlugged.command"
    if not out.exists():
        with open_url(SCRIPT_URL, timeout=30) as resp:
            out.write_bytes(resp.read())
    return out
