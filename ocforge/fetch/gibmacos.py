"""Fetch corpnewt/gibMacOS and use it to grab a full macOS installer.

Same "grab the branch tarball, cache under the work dir" pattern as
[`ssdttime`](ssdttime.py). gibMacOS talks to Apple's software-update catalog
directly (no third-party deps) — we just shell out to it non-interactively.

Passing ``--version`` auto-enables gibMacOS's own ``--no-interactive`` mode,
so no prompts to worry about; see its ``--help`` for the rest.
"""

from __future__ import annotations

import io
import subprocess
import sys
import tarfile
from pathlib import Path

from ocforge.fetch.http import open_url

TARBALL = "https://codeload.github.com/corpnewt/gibMacOS/tar.gz/refs/heads/master"


class GibMacOSError(RuntimeError):
    pass


def fetch(work: Path) -> Path:
    out = work / "gibmacos"
    if (out / "gibMacOS.py").exists():
        return out
    with open_url(TARBALL, timeout=60) as resp:
        buf = io.BytesIO(resp.read())
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        root = tf.getnames()[0].split("/")[0]
        tf.extractall(work, filter="data")
    (work / root).rename(out)
    return out


def download_installer(work: Path, version: str, *, catalog: str = "publicrelease",
                       timeout: int = 60 * 60) -> Path:
    """Downloads the full installer (InstallAssistant.pkg + friends) for
    ``version`` (e.g. "13" or "Ventura") and returns the InstallAssistant.pkg
    path. Large (~10-13 GB) and slow — this can take a while."""
    root = fetch(work)
    out_dir = work / "gibmacos-downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    argv = [
        sys.executable, str(root / "gibMacOS.py"),
        "--version", version,
        "--catalog", catalog,
        "--download-dir", str(out_dir),
    ]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise GibMacOSError(f"gibMacOS exited {proc.returncode}\n{(proc.stdout + proc.stderr)[-1500:]}")
    hits = sorted(out_dir.rglob("InstallAssistant.pkg"))
    if not hits:
        raise GibMacOSError(
            f"gibMacOS finished but no InstallAssistant.pkg landed under {out_dir}\n"
            f"{(proc.stdout + proc.stderr)[-1500:]}"
        )
    return hits[0]
