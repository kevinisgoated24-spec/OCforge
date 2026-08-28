"""Windows host probe (via CIM/WMI through PowerShell).

One PowerShell call returns a JSON blob with everything; ``parse()`` turns it
into a Machine and is unit-tested against a captured blob.
"""

from __future__ import annotations

import json
import re

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
from ocforge.probe.base import amd_family, intel_generation, powershell, vendor_from_text

_PS_SNAPSHOT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$enc = Get-CimInstance Win32_SystemEnclosure | Select-Object -First 1
$bb  = Get-CimInstance Win32_BaseBoard | Select-Object -First 1
$bios = Get-CimInstance Win32_BIOS | Select-Object -First 1
[pscustomobject]@{
  cpu   = @{ name = $cpu.Name; mfr = $cpu.Manufacturer; cores = $cpu.NumberOfCores; threads = $cpu.NumberOfLogicalProcessors }
  chassis = @($enc.ChassisTypes)
  board = @{ vendor = $bb.Manufacturer; name = $bb.Product; bios = $bios.Manufacturer }
  gpus  = @(Get-CimInstance Win32_VideoController | ForEach-Object { @{ name = $_.Name; pnp = $_.PNPDeviceID } })
  nics  = @(Get-CimInstance Win32_NetworkAdapter | Where-Object { $_.PNPDeviceID -like 'PCI\*' } | ForEach-Object { @{ name = $_.Name; pnp = $_.PNPDeviceID } })
  nvme  = @(Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPClass -eq 'SCSIAdapter' -and $_.Name -match 'NVM' } | ForEach-Object { $_.PNPDeviceID })
  i2chid = [bool](Get-CimInstance Win32_PnPEntity | Where-Object { ($_.HardwareID -join ' ') -match 'PNP0C50|ACPI0C50' })
} | ConvertTo-Json -Depth 5 -Compress
"""

_LAPTOP_CHASSIS = {8, 9, 10, 11, 12, 14, 30, 31, 32}
_DESKTOP_CHASSIS = {3, 4, 5, 6, 7, 13, 15, 16, 23, 24}


def _pnp_ids(pnp: str) -> PciId:
    ven = re.search(r"VEN_([0-9A-Fa-f]{4})", pnp or "")
    dev = re.search(r"DEV_([0-9A-Fa-f]{4})", pnp or "")
    sub = re.search(r"SUBSYS_([0-9A-Fa-f]{8})", pnp or "")
    return PciId(
        vendor=ven.group(1).lower() if ven else "",
        device=dev.group(1).lower() if dev else "",
        sub=(sub.group(1)[4:] + sub.group(1)[:4]).lower() if sub else "",
    )


def parse(blob: str) -> Machine:
    d = json.loads(blob)

    cpu_d = d.get("cpu") or {}
    brand = (cpu_d.get("name") or "").strip()
    mfr = (cpu_d.get("mfr") or "").lower()
    if "amd" in mfr or "authenticamd" in mfr:
        vendor = Vendor.AMD
    elif "intel" in mfr or "genuineintel" in mfr:
        vendor = Vendor.INTEL
    else:
        vendor = vendor_from_text(brand)
    gen, family = (intel_generation(brand) if vendor is Vendor.INTEL else (0, amd_family(brand)))
    cpu = Cpu(
        brand=brand,
        vendor=vendor,
        family=family,
        intel_gen=gen,
        cores=int(cpu_d.get("cores") or 0),
        threads=int(cpu_d.get("threads") or 0),
    )

    chassis = Chassis.UNKNOWN
    for c in d.get("chassis") or []:
        if c in _LAPTOP_CHASSIS:
            chassis = Chassis.LAPTOP
            break
        if c in _DESKTOP_CHASSIS:
            chassis = Chassis.DESKTOP

    igpu = dgpu = None
    for g in d.get("gpus") or []:
        pci = _pnp_ids(g.get("pnp", ""))
        v = vendor_from_text(g.get("name", ""))
        discrete = v is Vendor.NVIDIA or (
            v is Vendor.AMD and any(x in g.get("name", "").lower() for x in ("rx ", "radeon pro", "vega 56", "vega 64", "w6", "w7"))
        )
        gpu = Gpu(name=(g.get("name") or "").strip(), vendor=v, pci=pci, discrete=discrete)
        if gpu.discrete and dgpu is None:
            dgpu = gpu
        elif not gpu.discrete and igpu is None:
            igpu = gpu
        elif dgpu is None:
            dgpu = gpu

    nics = []
    for n in d.get("nics") or []:
        nm = (n.get("name") or "")
        nics.append(
            NetIf(
                name=nm.strip(),
                vendor=vendor_from_text(nm),
                pci=_pnp_ids(n.get("pnp", "")),
                wireless=any(w in nm.lower() for w in ("wi-fi", "wifi", "wireless", "802.11")),
            )
        )

    board = d.get("board") or {}
    return Machine(
        chassis=chassis,
        cpu=cpu,
        igpu=igpu,
        dgpu=dgpu,
        net=nics,
        storage=Storage(has_nvme=bool(d.get("nvme"))),
        inputs=Input(has_touchpad=bool(d.get("i2chid")), touchpad_bus="i2c-hid" if d.get("i2chid") else ""),
        firmware=Firmware(
            board_vendor=(board.get("vendor") or "").strip(),
            board_name=(board.get("name") or "").strip(),
            bios_vendor=(board.get("bios") or "").strip(),
        ),
    )


def probe() -> Machine:
    blob = powershell(_PS_SNAPSHOT).strip()
    if not blob:
        raise RuntimeError("PowerShell CIM query returned nothing (run elevated?)")
    return parse(blob)
