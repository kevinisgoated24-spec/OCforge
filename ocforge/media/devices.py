"""Enumerate removable USB block devices, per host OS.

Internal disks are never returned — you can't ``ocforge build --usb`` your
system drive.
"""

from __future__ import annotations

import json
import plistlib
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class UsbDisk:
    id: str          # /dev/sdb , /dev/disk3 , or a Windows disk number
    size_bytes: int
    label: str = ""

    @property
    def size_gib(self) -> float:
        return self.size_bytes / (1 << 30)

    def __str__(self) -> str:  # pragma: no cover
        lbl = f"  {self.label}" if self.label else ""
        return f"{self.id}  {self.size_gib:.1f} GiB{lbl}"


def _sh(argv: list[str]) -> str:
    return subprocess.run(argv, capture_output=True, text=True, timeout=20, check=False).stdout


def _linux() -> list[UsbDisk]:
    data = json.loads(_sh(["lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,TRAN,RM,LABEL"]))
    out = []
    for d in data.get("blockdevices", []):
        if d.get("type") == "disk" and d.get("tran") == "usb" and (d.get("rm") in (True, "1", 1)):
            out.append(UsbDisk(f"/dev/{d['name']}", int(d.get("size") or 0), d.get("label") or ""))
    return out


def _darwin() -> list[UsbDisk]:
    raw = subprocess.run(
        ["diskutil", "list", "-plist", "external", "physical"],
        capture_output=True, timeout=20, check=False,
    ).stdout
    plist = plistlib.loads(raw)
    out = []
    for whole in plist.get("WholeDisks", []):
        info = plistlib.loads(
            subprocess.run(["diskutil", "info", "-plist", whole], capture_output=True, timeout=10, check=False).stdout
        )
        if not info.get("RemovableMediaOrExternalDevice", True):
            continue
        out.append(UsbDisk(f"/dev/{whole}", int(info.get("TotalSize") or 0), info.get("MediaName") or ""))
    return out


def _windows() -> list[UsbDisk]:
    raw = _sh([
        "powershell", "-NoProfile", "-Command",
        "Get-Disk | Where-Object BusType -eq 'USB' | Select-Object Number,Size,FriendlyName | ConvertTo-Json",
    ])
    if not raw.strip():
        return []
    rows = json.loads(raw)
    if isinstance(rows, dict):
        rows = [rows]
    return [UsbDisk(str(r["Number"]), int(r.get("Size") or 0), r.get("FriendlyName") or "") for r in rows]


def list_usb() -> list[UsbDisk]:
    if sys.platform.startswith("linux"):
        return _linux()
    if sys.platform == "darwin":
        return _darwin()
    if sys.platform == "win32":
        return _windows()
    raise RuntimeError(f"USB enumeration not supported on {sys.platform}")
