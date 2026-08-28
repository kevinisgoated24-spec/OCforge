r"""Resolve a downloadable asset from a GitHub release.

``latest_asset("acidanthera/OpenCorePkg", r"OpenCore-.*-RELEASE\.zip")`` →
``Asset(name, url, size, digest)``. Digest is Apple/GitHub's ``sha256:...``
attestation when the release provides one.

Release JSON is cached — in-process always, and on disk (6 h TTL) once
:func:`set_cache_dir` is called — so a build that resolves ~20 kexts from ~10
repos, or a rebuild an hour later, spends a handful of API calls, not dozens.
Unauthenticated GitHub allows only 60 requests/hour; :func:`http.github_headers`
supplies a token from ``GITHUB_TOKEN`` / ``GH_TOKEN`` / an authenticated ``gh``.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from ocforge.fetch.http import github_headers, open_url

API = "https://api.github.com/repos"

_MEM: dict[str, dict] = {}
_CACHE_DIR: Path | None = None
_TTL = 6 * 3600


def set_cache_dir(path: Path | None) -> None:
    """Point the on-disk release-JSON cache at ``path`` (call once per build)."""
    global _CACHE_DIR
    _CACHE_DIR = path
    if path is not None:
        path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Asset:
    name: str
    url: str
    size: int
    sha256: str | None = None
    release_tag: str = ""


def _cache_file(key: str) -> Path | None:
    if _CACHE_DIR is None:
        return None
    return _CACHE_DIR / (key.replace("/", "_") + ".json")


def _release_json(repo: str, tag: str | None) -> dict:
    key = f"{repo}@{tag or 'latest'}"
    if key in _MEM:
        return _MEM[key]

    cf = _cache_file(key)
    if cf is not None and cf.is_file() and (time.time() - cf.stat().st_mtime) < _TTL:
        try:
            data = json.loads(cf.read_text())
            _MEM[key] = data
            return data
        except (json.JSONDecodeError, OSError):
            pass

    path = (f"{API}/{repo}/releases/latest" if tag in (None, "latest")
            else f"{API}/{repo}/releases/tags/{tag}")
    with open_url(path, headers={"Accept": "application/vnd.github+json", **github_headers()}) as resp:
        data = json.loads(resp.read())

    _MEM[key] = data
    if cf is not None:
        try:
            cf.write_text(json.dumps(data))
        except OSError:
            pass
    return data


def _digest(asset: dict) -> str | None:
    d = asset.get("digest") or ""
    return d.split(":", 1)[1] if d.startswith("sha256:") else None


def list_assets(repo: str, tag: str | None = "latest") -> list[Asset]:
    rel = _release_json(repo, tag)
    return [
        Asset(a["name"], a["browser_download_url"], a.get("size", 0), _digest(a), rel.get("tag_name", ""))
        for a in rel.get("assets", [])
    ]


def latest_asset(repo: str, name_pattern: str, *, tag: str | None = "latest") -> Asset:
    rx = re.compile(name_pattern)
    matches = [a for a in list_assets(repo, tag) if rx.search(a.name)]
    if not matches:
        raise LookupError(f"no asset matching /{name_pattern}/ in {repo}@{tag}")
    # prefer the shortest name (avoids picking a *-DEBUG when both exist and the
    # pattern was loose) then the largest — real payloads over checksums.
    matches.sort(key=lambda a: (len(a.name), -a.size))
    return matches[0]


def head_commit(repo: str, branch: str = "main") -> str:
    with open_url(f"{API}/{repo}/commits/{branch}",
                  headers={"Accept": "application/vnd.github+json", **github_headers()}) as resp:
        return json.loads(resp.read())["sha"]
