"""Fetch the precompiled SSDT .aml files a BuildPlan selected."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ocforge.catalog.acpi import Ssdt
from ocforge.fetch.http import DownloadError, get_bytes

_RAW = "https://raw.githubusercontent.com/{repo}/{path}"
_DORTANIA = "dortania/Getting-Started-With-ACPI"


@dataclass
class SsdtResult:
    name: str
    path: Path | None
    error: str = ""


def fetch_all(ssdts: list[Ssdt], acpi_out: Path) -> list[SsdtResult]:
    acpi_out.mkdir(parents=True, exist_ok=True)
    results = []
    for s in ssdts:
        url = _RAW.format(repo=_DORTANIA, path=s.source_path())
        try:
            data = get_bytes(url, timeout=30)
            if data[:4] not in (b"SSDT", b"DSDT"):
                # a 404 page or an HTML redirect, not an AML table
                raise DownloadError("response is not an AML table")
            dst = acpi_out / f"{s.name}.aml"
            dst.write_bytes(data)
            results.append(SsdtResult(s.name, dst))
        except (DownloadError, OSError) as exc:
            results.append(SsdtResult(s.name, None, str(exc)))
    return results
