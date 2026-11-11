"""Shared helpers for the per-OS probes.

Deliberately tiny: command execution, a couple of string→enum mappers, and
Intel-generation inference. Anything OS-specific lives in the sibling modules.
"""

from __future__ import annotations

import re
import shutil
import subprocess

from ocforge.model import Vendor

# --- PCI vendor ids we care about -----------------------------------------

_PCI_VENDOR = {
    "8086": Vendor.INTEL,
    "1002": Vendor.AMD,
    "1022": Vendor.AMD,
    "10de": Vendor.NVIDIA,
    "10ec": Vendor.REALTEK,
    "14e4": Vendor.BROADCOM,
    "17cb": Vendor.QUALCOMM,
    "168c": Vendor.QUALCOMM,  # Atheros, now Qualcomm
    "106b": Vendor.APPLE,
}


def vendor_from_pci(vendor_id: str) -> Vendor:
    return _PCI_VENDOR.get(vendor_id.lower().removeprefix("0x").zfill(4), Vendor.UNKNOWN)


def vendor_from_text(text: str) -> Vendor:
    t = text.lower()
    for needle, v in (
        ("intel", Vendor.INTEL),
        ("amd", Vendor.AMD),
        ("advanced micro devices", Vendor.AMD),
        ("nvidia", Vendor.NVIDIA),
        ("geforce", Vendor.NVIDIA),
        ("realtek", Vendor.REALTEK),
        ("broadcom", Vendor.BROADCOM),
        ("qualcomm", Vendor.QUALCOMM),
        ("atheros", Vendor.QUALCOMM),
        ("apple", Vendor.APPLE),
    ):
        if needle in t:
            return v
    return Vendor.UNKNOWN


# --- command execution --------------------------------------------------------


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def run(argv: list[str], *, timeout: int = 20, check: bool = False) -> str:
    """Run a command, return stdout as text. Empty string on failure unless
    ``check`` is set, in which case CalledProcessError propagates."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
        return proc.stdout
    except (OSError, subprocess.SubprocessError):
        if check:
            raise
        return ""


def powershell(script: str, *, timeout: int = 25) -> str:
    return run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        timeout=timeout,
    )


# --- Intel Core generation from a brand string ------------------------------

_INTEL_GEN_RULES: tuple[tuple[re.Pattern[str], int, str], ...] = (
    # `\s*(?:\(tm\))?\s+` rather than a plain `\s+` after "core" -- Windows'
    # own CIM/WMI CPU name always carries the registered/trademark glyphs
    # with no space before them ("Core(TM) Ultra 5 125U", "Core(TM) 3
    # 100U"), so a bare `\bcore\s+` never matched a single real brand string
    # here, on any generation -- only ocforge's own plain test fixtures.
    (re.compile(r"\bcore\s*(?:\(tm\))?\s+ultra\s+\d\s+2\d\d"), 15, "Arrow Lake"),
    (re.compile(r"\bcore\s*(?:\(tm\))?\s+ultra\s+\d\s+1\d\d"), 14, "Meteor Lake"),
    (re.compile(r"\bi[3579]-14\d\d\d"), 14, "Raptor Lake Refresh"),
    (re.compile(r"\bi[3579]-13\d\d\d"), 13, "Raptor Lake"),
    # Late 2023+: Intel dropped "i3/i5/i7" for non-Ultra parts too -- "Core
    # 3/5/7/9" with no generation digit in the name at all, just a 3-digit
    # model number. The 100-series is a Raptor Lake rebrand (same silicon,
    # same gen number, same lack of an ig-platform-id entry below, as the
    # old-naming i3579-13xxx rule above) -- confirmed e.g. by the Core 3
    # 100U, whose own iGPU (8086:a7ad) is one of WhateverXe's documented
    # Raptor Lake-U ids, not a classic Gen9.5 UHD 6xx one.
    (re.compile(r"\bcore\s*(?:\(tm\))?\s+[3579]\s+1\d\d[uhp]?\b"), 13, "Raptor Lake"),
    (re.compile(r"\bi[3579]-12\d\d\d"), 12, "Alder Lake"),
    (re.compile(r"\bi[3579]-11\d\d\d"), 11, "Rocket/Tiger Lake"),
    # Both "10th gen" in Intel's own marketing, but different silicon needing
    # different SMBIOS/DeviceProperties (build/config.py, build/plan.py) --
    # distinguished by the model-number shape: Ice Lake is 4 digits + a
    # graphics-tier suffix (1065G7, 1035G1, 1038NG7); Comet Lake is a plain
    # 5-digit number (10510U) with no such suffix, so it's never matched by
    # the Ice Lake pattern below.
    (re.compile(r"\bi[3579]-10\d\dn?g[147]\b"), 10, "Ice Lake"),
    (re.compile(r"\bi[3579]-10\d\d\d"), 10, "Comet Lake"),
    (re.compile(r"\bi[3579]-9\d\d\d"), 9, "Coffee Lake Refresh"),
    (re.compile(r"\bi[3579]-8\d\d\d"), 8, "Coffee Lake"),
    (re.compile(r"\bi[3579]-7\d\d\d"), 7, "Kaby Lake"),
    (re.compile(r"\bi[3579]-6\d\d\d"), 6, "Skylake"),
    (re.compile(r"\bi[3579]-5\d\d\d"), 5, "Broadwell"),
    (re.compile(r"\bi[3579]-4\d\d\d"), 4, "Haswell"),
    (re.compile(r"\bi[3579]-3\d\d\d"), 3, "Ivy Bridge"),
    (re.compile(r"\bi[3579]-2\d\d\d"), 2, "Sandy Bridge"),

    # Pentium Gold / Celeron desktop parts — no i3/i5 number, keyed off the
    # G-series SKU. These need a CPUID spoof (handled in build/config.py).
    (re.compile(r"\b(?:pentium|celeron)\b.*\bg6\d{3}"), 10, "Comet Lake (Pentium/Celeron)"),
    (re.compile(r"\bceleron\b.*\bg59\d\d"), 10, "Comet Lake (Celeron)"),
    (re.compile(r"\bpentium\b.*\bg5\d{3}"), 8, "Coffee Lake (Pentium Gold)"),
    (re.compile(r"\bceleron\b.*\bg49\d\d"), 8, "Coffee Lake (Celeron)"),
    (re.compile(r"\bpentium\b.*\bg4[56]\d\d"), 7, "Kaby Lake (Pentium)"),
    (re.compile(r"\b(?:pentium|celeron)\b.*\bg3\d{3}"), 6, "Skylake (Pentium/Celeron)"),
)


def intel_generation(brand: str) -> tuple[int, str]:
    """(generation number, microarch family). (0, "") when it can't be told."""
    b = brand.lower()
    for pattern, gen, family in _INTEL_GEN_RULES:
        if pattern.search(b):
            return gen, family
    return 0, ""


# Intel iGPU PCI device ids -> Core generation. A fallback for when the brand
# string can't be parsed (odd OEM strings, VMs, generic CPUID names, or a
# naming scheme _INTEL_GEN_RULES doesn't know yet) but an Intel iGPU is
# present. Each selector is either a contiguous `range` or, for generations
# whose ids Intel didn't allocate contiguously (Alder Lake's H/P/U parts,
# Raptor Lake-U), a `frozenset` of the exact ids -- both support `in`
# identically, so `intel_gen_from_igpu` doesn't need to care which.
_IGPU_GEN_IDS: tuple[tuple[range | frozenset[int], int, str], ...] = (
    (range(0x0100, 0x0131), 2,  "Sandy Bridge"),
    (range(0x0150, 0x0180), 3,  "Ivy Bridge"),
    (range(0x0400, 0x0D40), 4,  "Haswell"),
    (range(0x1600, 0x1640), 5,  "Broadwell"),
    (range(0x1900, 0x1940), 6,  "Skylake"),
    (range(0x5900, 0x5940), 7,  "Kaby Lake"),
    (range(0x87C0, 0x87D0), 7,  "Kaby Lake"),
    (range(0x3E90, 0x3EB0), 8,  "Coffee Lake"),
    (range(0x9B00, 0x9C00), 10, "Comet Lake"),
    (range(0x8A50, 0x8A80), 10, "Ice Lake"),
    (range(0x9A40, 0x9A79), 11, "Tiger Lake"),
    (frozenset({0x4626, 0x4628, 0x462A, *range(0x46A0, 0x46A4), 0x46A6, 0x46A8,
                0x46AA, *range(0x46B0, 0x46B4), *range(0x46C0, 0x46C4)}),
     12, "Alder Lake"),
    (range(0x46D0, 0x46D5), 12, "Alder Lake-N"),
    (frozenset({0xA721, 0xA7A1, 0xA7A9, 0xA7AC, 0xA7AD}), 13, "Raptor Lake"),
)


def intel_gen_from_igpu(device_hex: str) -> tuple[int, str]:
    """(generation, family) inferred from an Intel iGPU device id, else (0, "")."""
    try:
        dev = int(device_hex, 16)
    except (TypeError, ValueError):
        return 0, ""
    for ids, gen, family in _IGPU_GEN_IDS:
        if dev in ids:
            return gen, family
    return 0, ""


def backfill_intel_gen(machine) -> None:
    """If the CPU generation is unknown but there's an Intel iGPU, take the
    generation from the iGPU device id. Mutates ``machine`` in place."""
    from ocforge.model import Vendor

    cpu = machine.cpu
    if cpu.vendor is not Vendor.INTEL or cpu.intel_gen:
        return
    ig = machine.igpu
    if ig is None or ig.vendor is not Vendor.INTEL:
        return
    gen, family = intel_gen_from_igpu(ig.pci.device)
    if gen:
        cpu.intel_gen = gen
        if not cpu.family:
            cpu.family = family


# --- AMD Zen family from a brand string -------------------------------------


def amd_family(brand: str) -> str:
    b = brand.lower()
    m = re.search(r"ryzen(?:\s+ai)?(?:\s+\w+)?\s+(\d)\s*(\d{3})", b)
    if not m:
        if "threadripper" in b:
            return "Zen (Threadripper)"
        return "Zen" if "ryzen" in b else ""
    series = int(m.group(1) + m.group(2))
    if "ryzen ai" in b or series >= 9000:
        return "Zen 5"
    if series >= 8000:
        return "Zen 4"
    if series >= 7000:
        return "Zen 4"
    if series >= 6000:
        return "Zen 3+"
    if series >= 5000:
        return "Zen 3"
    if series >= 3000:
        return "Zen 2"
    return "Zen+"


def is_legacy_amd(m) -> bool:
    """True for pre-Zen AMD -- Bulldozer/Piledriver/Steamroller/Excavator
    (Family 15h) and Jaguar/Puma (Family 16h). ocforge can't reliably name
    every FX-/A-series/E-series/GX- SKU across that decade of confusingly
    reused branding, so this is the inverse of the reliable signal instead:
    genuinely-AMD hardware that amd_family() didn't recognize as Zen.

    Matters because the config is meaningfully different (Dortania
    Bulldozer/Jaguar vs Ryzen/Threadripper): no AMDRyzenCPUPowerManagement/
    SMCAMDProcessor/ForgedInvariant (catalog/kexts.py), and the legacy
    memory map by default, not the modern MAT-based one (build/config.py).
    """
    from ocforge.model import Vendor

    return m.cpu.vendor is Vendor.AMD and not m.cpu.family
