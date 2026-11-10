"""macOS host probe.

Who runs ocforge on a Mac: someone already on a working Hackintosh who wants
to rebuild/upgrade their EFI (probing the box itself), or someone on any Mac
building for a *different* PC (that's ``--spec``, not this module).

Inputs: ``sysctl`` for the CPU, ``ioreg -a`` (plist output, so no text
scraping) for the PCI bus — GPUs, NICs, NVMe — and ``system_profiler -json``
for nicer GPU names and the model identifier. The PCI list is mapped through
the Linux probe's :func:`~ocforge.probe.linux.build_machine` so both hosts
classify hardware identically. Parse helpers are pure and fixture-tested.

Apple Silicon can't run OpenCore at all, so probing one is refused with a
pointer to ``--spec`` instead of returning a nonsense Machine.
"""

from __future__ import annotations

import json
import plistlib
import re
import subprocess
from xml.parsers.expat import ExpatError

from ocforge.model import Chassis, Cpu, Firmware, Gpu, Input, Machine, PciId, Vendor
from ocforge.probe.base import amd_family, intel_generation, run, vendor_from_text
from ocforge.probe.linux import PciDevice, build_machine


class AppleSiliconHost(RuntimeError):
    pass


def _sysctl(key: str) -> str:
    return run(["sysctl", "-n", key]).strip()


def _hex_id(val: str) -> str:
    return val.lower().removeprefix("0x").zfill(4) if val else ""


# --- CPU ---------------------------------------------------------------------

# machdep.cpu.features / leaf7_features tokens -> the Linux-style flag names
# the rest of ocforge (catalog/macos.py) checks for.
_FEATURE_MAP = {
    "SSE4.2": "sse4_2",
    "SSE4A": "sse4a",
    "AVX1.0": "avx",
    "AVX2": "avx2",
    "BMI1": "bmi1",
    "BMI2": "bmi2",
    "AES": "aes",
    "RDRAND": "rdrand",
}


def parse_cpu_features(features: str) -> frozenset[str]:
    return frozenset(_FEATURE_MAP[t] for t in features.upper().split() if t in _FEATURE_MAP)


def is_apple_silicon(arm64_flag: str, brand: str) -> bool:
    """``hw.optional.arm64`` is 1 on Apple Silicon even for a Rosetta-translated
    Python, which is what we want: it's the *hardware* that can't run OpenCore."""
    return arm64_flag.strip() == "1" or brand.strip().startswith("Apple ")


def _cpu() -> Cpu:
    brand = _sysctl("machdep.cpu.brand_string")
    if is_apple_silicon(_sysctl("hw.optional.arm64"), brand):
        raise AppleSiliconHost(
            f"this is an Apple Silicon Mac ({brand or 'arm64'}) — OpenCore only "
            "boots x86 PCs, so there's nothing here to probe. Build for the target "
            "PC instead: run `ocforge probe --save my-pc.json` on it (Windows/Linux "
            "work fine), then `ocforge build --spec my-pc.json` here."
        )
    vraw = _sysctl("machdep.cpu.vendor").lower()
    vendor = Vendor.INTEL if "intel" in vraw else (
        Vendor.AMD if "amd" in vraw else vendor_from_text(brand)
    )
    gen, family = intel_generation(brand) if vendor is Vendor.INTEL else (0, amd_family(brand))
    try:
        cores = int(_sysctl("hw.physicalcpu") or 0)
        threads = int(_sysctl("hw.logicalcpu") or 0)
    except ValueError:
        cores = threads = 0
    flags = parse_cpu_features(
        f"{_sysctl('machdep.cpu.features')} {_sysctl('machdep.cpu.leaf7_features')}"
    )
    return Cpu(brand=brand, vendor=vendor, family=family, intel_gen=gen,
               cores=cores, threads=threads, flags=flags)


# --- PCI via ioreg -----------------------------------------------------------

_PCIDEBUG = re.compile(r"^\s*(\d+):(\d+):(\d+)")


def _le_hex(val, width: int = 4) -> str:
    """ioreg PCI ids are little-endian ``data`` (4 bytes for a 16-bit id)."""
    if isinstance(val, bytes) and val:
        return f"{int.from_bytes(val, 'little'):0{width}x}"[-width:]
    if isinstance(val, int):
        return f"{val:0{width}x}"[-width:]
    return ""


def _text(val) -> str:
    if isinstance(val, bytes):
        return val.split(b"\x00", 1)[0].decode("utf-8", "replace").strip()
    return str(val).strip() if val else ""


def _walk(node):
    """Every dict in an ioreg plist, depth-first (``-r`` output is a list of
    matched entries, each possibly carrying ``IORegistryEntryChildren``)."""
    if isinstance(node, dict):
        yield node
        for child in node.get("IORegistryEntryChildren", ()):
            yield from _walk(child)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def load_ioreg_plist(raw: bytes):
    if not raw.strip():
        return []
    try:
        return plistlib.loads(raw)
    except (plistlib.InvalidFileException, ValueError, ExpatError):
        return []


def parse_ioreg_pci(raw: bytes) -> list[PciDevice]:
    """``ioreg -a -r -c IOPCIDevice`` -> the same :class:`PciDevice` records
    the Linux probe builds from lspci."""
    out: list[PciDevice] = []
    for d in _walk(load_ioreg_plist(raw)):
        ven, dev, cls = d.get("vendor-id"), d.get("device-id"), d.get("class-code")
        if ven is None or dev is None or cls is None:
            continue
        # class-code is 0xCCSSPP (class, subclass, prog-if) in LE data; the
        # Linux side compares 4-hex "CCSS" for most classes and "0108" NVMe.
        full = int(_le_hex(cls, 8) or "0", 16)
        cls4 = f"{(full >> 8) & 0xFFFF:04x}"
        m = _PCIDEBUG.match(_text(d.get("pcidebug", "")))
        slot = f"{int(m[1]):02x}:{int(m[2]):02x}.{int(m[3])}" if m else ""
        sven, sdev = _le_hex(d.get("subsystem-vendor-id")), _le_hex(d.get("subsystem-id"))
        out.append(PciDevice(
            slot=slot,
            cls=cls4,
            vendor_id=_le_hex(ven),
            device_id=_le_hex(dev),
            sub=f"{sven}{sdev}" if sven and sdev else "",
            name=_text(d.get("model")) or _text(d.get("IOName")) or _text(d.get("name")),
            vendor_name="",
        ))
    return out


def parse_displays(sp_json: str) -> tuple[Gpu | None, Gpu | None]:
    """system_profiler's view of the GPUs — used for names, and as the whole
    GPU answer if ioreg came back empty."""
    igpu = dgpu = None
    try:
        items = json.loads(sp_json).get("SPDisplaysDataType", [])
    except (json.JSONDecodeError, AttributeError):
        return None, None
    for it in items:
        name = it.get("sppci_model") or it.get("_name") or ""
        v = vendor_from_text(name)
        pci = PciId(_hex_id(it.get("spdisplays_vendor-id", "")), _hex_id(it.get("spdisplays_device-id", "")))
        bus = (it.get("sppci_bus") or "").lower()
        discrete = v is Vendor.NVIDIA or "pcie" in bus or it.get("sppci_device_type") == "spdisplays_egpu"
        gpu = Gpu(name=name.strip(), vendor=v, pci=pci, discrete=discrete)
        if discrete and dgpu is None:
            dgpu = gpu
        elif not discrete and igpu is None:
            igpu = gpu
        elif dgpu is None:
            dgpu = gpu
    return igpu, dgpu


def _named(gpu: Gpu | None, sp: tuple[Gpu | None, Gpu | None]) -> Gpu | None:
    """Prefer system_profiler's marketing name for a PCI-found GPU."""
    if gpu is None:
        return None
    for g in sp:
        if g is not None and g.name and g.pci.device == gpu.pci.device:
            return Gpu(name=g.name, vendor=gpu.vendor, pci=gpu.pci, discrete=gpu.discrete)
    return gpu


# --- chassis / input ---------------------------------------------------------

def chassis_from(model_id: str, has_battery: bool) -> Chassis:
    if has_battery or "book" in model_id.lower():
        return Chassis.LAPTOP
    return Chassis.DESKTOP if model_id else Chassis.UNKNOWN


def touchpad_from_ioreg(classes: str) -> Input:
    """Which trackpad driver stack is loaded tells us the bus on a Hackintosh."""
    c = classes.lower()
    if "voodooi2c" in c:
        return Input(has_touchpad=True, touchpad_bus="i2c-hid")
    if "voodoormi" in c or "voodoosmbus" in c:
        return Input(has_touchpad=True, touchpad_bus="smbus")
    if "appleps2" in c or "voodoops2" in c:
        return Input(has_touchpad=True, touchpad_bus="ps2")
    return Input()


def probe() -> Machine:
    cpu = _cpu()

    sp = parse_displays(run(["system_profiler", "-json", "SPDisplaysDataType"], timeout=40))
    pci = parse_ioreg_pci(run_bytes(["ioreg", "-a", "-r", "-c", "IOPCIDevice"]))

    model_id = ""
    try:
        hw = json.loads(run(["system_profiler", "-json", "SPHardwareDataType"], timeout=40))
        model_id = (hw.get("SPHardwareDataType") or [{}])[0].get("machine_model", "")
    except (json.JSONDecodeError, IndexError, AttributeError):
        pass
    has_battery = bool(run(["ioreg", "-r", "-c", "AppleSmartBattery", "-d", "1"]).strip())
    chassis = chassis_from(model_id, has_battery)

    inputs = Input()
    if chassis is Chassis.LAPTOP:
        kexts = run(["kextstat", "-l"], timeout=20) or run(["kmutil", "showloaded"], timeout=30)
        inputs = touchpad_from_ioreg(kexts)
        if not inputs.has_touchpad:  # laptop, unknown stack — the common modern case
            inputs = Input(has_touchpad=True, touchpad_bus="i2c-hid")

    m = build_machine(pci, cpu, chassis, Firmware(board_name=model_id), inputs)
    if not pci:  # ioreg unavailable/empty — fall back to system_profiler GPUs
        m.igpu, m.dgpu = sp
    else:
        m.igpu, m.dgpu = _named(m.igpu, sp), _named(m.dgpu, sp)
    return m


def run_bytes(argv: list[str], *, timeout: int = 30) -> bytes:
    try:
        return subprocess.run(argv, capture_output=True, timeout=timeout, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return b""
