"""macOS probe + IORegistry ACPI dump, against synthetic ``ioreg -a`` plists
(no Mac needed — the parse helpers are pure)."""

import plistlib

import pytest

from ocforge.model import Chassis, Cpu, Firmware, Input, Vendor
from ocforge.probe import acpi_dump, darwin
from ocforge.probe.linux import build_machine


def _le(n: int, size: int = 4) -> bytes:
    return n.to_bytes(size, "little")


def _pci(ven, dev, cls, dbg, model=None, sub=None):
    d = {"vendor-id": _le(ven), "device-id": _le(dev), "class-code": _le(cls),
         "pcidebug": dbg, "IOName": "pci-bridge"}
    if model:
        d["model"] = model.encode() + b"\x00"
    if sub:
        d["subsystem-vendor-id"], d["subsystem-id"] = _le(sub[0]), _le(sub[1])
    return d


# What `ioreg -a -r -c IOPCIDevice` looks like on an Intel Hackintosh laptop:
# UHD 630 iGPU, an RX 580 dGPU, I219-V ethernet, AX201 Wi-Fi, NVMe.
_PCI_PLIST = plistlib.dumps([
    _pci(0x8086, 0x3E9B, 0x030000, "0:2:0", "Intel UHD Graphics 630"),
    _pci(0x1002, 0x67DF, 0x030000, "1:0:0(1:1)", "Radeon RX 580", sub=(0x1DA2, 0xE387)),
    _pci(0x8086, 0x15BC, 0x020000, "0:31:6"),
    _pci(0x8086, 0x06F0, 0x028000, "0:20:3"),
    _pci(0x144D, 0xA808, 0x010802, "2:0:0(2:2)"),
    {"IOName": "not-a-pci-device"},  # no ids -> skipped
])


def test_parse_ioreg_pci_maps_to_lspci_style_records():
    devs = darwin.parse_ioreg_pci(_PCI_PLIST)
    assert len(devs) == 5
    igpu = devs[0]
    assert (igpu.vendor_id, igpu.device_id, igpu.cls, igpu.slot) == ("8086", "3e9b", "0300", "00:02.0")
    assert igpu.name == "Intel UHD Graphics 630"
    assert devs[1].slot == "01:00.0" and devs[1].sub == "1da2e387"
    assert devs[3].cls == "0280"
    assert devs[4].cls == "0108"


def test_ioreg_pci_builds_same_machine_as_linux():
    m = build_machine(darwin.parse_ioreg_pci(_PCI_PLIST), Cpu(), Chassis.LAPTOP, Firmware(), Input())
    assert m.igpu is not None and not m.igpu.discrete and m.igpu.pci.device == "3e9b"
    assert m.dgpu is not None and m.dgpu.discrete and m.dgpu.vendor is Vendor.AMD
    assert m.wifi is not None and m.wifi.pci.device == "06f0"
    assert [n.pci.device for n in m.wired_nics] == ["15bc"]
    assert m.storage.has_nvme and m.storage.nvme_pci.vendor == "144d"


def test_parse_ioreg_pci_tolerates_garbage():
    assert darwin.parse_ioreg_pci(b"") == []
    assert darwin.parse_ioreg_pci(b"not a plist") == []


def test_cpu_features_map_to_linux_flag_names():
    flags = darwin.parse_cpu_features(
        "FPU VME SSE4.1 SSE4.2 AES AVX1.0 RDRAND F16C SMEP BMI1 AVX2 BMI2 ERMS"
    )
    assert flags == frozenset({"sse4_2", "aes", "avx", "rdrand", "bmi1", "avx2", "bmi2"})


@pytest.mark.parametrize(("arm", "brand", "want"), [
    ("1", "Apple M2 Pro", True),
    ("", "Apple M1", True),          # sysctl key missing, brand still tells
    ("1", "", True),                 # Rosetta Python: the hardware flag still says arm64
    ("", "Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz", False),
    ("0", "AMD Ryzen 7 5800X 8-Core Processor", False),
])
def test_apple_silicon_detection(arm, brand, want):
    assert darwin.is_apple_silicon(arm, brand) is want


def test_probe_refuses_apple_silicon(monkeypatch):
    vals = {"machdep.cpu.brand_string": "Apple M3", "hw.optional.arm64": "1"}
    monkeypatch.setattr(darwin, "_sysctl", lambda k: vals.get(k, ""))
    with pytest.raises(darwin.AppleSiliconHost, match="--spec"):
        darwin.probe()
    assert issubclass(darwin.AppleSiliconHost, RuntimeError)  # cli.main prints it cleanly


@pytest.mark.parametrize(("model", "battery", "want"), [
    ("MacBookPro16,1", False, Chassis.LAPTOP),
    ("iMac20,1", True, Chassis.LAPTOP),   # Hackintosh laptop on a desktop SMBIOS
    ("iMac20,1", False, Chassis.DESKTOP),
    ("", False, Chassis.UNKNOWN),
])
def test_chassis(model, battery, want):
    assert darwin.chassis_from(model, battery) is want


def test_touchpad_bus_from_loaded_kexts():
    assert darwin.touchpad_from_ioreg("com.alexandred.VoodooI2CHID").touchpad_bus == "i2c-hid"
    assert darwin.touchpad_from_ioreg(
        "as.acidanthera.voodoo.driver.PS2Controller VoodooPS2Trackpad").touchpad_bus == "ps2"
    assert darwin.touchpad_from_ioreg("VoodooRMI VoodooSMBus").touchpad_bus == "smbus"
    assert not darwin.touchpad_from_ioreg("com.apple.driver.AppleHIDKeyboard").has_touchpad


# ---- IORegistry ACPI tables --------------------------------------------------

def _table(sig: bytes, body: bytes) -> bytes:
    return sig + b"\x00" * 32 + body  # 36-byte header + payload


_DSDT = _table(b"DSDT", b"dsdt")
_SSDT_A = _table(b"SSDT", b"cpu")
_SSDT_B = _table(b"SSDT", b"gpio")


def _acpi_plist(tables: dict) -> bytes:
    return plistlib.dumps([{"IOName": "acpi", "IORegistryEntryChildren": [],
                            "ACPI Tables": tables}])


def test_parse_ioreg_acpi_groups_by_real_signature():
    raw = _acpi_plist({"SSDT-1": _SSDT_B, "DSDT": _DSDT, "SSDT": _SSDT_A,
                       "SSDT-CpuPm": _SSDT_A,        # duplicate payload -> dropped
                       "FACP": _table(b"FACP", b""), "junk": b"tiny"})
    got = acpi_dump.parse_ioreg_acpi(raw)
    assert got[b"DSDT"] == [_DSDT]
    assert got[b"SSDT"] == [_SSDT_A, _SSDT_B]
    assert b"FACP" in got and b"tiny" not in got


def test_parse_ioreg_acpi_finds_nested_dict_and_handles_empty():
    nested = plistlib.dumps({"IORegistryEntryChildren": [{"ACPI Tables": {"DSDT": _DSDT}}]})
    assert acpi_dump.parse_ioreg_acpi(nested)[b"DSDT"] == [_DSDT]
    assert acpi_dump.parse_ioreg_acpi(b"") == {}
    assert acpi_dump.parse_ioreg_acpi(plistlib.dumps([])) == {}  # Apple Silicon: no node


def test_dump_darwin_writes_dsdt_and_ssdts(monkeypatch, tmp_path):
    monkeypatch.setattr(acpi_dump.sys, "platform", "darwin")
    monkeypatch.setattr(acpi_dump, "_ioreg_acpi_raw",
                        lambda: _acpi_plist({"DSDT": _DSDT, "SSDT": _SSDT_A, "SSDT-1": _SSDT_B}))
    assert acpi_dump.can_dump() is True
    out = acpi_dump.dump_tables(tmp_path / "acpi")
    assert sorted(f.name for f in out.iterdir()) == ["DSDT.aml", "SSDT-1.aml", "SSDT-2.aml"]
    assert (out / "DSDT.aml").read_bytes() == _DSDT


def test_dump_darwin_apple_silicon_has_no_tables(monkeypatch, tmp_path):
    monkeypatch.setattr(acpi_dump.sys, "platform", "darwin")
    monkeypatch.setattr(acpi_dump, "_ioreg_acpi_raw", lambda: b"")
    assert acpi_dump.can_dump() is False
    with pytest.raises(acpi_dump.DsdtUnavailable, match="Apple Silicon"):
        acpi_dump.dump_tables(tmp_path / "acpi")
