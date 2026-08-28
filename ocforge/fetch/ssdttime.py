"""Fetch corpnewt/SSDTTime.

Not a release — grabbed as a branch tarball and cached under the work dir.
SSDTTime downloads its own ``iasl`` on first run.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

from ocforge.fetch.http import open_url

TARBALL = "https://codeload.github.com/corpnewt/SSDTTime/tar.gz/refs/heads/master"


def fetch(work: Path) -> Path:
    out = work / "ssdttime"
    if (out / "SSDTTime.py").exists():
        return out
    with open_url(TARBALL, timeout=60) as resp:
        buf = io.BytesIO(resp.read())
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        root = tf.getnames()[0].split("/")[0]
        tf.extractall(work, filter="data")
    (work / root).rename(out)
    return out
