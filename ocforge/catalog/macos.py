"""Which macOS releases a machine can realistically run.

Rules are public knowledge from Apple's supported-hardware lists and the
Dortania guide. Each release carries the constraints that matter for a
build:

* ``min_intel_gen`` — oldest Intel Core generation with a working iGPU/driver
  path (0 = no Intel floor, e.g. an AMD build).
* ``amd_ok`` — bootable on AMD Ryzen with the community kernel patches.
* ``needs_avx2`` — the OS itself requires AVX2 (Ventura and newer).
* ``metal_gpu_required`` — no non-Metal fallback; needs a supported dGPU on
  otherwise-unsupported iGPU hardware.
"""

from __future__ import annotations

from dataclasses import dataclass

from ocforge.model import Machine, Vendor


@dataclass(frozen=True)
class MacOSRelease:
    name: str
    major: int              # 11, 12, 13, 14, 15, 26 …
    darwin: int             # kernel major, for kext MinKernel/MaxKernel
    min_intel_gen: int
    amd_ok: bool
    needs_avx2: bool
    metal_gpu_required: bool


# newest first
RELEASES: tuple[MacOSRelease, ...] = (
    MacOSRelease("Tahoe", 26, 25, 8, True, True, True),
    MacOSRelease("Sequoia", 15, 24, 7, True, True, True),
    MacOSRelease("Sonoma", 14, 23, 7, True, True, True),
    MacOSRelease("Ventura", 13, 22, 6, True, True, False),
    MacOSRelease("Monterey", 12, 21, 3, True, False, False),
    MacOSRelease("Big Sur", 11, 20, 3, True, False, False),
)


def by_major(major: int) -> MacOSRelease | None:
    return next((r for r in RELEASES if r.major == major), None)


def _release_ok(rel: MacOSRelease, m: Machine) -> tuple[bool, str]:
    cpu = m.cpu
    if rel.needs_avx2 and "avx2" not in cpu.flags and cpu.vendor is Vendor.INTEL:
        return False, "needs AVX2"

    if cpu.vendor is Vendor.AMD:
        if not rel.amd_ok:
            return False, "AMD not supported on this release"
        # AMD builds have no iGPU; they need a Metal-capable dGPU.
        if rel.metal_gpu_required and (m.dgpu is None or m.dgpu.vendor is Vendor.NVIDIA):
            return False, "needs a supported AMD dGPU (no usable iGPU on AMD)"
        return True, ""

    if cpu.vendor is Vendor.INTEL:
        gen = cpu.intel_gen
        if gen == 0:
            return True, "Intel generation unknown — treat as tentative"
        if gen >= 11:
            # 11th gen+ Xe graphics has no macOS driver: desktop needs a dGPU,
            # laptop is usually a dead end.
            if m.dgpu is not None and m.dgpu.vendor is Vendor.AMD:
                return True, "iGPU unsupported — driving display from the AMD dGPU"
            return False, "11th gen+ Intel Xe graphics has no macOS driver"
        if gen < rel.min_intel_gen:
            return False, f"needs Intel {rel.min_intel_gen}th gen or newer"
        return True, ""

    return True, "CPU vendor unknown — tentative"


@dataclass(frozen=True)
class Compatibility:
    release: MacOSRelease
    supported: bool
    note: str


def evaluate(m: Machine) -> list[Compatibility]:
    """Every known release with a verdict, newest first."""
    return [Compatibility(r, *_release_ok(r, m)) for r in RELEASES]


def recommended(m: Machine) -> MacOSRelease | None:
    """Newest release that comes out clean (no note)."""
    for c in evaluate(m):
        if c.supported and not c.note:
            return c.release
    for c in evaluate(m):
        if c.supported:
            return c.release
    return None
