"""Value objects describing a target machine.

A `Machine` is assembled by a host probe (`ocforge.probe`) or built by hand
from a spec file. Everything downstream — macOS compatibility, kext choice,
config.plist assembly — reads this and nothing else, so the probes are the
only OS-specific code in the project.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Chassis(str, Enum):
    DESKTOP = "desktop"
    LAPTOP = "laptop"
    UNKNOWN = "unknown"


class Vendor(str, Enum):
    INTEL = "intel"
    AMD = "amd"
    NVIDIA = "nvidia"
    APPLE = "apple"
    REALTEK = "realtek"
    BROADCOM = "broadcom"
    QUALCOMM = "qualcomm"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PciId:
    """vendor:device, lowercase hex, no 0x. ``sub`` is subsystem id when known."""

    vendor: str = ""
    device: str = ""
    sub: str = ""

    def __str__(self) -> str:  # pragma: no cover - trivial
        core = f"{self.vendor}:{self.device}" if self.vendor and self.device else (self.device or "")
        return f"{core} ({self.sub})" if self.sub else core

    @property
    def empty(self) -> bool:
        return not (self.vendor or self.device)


@dataclass
class Cpu:
    brand: str = ""                 # raw brand string, e.g. "AMD Ryzen 5 5600X"
    vendor: Vendor = Vendor.UNKNOWN
    family: str = ""               # microarch family, e.g. "Zen 3", "Comet Lake"
    intel_gen: int = 0            # Intel Core generation, 0 for non-Intel / unknown
    cores: int = 0
    threads: int = 0
    flags: frozenset[str] = frozenset()  # cpuid feature flags of interest (sse4_2, avx2, …)


@dataclass
class Gpu:
    name: str = ""
    vendor: Vendor = Vendor.UNKNOWN
    pci: PciId = field(default_factory=PciId)
    discrete: bool = False        # False = iGPU / SoC graphics


@dataclass
class NetIf:
    name: str = ""
    vendor: Vendor = Vendor.UNKNOWN
    pci: PciId = field(default_factory=PciId)
    wireless: bool = False


@dataclass
class Storage:
    has_nvme: bool = False
    nvme_pci: PciId = field(default_factory=PciId)


@dataclass
class Input:
    has_touchpad: bool = False
    # "ps2" | "i2c-hid" | "smbus" | "usb" | "" — how the trackpad is wired
    touchpad_bus: str = ""


@dataclass
class Firmware:
    board_vendor: str = ""
    board_name: str = ""
    bios_vendor: str = ""


@dataclass
class Machine:
    chassis: Chassis = Chassis.UNKNOWN
    cpu: Cpu = field(default_factory=Cpu)
    igpu: Gpu | None = None
    dgpu: Gpu | None = None
    net: list[NetIf] = field(default_factory=list)
    storage: Storage = field(default_factory=Storage)
    inputs: Input = field(default_factory=Input)
    firmware: Firmware = field(default_factory=Firmware)
    source: str = "probe"         # "probe" | "spec" — where this came from

    # --- convenience accessors used all over the pipeline -------------------

    @property
    def display_gpu(self) -> Gpu | None:
        """Whatever actually drives the screen: the dGPU on a desktop with no
        iGPU, otherwise the iGPU."""
        return self.igpu or self.dgpu

    @property
    def gpus(self) -> list[Gpu]:
        return [g for g in (self.igpu, self.dgpu) if g is not None]

    @property
    def wired_nics(self) -> list[NetIf]:
        return [n for n in self.net if not n.wireless]

    @property
    def wifi(self) -> NetIf | None:
        return next((n for n in self.net if n.wireless), None)

    @property
    def is_laptop(self) -> bool:
        return self.chassis is Chassis.LAPTOP
