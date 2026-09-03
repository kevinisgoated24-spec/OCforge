"""Scans an OpenCore boot log (or a macOS panic report) for known trouble
signatures and explains each one.

The signatures themselves come straight from Dortania's own troubleshooting
guide (``OpenCore-Install-Guide/troubleshooting/boot.md``) -- this is
deliberately a small, curated list, not an attempt at an exhaustive boot-log
parser. A clean scan is not proof the boot actually succeeded; it only means
none of *these particular* known signatures showed up.

Two kinds of signature:

- **unambiguous errors** -- a real panic, or a message that only ever shows
  up when something's actually wrong. Safe to flag wherever it appears.
- **stall checkpoints** -- perfectly normal lines that show up on *every*
  boot, successful or not (PCI enumeration, IOConsoleUsers, ...). These only
  mean anything if the log stops right there -- they're only flagged when
  they're at (or very near) the end of the log, i.e. the last thing it
  printed before whatever was pasted here cuts off.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LogFinding:
    title: str
    explanation: str
    suggestion: str
    line_no: int
    line: str


@dataclass(frozen=True)
class _Signature:
    pattern: re.Pattern[str]
    title: str
    explanation: str
    suggestion: str
    stall_only: bool = False  # only meaningful as the log's last checkpoint


_SIGNATURES: tuple[_Signature, ...] = (
    _Signature(
        re.compile(r"no vault provided!", re.IGNORECASE),
        "No vault provided",
        "OpenCore couldn't verify its own vault/signature this early in boot.",
        "Re-check OpenCore/Vault in config.plist, or rebuild the EFI from "
        "scratch — this usually means a corrupted or hand-edited OpenCore folder.",
    ),
    _Signature(
        re.compile(r"Couldn'?t allocate runtime area"),
        "Couldn't allocate runtime area (KASLR slide)",
        "The kernel couldn't find a free memory region to load into — common "
        "on Z390/X99/X299 boards with a lot of PCI devices installed.",
        "Add a slide=N boot-arg (Dortania's KASLR-fix guide walks through "
        "finding a working N) instead of letting macOS pick a random slide "
        "each boot.",
    ),
    _Signature(
        re.compile(r"Cannot perform kext summary"),
        "Cannot perform kext summary",
        "A kext failed to load in a way that stopped the kernel from even "
        "listing what's loaded — usually one specific bad/incompatible kext.",
        "Check Kernel → Add in config.plist against this hardware; --debug "
        "on `ocforge build` gets you a DEBUG OpenCore build with more detail.",
    ),
    _Signature(
        re.compile(r"Invalid frame pointer"),
        "Invalid frame pointer",
        "A kernel-level memory fault during early kernel init — often an "
        "ACPI table or kext mismatch for this hardware.",
        "Cross-check the SSDTs and kexts ocforge selected (`ocforge explain`) "
        "against the Dortania guide page for this CPU generation.",
    ),
    _Signature(
        re.compile(r"panic\(cpu \d+ caller|Debugger message: panic"),
        "Kernel panic",
        "macOS itself panicked — this is a real panic report, not just a stall.",
        "Read the panic string right after this line for the actual subsystem "
        "(e.g. AppleIntelCPUPowerManagement, AppleACPIPlatform) and search "
        "that against the Dortania guide for this hardware.",
    ),
    _Signature(
        re.compile(r"\[EB\|#LOG:EXITBS:START\]"),
        "Stalled exiting boot services",
        "The last thing printed was OpenCore handing off to the kernel — the "
        "kernel itself never took over.",
        "Often a Booter Quirks mismatch (DevirtualiseMmio, ForceExitBootServices) "
        "for this board; try one with `ocforge build --quirk NAME=true|false`.",
        stall_only=True,
    ),
    _Signature(
        re.compile(r"kextd stall\[0\]: AppleACPICPU"),
        "Stalled waiting on AppleACPICPU (SMC)",
        "The kernel is waiting on a VirtualSMC key that never showed up.",
        "Check VirtualSMC (and SMCProcessor/SMCSuperIO/SMCBatteryManager as "
        "applicable) actually loaded — see the kext list in `ocforge explain`.",
        stall_only=True,
    ),
    _Signature(
        re.compile(r"Waiting for [Rr]oot [Dd]evice|prohibited sign", re.IGNORECASE),
        "Waiting for root device",
        "macOS can't find the disk to boot from — either the boot disk's "
        "controller has no driver, or a USB drive isn't mapped/recognized yet.",
        "For NVMe, check NVMeFix loaded; for a USB installer, re-check USB "
        "port mapping (UTBMap.kext) — see the guide's USB mapping section.",
        stall_only=True,
    ),
    _Signature(
        re.compile(r"IOConsoleUsers: gIOScreenLock"),
        "Stalled at IOConsoleUsers (no display handoff)",
        "The kernel is up but nothing ever took over the display — a GPU/"
        "WhateverGreen mismatch for this hardware.",
        "Re-check DeviceProperties/boot-args for this GPU (`ocforge explain`) "
        "— an AMD Navi dGPU needs agdpmod=pikera, Intel needs the right "
        "AAPL,ig-platform-id for this generation.",
        stall_only=True,
    ),
    _Signature(
        re.compile(r"PCI Configuration Begins|Previous Shutdown Cause|^\s*HPET\b"),
        "Stalled early in PCI/ACPI enumeration",
        "The log stops during very early UEFI/ACPI hardware enumeration, "
        "before the kernel itself has even started.",
        "Usually a firmware setting (CFG-Lock, Above 4G Decoding, VT-d) — "
        "see `ocforge bios` for this machine's checklist.",
        stall_only=True,
    ),
)

# How many trailing non-blank lines count as "the log's end" for a
# stall-only signature.
_STALL_WINDOW = 5


def scan(text: str) -> list[LogFinding]:
    """Returns at most one :class:`LogFinding` per signature that matched,
    in the order the signatures are defined above (roughly boot order)."""
    lines = text.splitlines()
    non_blank_idx = [i for i, line in enumerate(lines) if line.strip()]
    tail = set(non_blank_idx[-_STALL_WINDOW:])

    out: list[LogFinding] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        for sig in _SIGNATURES:
            if sig.title in seen:
                continue
            if sig.stall_only and i not in tail:
                continue
            if sig.pattern.search(line):
                out.append(LogFinding(sig.title, sig.explanation, sig.suggestion,
                                      i + 1, line.strip()))
                seen.add(sig.title)
    return out
