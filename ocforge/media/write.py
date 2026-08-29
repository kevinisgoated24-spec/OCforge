"""Format a USB GPT/FAT32 (or FAT32+ExFAT) and write the payload onto it.

Field-untested — the format/mount calls are destructive and OS-specific, so
they only run when you pass ``--usb`` to ``ocforge build``/``offline-installer``
and confirm.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LABEL = "OCFORGE"
LABEL_EXFAT = "UNPLUGGED"
FAT32_PART_SIZE_MIB = 1024  # dual-partition layout: FAT32 gets 1 GiB, ExFAT gets the rest


class MediaError(RuntimeError):
    pass


def _run(argv: list[str], *, input_text: str | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    try:
        p = subprocess.run(argv, input=input_text, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise MediaError(f"{argv[0]} not found — is it installed?") from exc
    if p.returncode != 0:
        raise MediaError(f"{argv[0]} failed ({p.returncode}):\n{(p.stdout + p.stderr)[-800:]}")
    return p


# --- format → returns a mounted, writable directory -----------------------


def _format_linux(dev: str) -> Path:
    if not any(t in dev for t in ("/dev/sd", "/dev/nvme", "/dev/mmcblk")):
        raise MediaError(f"refusing to format {dev!r}")
    _run(["sgdisk", "--zap-all", dev])
    _run(["sgdisk", "-n", "1:0:0", "-t", "1:0700", "-c", f"1:{LABEL}", dev])
    _run(["partprobe", dev])
    part = f"{dev}p1" if ("nvme" in dev or "mmcblk" in dev) else f"{dev}1"
    for _ in range(10):
        if Path(part).exists():
            break
        time.sleep(0.5)
    _run(["mkfs.fat", "-F", "32", "-n", LABEL, part])
    mnt = Path(tempfile.mkdtemp(prefix="ocforge-usb-"))
    _run(["mount", part, str(mnt)])
    return mnt


def _format_darwin(dev: str) -> Path:
    _run(["diskutil", "eraseDisk", "FAT32", LABEL, "GPT", dev])
    return Path(f"/Volumes/{LABEL}")


def _format_windows(disk_number: str) -> Path:
    script = "\n".join([
        f"select disk {disk_number}",
        "clean",
        "convert gpt",
        "create partition primary",
        f"format fs=fat32 quick label={LABEL}",
        "assign",
        "exit",
    ])
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write(script)
        sp = fh.name
    try:
        _run(["diskpart", "/s", sp])
    finally:
        Path(sp).unlink(missing_ok=True)
    out = _run([
        "powershell", "-NoProfile", "-Command",
        f"(Get-Volume -FileSystemLabel {LABEL}).DriveLetter",
    ]).stdout.strip()
    if not out:
        raise MediaError("formatted volume has no drive letter")
    return Path(f"{out}:\\")


def format_and_mount(device: str) -> Path:
    if sys.platform.startswith("linux"):
        return _format_linux(device)
    if sys.platform == "darwin":
        return _format_darwin(device)
    if sys.platform == "win32":
        return _format_windows(device)
    raise MediaError(f"unsupported host {sys.platform}")


def unmount(device: str) -> None:
    try:
        if sys.platform.startswith("linux"):
            subprocess.run(["umount", device + "1"], capture_output=True, timeout=30, check=False)
        elif sys.platform == "darwin":
            subprocess.run(["diskutil", "unmountDisk", device], capture_output=True, timeout=30, check=False)
    except OSError:
        pass


# --- dual-partition (FAT32 + ExFAT) format, for the offline installer -----
#
# ExFAT formatting needs a tool ocforge doesn't otherwise depend on:
# exfatprogs/exfat-utils' `mkfs.exfat` on Linux (`sudo apt install
# exfatprogs`). macOS and Windows can format ExFAT out of the box. None of
# these calls pin an allocation-unit size — every tool's own size-based
# default already lands well under UnPlugged's <=1024 KB requirement for a
# typical USB stick, so there's nothing to override.


def _format_linux_dual(dev: str) -> tuple[Path, Path]:
    if not any(t in dev for t in ("/dev/sd", "/dev/nvme", "/dev/mmcblk")):
        raise MediaError(f"refusing to format {dev!r}")
    _run(["sgdisk", "--zap-all", dev])
    _run(["sgdisk", "-n", f"1:0:+{FAT32_PART_SIZE_MIB}MiB", "-t", "1:0700", "-c", f"1:{LABEL}", dev])
    _run(["sgdisk", "-n", "2:0:0", "-t", "2:0700", "-c", f"2:{LABEL_EXFAT}", dev])
    _run(["partprobe", dev])
    sep = "p" if ("nvme" in dev or "mmcblk" in dev) else ""
    part1, part2 = f"{dev}{sep}1", f"{dev}{sep}2"
    for p in (part1, part2):
        for _ in range(10):
            if Path(p).exists():
                break
            time.sleep(0.5)
    _run(["mkfs.fat", "-F", "32", "-n", LABEL, part1])
    _run(["mkfs.exfat", "-n", LABEL_EXFAT, part2])
    mnt1 = Path(tempfile.mkdtemp(prefix="ocforge-usb-fat32-"))
    mnt2 = Path(tempfile.mkdtemp(prefix="ocforge-usb-exfat-"))
    _run(["mount", part1, str(mnt1)])
    _run(["mount", part2, str(mnt2)])
    return mnt1, mnt2


def _format_darwin_dual(dev: str) -> tuple[Path, Path]:
    _run([
        "diskutil", "partitionDisk", dev, "2", "GPT",
        "FAT32", LABEL, f"{FAT32_PART_SIZE_MIB}MiB",
        "ExFAT", LABEL_EXFAT, "R",
    ])
    return Path(f"/Volumes/{LABEL}"), Path(f"/Volumes/{LABEL_EXFAT}")


def _format_windows_dual(disk_number: str) -> tuple[Path, Path]:
    script = "\n".join([
        f"select disk {disk_number}",
        "clean",
        "convert gpt",
        f"create partition primary size={FAT32_PART_SIZE_MIB}",
        f"format fs=fat32 quick label={LABEL}",
        "assign",
        "create partition primary",
        f"format fs=exfat quick label={LABEL_EXFAT}",
        "assign",
        "exit",
    ])
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write(script)
        sp = fh.name
    try:
        _run(["diskpart", "/s", sp])
    finally:
        Path(sp).unlink(missing_ok=True)
    letters = {}
    for label in (LABEL, LABEL_EXFAT):
        out = _run([
            "powershell", "-NoProfile", "-Command",
            f"(Get-Volume -FileSystemLabel {label}).DriveLetter",
        ]).stdout.strip()
        if not out:
            raise MediaError(f"formatted {label} volume has no drive letter")
        letters[label] = Path(f"{out}:\\")
    return letters[LABEL], letters[LABEL_EXFAT]


def format_and_mount_dual(device: str) -> tuple[Path, Path]:
    """Formats ``device`` GPT with a 1 GiB FAT32 partition + an ExFAT
    partition using the rest, per corpnewt/UnPlugged's layout. Returns
    ``(fat32_mount, exfat_mount)``."""
    if sys.platform.startswith("linux"):
        return _format_linux_dual(device)
    if sys.platform == "darwin":
        return _format_darwin_dual(device)
    if sys.platform == "win32":
        return _format_windows_dual(device)
    raise MediaError(f"unsupported host {sys.platform}")


def unmount_dual(device: str) -> None:
    try:
        if sys.platform.startswith("linux"):
            subprocess.run(["umount", device + "1"], capture_output=True, timeout=30, check=False)
            subprocess.run(["umount", device + "2"], capture_output=True, timeout=30, check=False)
        elif sys.platform == "darwin":
            subprocess.run(["diskutil", "unmountDisk", device], capture_output=True, timeout=30, check=False)
    except OSError:
        pass


# --- copy payloads ---------------------------------------------------------


def _copytree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        t = dst / item.name
        if item.is_dir():
            _copytree(item, t)
        else:
            shutil.copy2(item, t)


def write_payload(mount: Path, efi_dir: Path, recovery_boot: Path | None) -> None:
    _copytree(efi_dir, mount / "EFI")
    if recovery_boot and recovery_boot.is_dir():
        _copytree(recovery_boot, mount / "com.apple.recovery.boot")


def write_offline_payload(fat32_mount: Path, exfat_mount: Path, *, efi_dir: Path,
                          recovery_boot: Path, exfat_dir: Path) -> None:
    _copytree(efi_dir, fat32_mount / "EFI")
    _copytree(recovery_boot, fat32_mount / "com.apple.recovery.boot")
    _copytree(exfat_dir, exfat_mount)
