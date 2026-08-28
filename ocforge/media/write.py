"""Format a USB GPT/FAT32 and write the EFI + recovery onto it.

Field-untested — the format/mount calls are destructive and OS-specific, so
they only run when you pass ``--usb`` to ``ocforge build`` and confirm.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LABEL = "OCFORGE"


class MediaError(RuntimeError):
    pass


def _run(argv: list[str], *, input_text: str | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    p = subprocess.run(argv, input=input_text, capture_output=True, text=True, timeout=timeout, check=False)
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
