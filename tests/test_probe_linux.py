from pathlib import Path

import pytest

from ocforge.model import Chassis, Vendor
from ocforge.probe import linux

FIX = Path(__file__).parent / "fixtures"

_RYZEN_CPUINFO = """\
processor\t: 0
vendor_id\t: AuthenticAMD
model name\t: AMD Ryzen 5 5600X 6-Core Processor
flags\t\t: fpu vme sse4_2 avx avx2 aes rdrand bmi1 bmi2
cpu cores\t: 6
processor\t: 11
"""

_INTEL_CPUINFO = """\
processor\t: 0
vendor_id\t: GenuineIntel
model name\t: Intel(R) Core(TM) i7-8650U CPU @ 1.90GHz
flags\t\t: fpu vme sse4_2 avx avx2 aes
cpu cores\t: 4
processor\t: 7
"""


def test_parse_lspci_ryzen_rx6800():
    devs = linux.parse_lspci((FIX / "lspci_ryzen_rx6800.txt").read_text())
    by_cls = {d.cls: d for d in devs}
    gpu = by_cls["0300"]
    assert gpu.vendor_id == "1002" and gpu.device_id == "73bf"
    assert gpu.sub == "1da2e438"
    assert "Radeon RX 6800" in gpu.name
    assert by_cls["0108"].device_id == "a808"  # NVMe
    assert by_cls["0200"].vendor_id == "10ec"  # RTL8125


def test_build_machine_ryzen_desktop():
    devs = linux.parse_lspci((FIX / "lspci_ryzen_rx6800.txt").read_text())
    cpu = linux.parse_cpuinfo(_RYZEN_CPUINFO)
    m = linux.build_machine(devs, cpu, Chassis.DESKTOP, linux.Firmware(), linux.Input())

    assert m.cpu.vendor is Vendor.AMD
    assert m.cpu.family == "Zen 3"
    assert m.cpu.cores == 6 and m.cpu.threads == 12
    assert m.igpu is None
    assert m.dgpu is not None and m.dgpu.vendor is Vendor.AMD and m.dgpu.discrete
    assert m.storage.has_nvme
    assert [n.vendor for n in m.wired_nics] == [Vendor.REALTEK]
    assert m.wifi is None


def test_build_machine_intel_laptop_igpu_only():
    devs = linux.parse_lspci((FIX / "lspci_thinkpad_i7_8650u.txt").read_text())
    cpu = linux.parse_cpuinfo(_INTEL_CPUINFO)
    m = linux.build_machine(devs, cpu, Chassis.LAPTOP, linux.Firmware(), linux.Input())

    assert m.cpu.vendor is Vendor.INTEL
    assert m.cpu.intel_gen == 8 and m.cpu.family == "Coffee Lake"
    assert m.igpu is not None and not m.igpu.discrete
    assert m.igpu.pci.device == "5917"
    assert m.dgpu is None
    assert m.wifi is not None and m.wifi.vendor is Vendor.INTEL
    assert [n.pci.device for n in m.wired_nics] == ["15d8"]  # I219-V


def test_parse_cpuinfo_flags_are_filtered():
    cpu = linux.parse_cpuinfo(_RYZEN_CPUINFO)
    assert "avx2" in cpu.flags and "sse4_2" in cpu.flags
    assert "fpu" not in cpu.flags and "vme" not in cpu.flags


def test_probe_requires_lspci(monkeypatch):
    monkeypatch.setattr(linux, "have", lambda _: False)
    with pytest.raises(RuntimeError, match="lspci"):
        linux.probe()
