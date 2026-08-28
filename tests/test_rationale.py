from dataclasses import asdict

from ocforge.build.plan import make
from ocforge.build.rationale import Decision, explain
from ocforge.model import Chassis, Cpu, Gpu, Input, Machine, NetIf, PciId, Vendor


def _amd_desktop():
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand="AMD Ryzen 5 5600X", vendor=Vendor.AMD, family="Zen 3",
                cores=6, threads=12, flags=frozenset({"avx2"})),
        dgpu=Gpu(name="RX 6800", vendor=Vendor.AMD, pci=PciId("1002", "73bf"), discrete=True),
        net=[NetIf(name="RTL8125", vendor=Vendor.REALTEK, pci=PciId("10ec", "8125"))],
    )


def _intel_laptop():
    return Machine(
        chassis=Chassis.LAPTOP,
        cpu=Cpu(brand="i7-8650U", vendor=Vendor.INTEL, intel_gen=8, cores=4, threads=8,
                flags=frozenset({"avx2"})),
        igpu=Gpu(name="UHD 620", vendor=Vendor.INTEL, pci=PciId("8086", "5917")),
        net=[NetIf(name="I219-V", vendor=Vendor.INTEL, pci=PciId("8086", "15d8"))],
        inputs=Input(has_touchpad=True, touchpad_bus="i2c-hid"),
    )


def _find(decs, section, needle):
    return [d for d in decs if d.section == section and needle in d.setting]


def test_every_decision_is_fully_populated_and_ascii():
    for m in (_amd_desktop(), _intel_laptop()):
        decs = explain(make(m))
        assert decs
        for d in decs:
            assert isinstance(d, Decision)
            for field in (d.section, d.setting, d.value, d.reason):
                assert field and field.strip()
                assert field.isascii(), field
            # round-trips for the --json path / GUI
            assert set(asdict(d)) == {"section", "setting", "value", "reason"}


def test_amd_decisions_match_the_config():
    decs = explain(make(_amd_desktop()))

    smbios = _find(decs, "SMBIOS", "SystemProductName")[0]
    assert smbios.value == "MacPro7,1"

    assert _find(decs, "Kernel", "ProvideCurrentCpuInfo")[0].value == "True"
    assert _find(decs, "Kernel", "AppleXcpmCfgLock")[0].value == "False"
    assert _find(decs, "Kernel", "DummyPowerManagement")[0].value == "True"
    assert _find(decs, "Kernel", "AMD_Vanilla")[0].value == "spliced to 6 cores"

    bootargs = {d.setting for d in decs if d.section == "boot-args"}
    assert {"npci=0x2000", "agdpmod=pikera", "-no_compat_check"} <= bootargs


def test_intel_laptop_decisions_match_the_config():
    decs = explain(make(_intel_laptop()))

    assert _find(decs, "SMBIOS", "SystemProductName")[0].value == "MacBookPro16,1"
    assert _find(decs, "Kernel", "ProvideCurrentCpuInfo")[0].value == "False"
    assert _find(decs, "Kernel", "AppleXcpmCfgLock")[0].value == "True"

    ig = _find(decs, "DeviceProperties", "ig-platform-id")
    assert ig and ig[0].value == "0x0000C087"   # gen 8 laptop framebuffer

    bootargs = {d.setting for d in decs if d.section == "boot-args"}
    assert "igfxonln=1" in bootargs
    assert "npci=0x2000" not in bootargs

    assert any(d.section == "ACPI" and d.setting == "SSDT-PNLF" for d in decs)
