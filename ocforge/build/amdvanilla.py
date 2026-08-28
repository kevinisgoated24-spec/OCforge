"""AMD Ryzen kernel patches.

Pulled from AMD-OSX/AMD_Vanilla at build time — that project is the canonical
source and it changes with every macOS release. The only local edit is byte 1
of the four "cpuid_cores_per_package" Replace values, which must equal the
machine's physical core count.
"""

from __future__ import annotations

import plistlib
from typing import Any

from ocforge.fetch.http import get_bytes

PATCHES_URL = "https://raw.githubusercontent.com/AMD-OSX/AMD_Vanilla/master/patches.plist"

_CORE_COUNT_MARK = "cpuid_cores_per_package"


def splice_core_count(patches: list[dict[str, Any]], cores: int) -> list[dict[str, Any]]:
    if not 1 <= cores <= 254:
        raise ValueError(f"implausible physical core count: {cores}")
    out = []
    for p in patches:
        p = dict(p)
        if _CORE_COUNT_MARK in p.get("Comment", "") and isinstance(p.get("Replace"), (bytes, bytearray)):
            rep = bytearray(p["Replace"])
            if len(rep) >= 2:
                rep[1] = cores
                p["Replace"] = bytes(rep)
        out.append(p)
    return out


def load(raw: bytes) -> list[dict[str, Any]]:
    return plistlib.loads(raw)["Kernel"]["Patch"]


def fetch(cores: int) -> list[dict[str, Any]]:
    return splice_core_count(load(get_bytes(PATCHES_URL, timeout=45)), cores)
