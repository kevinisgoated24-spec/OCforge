"""Which macOS releases a machine can realistically run.

Rules are public knowledge from Apple's supported-hardware lists and the
Dortania guide. Each release carries the constraints that matter for a
build:

* ``min_intel_gen`` — oldest Intel Core generation with a working iGPU/driver
  path (0 = no Intel floor, e.g. an AMD build).
* ``amd_ok`` — bootable on AMD Ryzen with the community kernel patches.
* ``needs_avx2`` — the OS itself requires AVX2 (Ventura and newer).

Every release also requires *some* supported graphics path at all — an Intel
iGPU or an AMD dGPU (see ``has_display_path``) — regardless of Metal; a
machine with no iGPU and only an NVIDIA (or absent) dGPU can't drive a
display on any of them.
"""

from __future__ import annotations

from dataclasses import dataclass

from ocforge.model import Machine, Vendor


class UnsupportedGpuError(ValueError):
    """No supported display path (see ``has_display_path``). Distinct from a
    plain ``ValueError`` so a caller can offer "continue anyway?" instead of
    just failing — pass ``allow_unsupported_gpu=True`` to
    :func:`ocforge.build.plan.make` to do so."""


@dataclass(frozen=True)
class MacOSRelease:
    name: str
    major: int              # 11, 12, 13, 14, 15, 26 …
    darwin: int             # kernel major, for kext MinKernel/MaxKernel
    min_intel_gen: int
    amd_ok: bool
    needs_avx2: bool


# newest first
RELEASES: tuple[MacOSRelease, ...] = (
    MacOSRelease("Tahoe", 26, 25, 8, True, True),
    MacOSRelease("Sequoia", 15, 24, 7, True, True),
    MacOSRelease("Sonoma", 14, 23, 7, True, True),
    MacOSRelease("Ventura", 13, 22, 6, True, True),
    MacOSRelease("Monterey", 12, 21, 3, True, False),
    MacOSRelease("Big Sur", 11, 20, 3, True, False),
)


def by_major(major: int) -> MacOSRelease | None:
    return next((r for r in RELEASES if r.major == major), None)


def has_display_path(m: Machine) -> bool:
    """True if something in this machine can plausibly drive a macOS display.

    An Intel iGPU always counts (its generation is checked separately). A
    dGPU only counts if it's AMD — NVIDIA (Maxwell and newer; Apple never
    shipped Kepler-or-older drivers past High Sierra either) has no macOS
    driver at all, on any release, Metal or otherwise. No iGPU and an
    unsupported/absent dGPU means no display once macOS hands off from the
    UEFI boot picker — not a build worth producing."""
    if m.igpu is not None:
        return True
    return m.dgpu is not None and m.dgpu.vendor is Vendor.AMD


def _release_ok(rel: MacOSRelease, m: Machine, *, ignore_gpu: bool = False) -> tuple[bool, str]:
    cpu = m.cpu
    if rel.needs_avx2 and cpu.vendor is Vendor.INTEL:
        brand = (cpu.brand or "").lower()
        if "pentium" in brand or "celeron" in brand:
            # Intel fuses AVX/AVX2 off on every Pentium/Celeron -> Monterey is
            # the newest macOS that boots. (The Windows/macOS probe reports no
            # feature flags, so a bare i3/i5/i7 is assumed to have AVX2.)
            return False, "Pentium/Celeron have no AVX2 (needed by Ventura+)"
        if cpu.flags and "avx2" not in cpu.flags:
            return False, "needs AVX2"

    if not ignore_gpu and not has_display_path(m):
        gpu_note = (f" ({m.dgpu.vendor.value} dGPU has no macOS driver)"
                   if m.dgpu else " (no GPU detected)")
        return False, f"no supported graphics — needs an Intel iGPU or an AMD dGPU{gpu_note}"

    if cpu.vendor is Vendor.AMD:
        if not rel.amd_ok:
            return False, "AMD not supported on this release"
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
            if ignore_gpu:
                return True, "iGPU unsupported and forced through anyway — expect no display"
            return False, "11th gen+ Intel Xe graphics has no macOS driver"
        if gen == 3 and rel.major > 11 and not (m.dgpu is not None and m.dgpu.vendor is Vendor.AMD):
            # Ivy Bridge iGPU has no driver past Big Sur (Dortania Ivy Bridge) --
            # Monterey+ needs a Metal AMD dGPU driving the display instead.
            if ignore_gpu:
                return True, "Ivy Bridge iGPU unsupported past Big Sur, forced through anyway"
            return False, "Ivy Bridge iGPU has no driver past Big Sur (11) — needs an AMD dGPU"
        if gen < rel.min_intel_gen:
            return False, f"needs Intel {rel.min_intel_gen}th gen or newer"
        return True, ""

    return True, "CPU vendor unknown — tentative"


@dataclass(frozen=True)
class Compatibility:
    release: MacOSRelease
    supported: bool
    note: str


def evaluate(m: Machine, *, ignore_gpu: bool = False) -> list[Compatibility]:
    """Every known release with a verdict, newest first.

    ``ignore_gpu`` skips the display-path gate — for a caller that already
    asked "this build is unsupported, continue anyway?" and got a yes; every
    *other* constraint (AVX2, Intel generation, AMD support) still applies.
    """
    return [Compatibility(r, *_release_ok(r, m, ignore_gpu=ignore_gpu)) for r in RELEASES]


def recommended(m: Machine, *, ignore_gpu: bool = False) -> MacOSRelease | None:
    """Newest release that comes out clean (no note)."""
    for c in evaluate(m, ignore_gpu=ignore_gpu):
        if c.supported and not c.note:
            return c.release
    for c in evaluate(m, ignore_gpu=ignore_gpu):
        if c.supported:
            return c.release
    return None
