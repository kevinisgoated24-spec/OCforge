"""Download + unpack an OpenCore release."""

from __future__ import annotations

import zipfile
from pathlib import Path

from ocforge.fetch.github import Asset, latest_asset
from ocforge.fetch.http import Progress, download


def resolve(*, debug: bool = False) -> Asset:
    kind = "DEBUG" if debug else "RELEASE"
    return latest_asset("acidanthera/OpenCorePkg", rf"^OpenCore-[\d.]+-{kind}\.zip$")


def fetch(dest_dir: Path, *, debug: bool = False, on_progress: Progress | None = None) -> Path:
    """Download the OpenCore zip and extract it under ``dest_dir/opencore``.
    Returns that directory (which contains ``X64/EFI/`` and ``Utilities/``)."""
    asset = resolve(debug=debug)
    zpath = dest_dir / asset.name
    download(asset.url, zpath, sha256=asset.sha256, expected_size=asset.size, on_progress=on_progress)
    out = dest_dir / "opencore"
    if out.exists():
        import shutil

        shutil.rmtree(out)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(out)
    return out


def _utility(opencore_dir: Path, subdir: str, names: tuple[str, ...]) -> str | None:
    import os
    import sys

    base = opencore_dir / "Utilities" / subdir
    for name in names:
        p = base / name
        if p.exists():
            if sys.platform != "win32":
                os.chmod(p, 0o755)
            return str(p)
    return None


def macserial_binary(opencore_dir: Path) -> str | None:
    import sys

    name = {"win32": "macserial.exe", "darwin": "macserial"}.get(sys.platform, "macserial.linux")
    return _utility(opencore_dir, "macserial", (name, "macserial", "macserial.linux"))


def ocvalidate_binary(opencore_dir: Path) -> str | None:
    import sys

    name = {"win32": "ocvalidate.exe", "darwin": "ocvalidate"}.get(sys.platform, "ocvalidate.linux")
    return _utility(opencore_dir, "ocvalidate", (name, "ocvalidate", "ocvalidate.linux"))
