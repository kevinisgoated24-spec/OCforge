"""Which kexts a machine needs, and where each one comes from.

``MANIFEST`` is the static "here is every kext ocforge knows about" table.
``resolve(machine, target)`` walks it and returns the ordered subset this
build needs, with MinKernel/MaxKernel already narrowed to the target release.
"""

from __future__ import annotations

from dataclasses import dataclass

from ocforge.catalog.macos import MacOSRelease
from ocforge.model import Machine, Vendor


@dataclass(frozen=True)
class Kext:
    name: str                       # bundle name without .kext
    repo: str                       # "owner/name" on GitHub
    asset: str                      # regex matched against release asset names
    bundle: str = ""               # path of the .kext inside the zip (default: <name>.kext at root)
    min_darwin: int = 0            # kext's own floor, 0 = none
    max_darwin: int = 0            # kext's own ceiling, 0 = none
    order: int = 50               # OpenCore load order; lower loads first

    def bundle_path(self) -> str:
        return self.bundle or f"{self.name}.kext"


# --- the table ------------------------------------------------------------
# Grouped only for readability; `order` is what actually sorts the output.

_ACIDANTHERA_ZIP = r"^{name}-[\d.]+-RELEASE\.zip$"


def _ac(name: str, order: int, **kw) -> Kext:
    return Kext(name, f"acidanthera/{name}", _ACIDANTHERA_ZIP.format(name=name), order=order, **kw)


MANIFEST: tuple[Kext, ...] = (
    # base — always
    _ac("Lilu", order=0),
    _ac("VirtualSMC", order=5),
    _ac("WhateverGreen", order=10),
    _ac("AppleALC", order=15),
    _ac("RestrictEvents", order=20),
    _ac("NVMeFix", order=25),
    _ac("FeatureUnlock", order=26),
    _ac("CryptexFixup", order=27, min_darwin=22),  # Ventura+, needed on AMD / pre-AVX2 Metal

    # VirtualSMC sensor plugins (shipped inside the VirtualSMC zip)
    Kext("SMCProcessor", "acidanthera/VirtualSMC", _ACIDANTHERA_ZIP.format(name="VirtualSMC"),
         bundle="Kexts/SMCProcessor.kext", order=6),
    Kext("SMCSuperIO", "acidanthera/VirtualSMC", _ACIDANTHERA_ZIP.format(name="VirtualSMC"),
         bundle="Kexts/SMCSuperIO.kext", order=7),
    Kext("SMCBatteryManager", "acidanthera/VirtualSMC", _ACIDANTHERA_ZIP.format(name="VirtualSMC"),
         bundle="Kexts/SMCBatteryManager.kext", order=8),

    # ethernet
    _ac("IntelMausi", order=40),
    Kext("AppleIGC", "Chris1111/AppleIGC", r"AppleIGC.*\.zip", order=41),  # Intel I225/I226 2.5GbE
    Kext("RealtekRTL8111", "CedWorf/RealtekRTL8111", r"RealtekRTL8111.*\.zip", order=42),
    Kext("LucyRTL8125Ethernet", "Mieze/LucyRTL8125Ethernet", r"LucyRTL8125Ethernet.*\.zip", order=43),
    Kext("AtherosE2200Ethernet", "Mieze/AtherosE2200Ethernet", r"AtherosE2200Ethernet.*\.zip", order=44),

    # wifi (Intel; Broadcom uses native drivers, nothing to inject)
    Kext("AirportItlwm", "OpenIntelWireless/itlwm", r"AirportItlwm.*\.zip", order=45),

    # USB mapping
    Kext("USBToolBox", "USBToolBox/kext", r"USBToolBox-.*\.zip", order=60),
    Kext("UTBMap", "", r"", order=61),  # generated locally, not downloaded

    # AMD Ryzen — two separate assets in the same release
    Kext("AMDRyzenCPUPowerManagement", "trulyspinach/SMCAMDProcessor",
         r"^AMDRyzenCPUPowerManagement\.kext\.zip$", bundle="AMDRyzenCPUPowerManagement.kext", order=30),
    Kext("SMCAMDProcessor", "trulyspinach/SMCAMDProcessor",
         r"^SMCAMDProcessor\.kext\.zip$", bundle="SMCAMDProcessor.kext", order=31),
    Kext("ForgedInvariant", "ChefKissInc/ForgedInvariant", r"ForgedInvariant.*\.zip", order=32),

    # Alder Lake+ core topology
    Kext("CpuTopologyRebuild", "b00t-1337/CpuTopologyRebuild", r"CpuTopologyRebuild.*\.zip", order=33),

    # laptop input
    Kext("VoodooPS2Controller", "acidanthera/VoodooPS2",
         r"^VoodooPS2Controller-[\d.]+-RELEASE\.zip$", order=70),
    Kext("VoodooI2C", "VoodooI2C/VoodooI2C", r"^VoodooI2C-[\d.]+-RELEASE\.zip$", order=71),
    Kext("VoodooI2CHID", "VoodooI2C/VoodooI2C", r"^VoodooI2C-[\d.]+-RELEASE\.zip$",
         bundle="VoodooI2CHID.kext", order=72),
    _ac("VoodooInput", order=69),
    Kext("BrightnessKeys", "acidanthera/BrightnessKeys",
         r"^BrightnessKeys-[\d.]+-RELEASE\.zip$", order=73),
    Kext("ECEnabler", "1Revenger1/ECEnabler", r"ECEnabler.*\.zip", order=74),
)

_BY_NAME = {k.name: k for k in MANIFEST}


def get(name: str) -> Kext:
    return _BY_NAME[name]


# --- selection ---------------------------------------------------------------


@dataclass
class Selected:
    kext: Kext
    min_darwin: int
    max_darwin: int
    comment: str = ""


def _need_ethernet(m: Machine) -> str | None:
    for nic in m.wired_nics:
        d = nic.pci.device
        if nic.vendor is Vendor.INTEL:
            if d in {"15f2", "15f3", "125b", "125c", "125d", "5502"}:  # I225/I226
                return "AppleIGC"
            return "IntelMausi"
        if nic.vendor is Vendor.REALTEK:
            return "LucyRTL8125Ethernet" if d == "8125" else "RealtekRTL8111"
        if nic.vendor is Vendor.QUALCOMM:
            return "AtherosE2200Ethernet"
    return None


def _need_wifi(m: Machine) -> str | None:
    w = m.wifi
    if w and w.vendor is Vendor.INTEL:
        return "AirportItlwm"
    return None  # Broadcom = native, unknown = user problem


def resolve(m: Machine, target: MacOSRelease) -> list[Selected]:
    picks: dict[str, str] = {}  # name -> comment

    for base in ("Lilu", "VirtualSMC", "SMCProcessor", "WhateverGreen", "AppleALC",
                 "RestrictEvents", "NVMeFix", "FeatureUnlock"):
        picks[base] = ""
    if target.darwin >= 22:
        picks["CryptexFixup"] = "Metal cryptex on AMD / pre-AVX2"

    if m.is_laptop:
        picks["SMCBatteryManager"] = ""
        picks["VoodooPS2Controller"] = ""
        picks["VoodooInput"] = ""
        picks["BrightnessKeys"] = ""
        picks["ECEnabler"] = ""
        if m.inputs.touchpad_bus == "i2c-hid":
            picks["VoodooI2C"] = ""
            picks["VoodooI2CHID"] = ""
    else:
        picks["SMCSuperIO"] = ""

    if m.cpu.vendor is Vendor.AMD:
        picks["AMDRyzenCPUPowerManagement"] = ""
        picks["SMCAMDProcessor"] = ""
        picks["ForgedInvariant"] = "TSC sync for AMD"
    elif m.cpu.vendor is Vendor.INTEL and m.cpu.intel_gen >= 12:
        picks["CpuTopologyRebuild"] = "E-core topology (Alder Lake+)"

    if eth := _need_ethernet(m):
        picks[eth] = f"for {eth}"
    if wifi := _need_wifi(m):
        picks[wifi] = "Intel Wi-Fi"

    if m.storage.has_nvme:
        picks.setdefault("NVMeFix", "")

    picks["USBToolBox"] = "USB mapping (map ports after first boot)"

    out = [Selected(_BY_NAME[n], _BY_NAME[n].min_darwin, _BY_NAME[n].max_darwin, c)
           for n, c in picks.items()]
    out.sort(key=lambda s: s.kext.order)
    return out
