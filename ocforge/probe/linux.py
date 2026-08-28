"""Linux host probe.

Inputs: ``lspci -nnmm`` (machine-parseable PCI list), ``/proc/cpuinfo``,
``/sys/class/dmi/id/*``. The parse helpers are pure so they can be tested
against captured fixtures without a Linux box.
"""

from __future__ import annotations

import re
from pathlib import Path

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
from ocforge.probe.base import (
    amd_family,
    have,
    intel_generation,
    run,
    vendor_from_pci,
)

# A `lspci -nnmm` record. Every bracketed group is a lowercase hex id.
_LSPCI_LINE = re.compile(
    r'^(?P<slot>\S+)\s+'
    r'"(?P<cls_name>[^"]*)\s\[(?P<cls>[0-9a-fA-F]{4})\]"\s+'
    r'"(?P<ven_name>[^"]*)\s\[(?P<ven>[0-9a-fA-F]{4})\]"\s+'
    r'"(?P<dev_name>[^"]*)\s\[(?P<dev>[0-9a-fA-F]{4})\]"'
    r'(?:\s+-\w+)?'
    r'(?:\s+"[^"]*\s\[(?P<sven>[0-9a-fA-F]{4})\]")?'
    r'(?:\s+"[^"]*\s\[(?P<sdev>[0-9a-fA-F]{4})\]")?'
)

# PCI class prefixes (first byte of the 4-hex class)
_CLASS_DISPLAY = ("03",)          # VGA / 3D / display controllers
_CLASS_NETWORK = ("0200", "0280")  # ethernet, other network
_CLASS_NVME = ("0108",)


class PciDevice:
    __slots__ = ("cls", "device_id", "name", "slot", "sub", "vendor_id", "vendor_name")

    def __init__(self, slot, cls, vendor_id, device_id, sub, name, vendor_name):
        self.slot = slot
        self.cls = cls
        self.vendor_id = vendor_id
        self.device_id = device_id
        self.sub = sub
        self.name = name
        self.vendor_name = vendor_name

    @property
    def pci(self) -> PciId:
        return PciId(self.vendor_id, self.device_id, self.sub)


def parse_lspci(text: str) -> list[PciDevice]:
    out: list[PciDevice] = []
    for line in text.splitlines():
        m = _LSPCI_LINE.match(line.strip())
        if not m:
            continue
        sub = ""
        if m.group("sven") and m.group("sdev"):
            sub = f"{m.group('sven').lower()}{m.group('sdev').lower()}"
        out.append(
            PciDevice(
                slot=m.group("slot"),
                cls=m.group("cls").lower(),
                vendor_id=m.group("ven").lower(),
                device_id=m.group("dev").lower(),
                sub=sub,
                name=m.group("dev_name").strip(),
                vendor_name=m.group("ven_name").strip(),
            )
        )
    return out


def parse_cpuinfo(text: str) -> Cpu:
    model = ""
    vendor_id = ""
    flags: set[str] = set()
    phys_cores = 0
    logical = 0
    for line in text.splitlines():
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key == "model name" and not model:
            model = val
        elif key == "vendor_id" and not vendor_id:
            vendor_id = val
        elif key == "flags" and not flags:
            flags = set(val.split())
        elif key == "cpu cores" and not phys_cores:
            phys_cores = int(val) if val.isdigit() else 0
        elif key == "processor":
            logical = max(logical, int(val) + 1) if val.isdigit() else logical

    vendor = Vendor.UNKNOWN
    if "AMD" in vendor_id:
        vendor = Vendor.AMD
    elif "Intel" in vendor_id:
        vendor = Vendor.INTEL

    gen, family = (0, "")
    if vendor is Vendor.INTEL:
        gen, family = intel_generation(model)
    elif vendor is Vendor.AMD:
        family = amd_family(model)

    interesting = {"sse4_2", "sse4a", "avx", "avx2", "bmi1", "bmi2", "aes", "rdrand"}
    return Cpu(
        brand=model,
        vendor=vendor,
        family=family,
        intel_gen=gen,
        cores=phys_cores or logical,
        threads=logical,
        flags=frozenset(interesting & flags),
    )


def _dmi(name: str) -> str:
    try:
        return Path(f"/sys/class/dmi/id/{name}").read_text().strip()
    except OSError:
        return ""


def _chassis_from_dmi() -> Chassis:
    # SMBIOS chassis type: 3/4/6/7 desktop-ish, 8-11/14/30-32 portable.
    raw = _dmi("chassis_type")
    try:
        n = int(raw)
    except ValueError:
        return Chassis.UNKNOWN
    if n in {8, 9, 10, 11, 12, 14, 30, 31, 32}:
        return Chassis.LAPTOP
    if n in {3, 4, 5, 6, 7, 13, 15, 16, 23, 24}:
        return Chassis.DESKTOP
    return Chassis.UNKNOWN


def _gpu_from(dev: PciDevice) -> Gpu:
    vendor = vendor_from_pci(dev.vendor_id)
    # heuristic: an Intel/AMD display device on function .0 of a low slot is
    # usually integrated; NVIDIA is always discrete.
    discrete = vendor is Vendor.NVIDIA or not dev.slot.startswith(("00:", "0000:00:"))
    name = dev.name or f"{dev.vendor_name} {dev.device_id}"
    return Gpu(name=name.strip(), vendor=vendor, pci=dev.pci, discrete=discrete)


def _touchpad() -> Input:
    # I2C-HID touchpads register a device whose modalias / name carries the
    # PNP0C50 / ACPI0C50 hid. SMBus (Synaptics RMI4) shows under i2c too.
    try:
        for p in Path("/sys/bus/i2c/devices").iterdir():
            hid = (p / "firmware_node" / "hid").read_text().strip() if (p / "firmware_node" / "hid").exists() else ""
            name = (p / "name").read_text().strip() if (p / "name").exists() else ""
            if "PNP0C50" in hid or "ACPI0C50" in hid or "hid-over-i2c" in name.lower():
                return Input(has_touchpad=True, touchpad_bus="i2c-hid")
    except OSError:
        pass
    for node in Path("/proc/bus/input/devices").read_text(errors="ignore").lower().splitlines() \
            if Path("/proc/bus/input/devices").exists() else []:
        if "touchpad" in node or "synaptics" in node:
            bus = "i2c-hid" if "i2c" in node else "ps2"
            return Input(has_touchpad=True, touchpad_bus=bus)
    return Input()


def build_machine(pci: list[PciDevice], cpu: Cpu, chassis: Chassis, fw: Firmware, inputs: Input) -> Machine:
    igpu = dgpu = None
    for dev in pci:
        if dev.cls.startswith("03"):
            gpu = _gpu_from(dev)
            if gpu.discrete and dgpu is None:
                dgpu = gpu
            elif not gpu.discrete and igpu is None:
                igpu = gpu
            elif dgpu is None:
                dgpu = gpu

    nics: list[NetIf] = []
    storage = Storage()
    for dev in pci:
        if dev.cls in _CLASS_NETWORK or dev.cls.startswith("028"):
            nics.append(
                NetIf(
                    name=dev.name or dev.vendor_name,
                    vendor=vendor_from_pci(dev.vendor_id),
                    pci=dev.pci,
                    wireless=dev.cls.startswith("028"),
                )
            )
        elif dev.cls in _CLASS_NVME:
            storage = Storage(has_nvme=True, nvme_pci=dev.pci)

    return Machine(
        chassis=chassis,
        cpu=cpu,
        igpu=igpu,
        dgpu=dgpu,
        net=nics,
        storage=storage,
        inputs=inputs,
        firmware=fw,
    )


def probe() -> Machine:
    if not have("lspci"):
        raise RuntimeError("lspci not found — install pciutils")
    pci = parse_lspci(run(["lspci", "-nnmm"]))
    try:
        cpu = parse_cpuinfo(Path("/proc/cpuinfo").read_text())
    except OSError:
        cpu = Cpu()
    fw = Firmware(
        board_vendor=_dmi("board_vendor"),
        board_name=_dmi("board_name"),
        bios_vendor=_dmi("bios_vendor"),
    )
    return build_machine(pci, cpu, _chassis_from_dmi(), fw, _touchpad())
