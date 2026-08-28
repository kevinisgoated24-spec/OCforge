"""Assemble the EFI/ tree from an extracted OpenCore + fetched pieces."""

from __future__ import annotations

import plistlib
import shutil
from pathlib import Path
from typing import Any

_DRIVERS = ("OpenRuntime.efi", "ResetNvramEntry.efi")  # HfsPlus.efi comes from OcBinaryData
_KEEP_TOOLS: tuple[str, ...] = ()  # none by default


def _copytree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _copytree(item, target)
        else:
            shutil.copy2(item, target)


def scaffold(opencore_dir: Path, out: Path) -> Path:
    """Copy OpenCore's ``X64/EFI`` skeleton to ``out/EFI`` and clear the
    sample kexts/acpi/tools. Returns the ``EFI/OC`` path."""
    src_efi = opencore_dir / "X64" / "EFI"
    if not src_efi.is_dir():
        raise FileNotFoundError(f"{src_efi} missing — bad OpenCore extract")
    efi = out / "EFI"
    if efi.exists():
        shutil.rmtree(efi)
    _copytree(src_efi, efi)

    oc = efi / "OC"
    for sub in ("ACPI", "Kexts", "Tools"):
        d = oc / sub
        if d.exists():
            shutil.rmtree(d)
        d.mkdir()
    # start Drivers from scratch too — only add what the config lists
    drv = oc / "Drivers"
    keep = {}
    for name in _DRIVERS:
        p = opencore_dir / "X64" / "EFI" / "OC" / "Drivers" / name
        if p.exists():
            keep[name] = p.read_bytes()
    shutil.rmtree(drv)
    drv.mkdir()
    for name, data in keep.items():
        (drv / name).write_bytes(data)
    for stray in ("config.plist",):
        (oc / stray).unlink(missing_ok=True)
    return oc


def add_hfsplus(oc: Path, ocbinary_dir: Path) -> None:
    src = ocbinary_dir / "Drivers" / "HfsPlus.efi"
    if src.exists():
        shutil.copy2(src, oc / "Drivers" / "HfsPlus.efi")


def add_resources(oc: Path, ocbinary_dir: Path) -> None:
    res = ocbinary_dir / "Resources"
    if res.is_dir():
        dst = oc / "Resources"
        if dst.exists():
            shutil.rmtree(dst)
        _copytree(res, dst)


def place_kexts(oc: Path, bundle_dirs: list[Path]) -> None:
    for b in bundle_dirs:
        _copytree(b, oc / "Kexts" / b.name)


def place_acpi(oc: Path, aml_files: list[Path]) -> None:
    for a in aml_files:
        shutil.copy2(a, oc / "ACPI" / a.name)


def fixup_kext_paths(config: dict[str, Any], oc: Path) -> list[str]:
    """Rewrite each kext's ExecutablePath from the bundle actually on disk
    (a plist-only bundle gets an empty path). Returns names that changed."""
    changed = []
    for entry in config.get("Kernel", {}).get("Add", []):
        bp = entry.get("BundlePath", "")
        info = oc / "Kexts" / bp / "Contents" / "Info.plist"
        if not info.exists():
            continue
        try:
            exe = plistlib.loads(info.read_bytes()).get("CFBundleExecutable", "")
        except Exception:  # noqa: BLE001 - a mangled Info.plist shouldn't abort the build
            exe = ""
        want = f"Contents/MacOS/{exe}" if exe else ""
        if want and not (oc / "Kexts" / bp / want).exists():
            want = ""
        if entry.get("ExecutablePath") != want:
            entry["ExecutablePath"] = want
            changed.append(bp)
    return changed


def write_config(oc: Path, config: dict[str, Any]) -> Path:
    path = oc / "config.plist"
    with open(path, "wb") as fh:
        plistlib.dump(config, fh, fmt=plistlib.FMT_XML, sort_keys=False)
    return path


def prune_dead_acpi(config: dict[str, Any], oc: Path) -> int:
    """Drop ACPI/Add entries whose .aml never made it onto disk."""
    add = config.get("ACPI", {}).get("Add", [])
    before = len(add)
    config["ACPI"]["Add"] = [e for e in add if (oc / "ACPI" / e["Path"]).exists()]
    return before - len(config["ACPI"]["Add"])
