"""Download the kexts a BuildPlan selected and extract each .kext bundle."""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ocforge.catalog.kexts import Selected
from ocforge.fetch.github import latest_asset
from ocforge.fetch.http import DownloadError, download


@dataclass
class KextResult:
    name: str
    bundle_dir: Path | None      # the extracted <name>.kext, or None if it failed
    error: str = ""


def _extract_bundle(zip_path: Path, wanted: str, into: Path) -> Path | None:
    """Pull the file tree of ``wanted`` (a ``<name>.kext``) out of the zip into
    ``into/<name>.kext/``. Returns that path, or None if the bundle isn't there.
    Picks the first (shallowest) match, so a ``Release/`` copy wins over
    ``Debug/``."""
    name = wanted.split("/")[-1]
    marker = f"/{name}/"
    out = into / name
    if out.exists():
        shutil.rmtree(out)

    with zipfile.ZipFile(zip_path) as zf:
        files = [n for n in zf.namelist() if not n.endswith("/")]
        # candidate bundle roots: "<prefix><name>/"
        roots = sorted(
            {f[: f.index(marker) + 1] + name + "/" for f in files if marker in f"/{f}" and not f.startswith(name + "/")}
            | {name + "/" for f in files if f.startswith(name + "/")}
        )
        if not roots:
            return None
        # prefer a Release/ copy, then the shallowest path
        root = min(roots, key=lambda r: (0 if "release" in r.lower() else 1, r.count("/"), len(r)))
        for f in files:
            if not f.startswith(root):
                continue
            dst = out / f[len(root):]
            dst.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(f) as src, open(dst, "wb") as fh:
                shutil.copyfileobj(src, fh)
    return out if out.exists() else None


def fetch_all(selected: list[Selected], work: Path, kexts_out: Path) -> list[KextResult]:
    kexts_out.mkdir(parents=True, exist_ok=True)
    dl_cache = work / "kext-zips"
    dl_cache.mkdir(parents=True, exist_ok=True)

    zip_cache: dict[tuple[str, str], Path] = {}
    results: list[KextResult] = []

    for s in selected:
        k = s.kext
        if not k.repo:  # e.g. UTBMap, generated later
            results.append(KextResult(k.name, None, "generated locally, not downloaded"))
            continue
        key = (k.repo, k.asset)
        try:
            if key not in zip_cache:
                asset = latest_asset(k.repo, k.asset)
                zp = dl_cache / f"{k.repo.replace('/', '_')}__{asset.name}"
                download(asset.url, zp, sha256=asset.sha256, expected_size=asset.size)
                zip_cache[key] = zp
            bundle = _extract_bundle(zip_cache[key], k.bundle_path(), kexts_out)
            if bundle is None:
                results.append(KextResult(k.name, None, f"{k.bundle_path()} not found in {k.repo} release"))
            else:
                results.append(KextResult(k.name, bundle))
        except (LookupError, DownloadError, OSError) as exc:
            results.append(KextResult(k.name, None, str(exc)))
    return results
