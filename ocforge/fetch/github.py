r"""Resolve a downloadable asset from a GitHub release.

``latest_asset("acidanthera/OpenCorePkg", r"OpenCore-.*-RELEASE\.zip")`` →
``Asset(name, url, size, digest)``. Digest is Apple/GitHub's ``sha256:...``
attestation when the release provides one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ocforge.fetch.http import get_bytes, github_headers, open_url

API = "https://api.github.com/repos"


@dataclass(frozen=True)
class Asset:
    name: str
    url: str
    size: int
    sha256: str | None = None
    release_tag: str = ""


def _release_json(repo: str, tag: str | None) -> dict:
    path = f"{API}/{repo}/releases/latest" if tag in (None, "latest") else f"{API}/{repo}/releases/tags/{tag}"
    with open_url(path, headers={"Accept": "application/vnd.github+json", **github_headers()}) as resp:
        return json.loads(resp.read())


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
    data = json.loads(get_bytes(f"{API}/{repo}/commits/{branch}"))
    return data["sha"]
