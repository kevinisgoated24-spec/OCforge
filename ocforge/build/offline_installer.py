"""Stage a corpnewt/UnPlugged offline-installer payload.

UnPlugged lets you install macOS from a USB with **no internet connection
during the actual install** — you still need internet once, on the host
machine, to download the installer and recovery boot image, but the target
machine never touches the network. Useful for a spotty connection, a slow
one, or a machine you'd rather not point at Apple's servers mid-install.

What ocforge can do host-side: download the full installer (via gibMacOS)
and the recovery boot image, and lay them out exactly where UnPlugged/macOS
Recovery expect them. What it can't do: run UnPlugged itself — that's a
bash script meant to run *inside* a booted macOS Recovery environment, using
APIs (`diskutil`, `installer`, `asr`) that only exist there. You still boot
the USB and run `./UnPlugged.command` yourself in Recovery Terminal; see
README.md's "Offline installer" section for the exact steps.

Two-partition layout this stages, from corpnewt/UnPlugged's README:

    FAT32 partition  (~1 GB, boots via OpenCore)
        EFI/                          — ocforge's usual output
        com.apple.recovery.boot/      — BaseSystem.dmg (+ .chunklist)

    ExFAT partition  (remaining space, allocation unit <=1024 KB)
        InstallAssistant.pkg          — the real target-version installer
        UnPlugged.command

Sonoma (14) and newer can't mount FAT32/ExFAT in their own Recovery, so the
*boot* environment deliberately uses an older BaseSystem (Monterey, per
UnPlugged's README) even when the *install payload* targets something much
newer — that split is intentional, not a mismatch.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from ocforge.build.plan import BuildPlan
from ocforge.fetch import gibmacos
from ocforge.fetch import recovery as fetch_recovery
from ocforge.fetch import unplugged

# UnPlugged's own compatibility note (see module docstring).
_MIN_SONOMA_MAJOR = 14
_BOOT_BASESYSTEM_MAJOR = 12  # Monterey


class OfflineInstallerError(RuntimeError):
    pass


@dataclass
class OfflineInstallerReport:
    exfat_dir: Path
    recovery_boot: Path
    installer_pkg: Path
    unplugged_script: Path
    boot_major: int
    notes: list[str] = field(default_factory=list)


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def stage(plan: BuildPlan, work: Path, out: Path, *, log=lambda _: None) -> OfflineInstallerReport:
    """Downloads the installer + recovery boot image and lays them out under
    ``out`` (``out/ExFAT/…`` and ``out/com.apple.recovery.boot/…``). Doesn't
    touch ``out/EFI`` — pair this with ``build_efi`` for that."""
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    exfat = out / "ExFAT"
    exfat.mkdir(exist_ok=True)

    major = plan.target.major
    notes: list[str] = []

    log(f"downloading the macOS {major} installer via gibMacOS (large — this is the slow part)…")
    pkg = gibmacos.download_installer(work, str(major))
    dest_pkg = exfat / "InstallAssistant.pkg"
    _copy(pkg, dest_pkg)

    log("fetching UnPlugged.command…")
    script = unplugged.fetch(work)
    dest_script = exfat / "UnPlugged.command"
    _copy(script, dest_script)
    dest_script.chmod(0o755)

    boot_major = _BOOT_BASESYSTEM_MAJOR if major >= _MIN_SONOMA_MAJOR else major
    if boot_major != major:
        notes.append(
            f"macOS {major} Recovery can't mount FAT32/ExFAT itself, so the boot "
            f"environment uses macOS {boot_major}'s recovery image instead of "
            f"{major}'s — expected, not a mismatch (see corpnewt/UnPlugged's README)."
        )

    log(f"downloading the macOS {boot_major} recovery boot image…")
    recovery_boot = fetch_recovery.download(
        boot_major, work / "opencore", out, work=work
    )

    notes.append(
        "Format the target USB with a FAT32 partition (EFI/ + "
        "com.apple.recovery.boot/) and an ExFAT partition (allocation unit "
        "<=1024 KB) holding everything under ExFAT/, then boot it, open "
        "Terminal in Recovery, cd to the ExFAT volume, and run "
        "./UnPlugged.command — it walks you through the rest."
    )

    return OfflineInstallerReport(
        exfat_dir=exfat,
        recovery_boot=recovery_boot,
        installer_pkg=dest_pkg,
        unplugged_script=dest_script,
        boot_major=boot_major,
        notes=notes,
    )
