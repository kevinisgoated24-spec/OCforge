"""OcBinaryData — HfsPlus.efi and the picker Resources.

Not a release; fetched as a branch tarball and cached.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

from ocforge.fetch.http import open_url

TARBALL = "https://codeload.github.com/acidanthera/OcBinaryData/tar.gz/refs/heads/master"


def fetch(work: Path) -> Path:
    """Extract OcBinaryData under ``work/ocbinarydata`` and return that dir
    (it has ``Drivers/`` and ``Resources/``)."""
    out = work / "ocbinarydata"
    if (out / "Drivers" / "HfsPlus.efi").exists():
        return out
    with open_url(TARBALL, timeout=60) as resp:
        buf = io.BytesIO(resp.read())
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        root = tf.getnames()[0].split("/")[0]
        tf.extractall(work, filter="data")
    (work / root).rename(out)
    return out
