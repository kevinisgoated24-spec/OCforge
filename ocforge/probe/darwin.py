"""macOS host probe (sysctl + system_profiler -json)."""

from __future__ import annotations

import json

from ocforge.model import (
    Chassis,
    Cpu,
    Firmware,
    Gpu,
    Input,
    Machine,
    NetIf,
    PciId,
    Storage,
    Vendor,
)
from ocforge.probe.base import amd_family, intel_generation, run, vendor_from_text


def _sysctl(key: str) -> str:
    return run(["sysctl", "-n", key]).strip()


def _hex_id(val: str) -> str:
    return val.lower().removeprefix("0x").zfill(4) if val else ""


def parse_displays(sp_json: str) -> tuple[Gpu | None, Gpu | None]:
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


def probe() -> Machine:
    brand = _sysctl("machdep.cpu.brand_string")
    vraw = _sysctl("machdep.cpu.vendor").lower()
    vendor = Vendor.INTEL if "intel" in vraw or "genuineintel" in vraw else (
        Vendor.AMD if "amd" in vraw or "authenticamd" in vraw else vendor_from_text(brand)
    )
    gen, family = (intel_generation(brand) if vendor is Vendor.INTEL else (0, amd_family(brand)))
    try:
        cores = int(_sysctl("hw.physicalcpu") or 0)
        threads = int(_sysctl("hw.logicalcpu") or 0)
    except ValueError:
        cores = threads = 0
    cpu = Cpu(brand=brand, vendor=vendor, family=family, intel_gen=gen, cores=cores, threads=threads)

    igpu, dgpu = parse_displays(run(["system_profiler", "-json", "SPDisplaysDataType"]))

    model_id = ""
    try:
        hw = json.loads(run(["system_profiler", "-json", "SPHardwareDataType"]))
        model_id = (hw.get("SPHardwareDataType") or [{}])[0].get("machine_model", "")
    except (json.JSONDecodeError, IndexError, AttributeError):
        pass
    chassis = Chassis.LAPTOP if "book" in model_id.lower() else Chassis.DESKTOP if model_id else Chassis.UNKNOWN

    return Machine(
        chassis=chassis,
        cpu=cpu,
        igpu=igpu,
        dgpu=dgpu,
        net=[NetIf(name="", vendor=Vendor.UNKNOWN)] if False else [],
        storage=Storage(has_nvme=True),  # every Mac-era target has NVMe; refined later
        inputs=Input(has_touchpad=chassis is Chassis.LAPTOP, touchpad_bus="i2c-hid" if chassis is Chassis.LAPTOP else ""),
        firmware=Firmware(board_name=model_id),
    )
