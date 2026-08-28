"""HTTP download with resume, progress and optional SHA-256 verification.

stdlib only — this has to run from minimal environments (a live USB, a fresh
Windows box) with nothing pip-installed.
"""

from __future__ import annotations

import hashlib
import os
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

UA = "ocforge"
Progress = Callable[[int, int], None]  # (bytes_done, bytes_total) — total 0 if unknown


class DownloadError(RuntimeError):
    pass


def _contexts() -> list[ssl.SSLContext]:
    ctxs = [ssl.create_default_context()]
    try:
        import certifi  # optional; helps frozen builds reach the system store

        ctxs.append(ssl.create_default_context(cafile=certifi.where()))
    except ModuleNotFoundError:
        pass
    return ctxs


def open_url(url: str, *, headers: dict[str, str] | None = None, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    last: Exception | None = None
    for ctx in _contexts():
        try:
            return urllib.request.urlopen(req, context=ctx, timeout=timeout)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, ssl.SSLError) as exc:
            last = exc
    raise DownloadError(f"could not open {url}: {last}")


def get_bytes(url: str, *, timeout: int = 30) -> bytes:
    with open_url(url, timeout=timeout) as resp:
        return resp.read()


def download(
    url: str,
    dest: Path,
    *,
    sha256: str | None = None,
    expected_size: int = 0,
    on_progress: Progress | None = None,
) -> Path:
    """Stream ``url`` to ``dest``, resuming a partial file with a Range request.
    Verifies ``sha256`` / ``expected_size`` when given. Returns ``dest``."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    have = dest.stat().st_size if dest.exists() else 0
    if expected_size and have > expected_size:
        dest.unlink()
        have = 0
    if expected_size and have == expected_size and _ok(dest, sha256):
        if on_progress:
            on_progress(have, expected_size)
        return dest

    headers = {"Range": f"bytes={have}-"} if have else {}
    with open_url(url, headers=headers) as resp:
        mode = "ab" if have and resp.status == 206 else "wb"
        if mode == "wb":
            have = 0
        total = expected_size or _content_total(resp, have)
        done = have
        with open(dest, mode) as fh:
            while chunk := resp.read(1 << 16):
                fh.write(chunk)
                done += len(chunk)
                if on_progress:
                    on_progress(done, total)

    if expected_size and dest.stat().st_size != expected_size:
        raise DownloadError(f"{dest.name}: {dest.stat().st_size} bytes, expected {expected_size}")
    if sha256 and not _ok(dest, sha256):
        raise DownloadError(f"{dest.name}: sha256 mismatch")
    return dest


def _content_total(resp, have: int) -> int:
    rng = resp.headers.get("Content-Range", "")
    if "/" in rng and rng.rsplit("/", 1)[-1].isdigit():
        return int(rng.rsplit("/", 1)[-1])
    clen = resp.headers.get("Content-Length")
    return have + int(clen) if clen and clen.isdigit() else 0


def _ok(path: Path, sha256: str | None) -> bool:
    if not sha256:
        return True
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().lower() == sha256.lower()


def github_headers() -> dict[str, str]:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    return {"Authorization": f"Bearer {tok}"} if tok else {}
