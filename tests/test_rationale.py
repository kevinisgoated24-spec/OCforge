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
            assert d.doc.startswith("https://"), d
            # round-trips for the --json path / GUI
            assert set(asdict(d)) == {"section", "setting", "value", "reason", "doc"}


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

    # AMD build -> config-section docs point at the Dortania AMD guide
    assert _find(decs, "Kernel", "AppleXcpmCfgLock")[0].doc.endswith("/AMD/")


def test_amd_vanilla_patch_list_is_expanded_when_supplied():
    plan = make(_amd_desktop())
    patches = [
        {"Comment": "algrey - Force cpuid_cores_per_package Patch _foo",
         "Enabled": True, "Replace": b"\xb8\x00\x00\x00", "MinKernel": "19.0.0", "MaxKernel": ""},
        {"Comment": "Shaneee - _mtrr_update_action Fix PAT",
         "Enabled": False, "Replace": b"\x00", "MinKernel": "17.0.0", "MaxKernel": "23.99.99"},
    ]
    decs = explain(plan, amd_patches=patches)
    av = [d for d in decs if d.section == "AMD_Vanilla"]
    assert av[0].setting == "patch set (live)" and "2 patches" in av[0].value
    core = next(d for d in av if "cpuid_cores_per_package" in d.setting)
    assert "6" in core.reason                       # spliced to physical core count
    disabled = next(d for d in av if d.setting.startswith("Shaneee"))
    assert "disabled" in disabled.reason
    assert all(d.doc == "https://github.com/AMD-OSX/AMD_Vanilla" for d in av)


def test_intel_laptop_decisions_match_the_config():
    decs = explain(make(_intel_laptop()))

    # gen 8 (Coffee Lake), no dGPU -- was flatly MacBookPro16,1 (Comet Lake's
    # model, "any gen>=8 laptop") until cross-checked against Dortania's own
    # per-generation laptop SMBIOS tables.
    assert _find(decs, "SMBIOS", "SystemProductName")[0].value == "MacBookPro15,2"
    assert _find(decs, "Kernel", "ProvideCurrentCpuInfo")[0].value == "False"
    assert _find(decs, "Kernel", "AppleXcpmCfgLock")[0].value == "True"

    ig = _find(decs, "DeviceProperties", "ig-platform-id")
    assert ig and ig[0].value == "0x00009B3E"   # gen 8 (Coffee Lake) laptop framebuffer

    bootargs = {d.setting for d in decs if d.section == "boot-args"}
    assert "igfxonln=1" in bootargs
    assert "npci=0x2000" not in bootargs

    assert any(d.section == "ACPI" and d.setting == "SSDT-PNLF" for d in decs)
