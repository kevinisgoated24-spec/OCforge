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
    (re.compile(r"\bcore\s+ultra\s+\d\s+2\d\d"), 15, "Arrow Lake"),
    (re.compile(r"\bcore\s+ultra\s+\d\s+1\d\d"), 14, "Meteor Lake"),
    (re.compile(r"\bi[3579]-14\d\d\d"), 14, "Raptor Lake Refresh"),
    (re.compile(r"\bi[3579]-13\d\d\d"), 13, "Raptor Lake"),
    (re.compile(r"\bi[3579]-12\d\d\d"), 12, "Alder Lake"),
    (re.compile(r"\bi[3579]-11\d\d\d"), 11, "Rocket/Tiger Lake"),
    (re.compile(r"\bi[3579]-10\d\d\d"), 10, "Comet/Ice Lake"),
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


# Intel iGPU PCI device-id ranges -> Core generation. A fallback for when the
# brand string can't be parsed (odd OEM strings, VMs, generic CPUID names) but
# an Intel iGPU is present.
_IGPU_GEN_RANGES: tuple[tuple[int, int, int, str], ...] = (
    (0x0100, 0x0130, 2,  "Sandy Bridge"),
    (0x0150, 0x017F, 3,  "Ivy Bridge"),
    (0x0400, 0x0D3F, 4,  "Haswell"),
    (0x1600, 0x163F, 5,  "Broadwell"),
    (0x1900, 0x193F, 6,  "Skylake"),
    (0x5900, 0x593F, 7,  "Kaby Lake"),
    (0x87C0, 0x87CF, 7,  "Kaby Lake"),
    (0x3E90, 0x3EAF, 8,  "Coffee Lake"),
    (0x9B00, 0x9BFF, 10, "Comet Lake"),
    (0x8A50, 0x8A7F, 10, "Ice Lake"),
)


def intel_gen_from_igpu(device_hex: str) -> tuple[int, str]:
    """(generation, family) inferred from an Intel iGPU device id, else (0, "")."""
    try:
        dev = int(device_hex, 16)
    except (TypeError, ValueError):
        return 0, ""
    for lo, hi, gen, family in _IGPU_GEN_RANGES:
        if lo <= dev <= hi:
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
