import plistlib
from pathlib import Path

from ocforge.build import config as cfgmod
from ocforge.build import ssdtgen
from ocforge.build.plan import make
from ocforge.build.smbios import generate
from ocforge.model import Chassis, Cpu, Gpu, Input, Machine, PciId, Storage, Vendor

FIXT = Path(__file__).parent / "fixtures" / "ssdttime_results"


def _amd_desktop():
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand="AMD Ryzen 5 5600X", vendor=Vendor.AMD, cores=6, threads=12),
        dgpu=Gpu(name="RX 6800", vendor=Vendor.AMD, pci=PciId("1002", "73bf"), discrete=True),
        storage=Storage(has_nvme=True),
    )


def _intel_laptop():
    return Machine(
        chassis=Chassis.LAPTOP,
        cpu=Cpu(brand="i7-8650U", vendor=Vendor.INTEL, intel_gen=8, cores=4, threads=8),
        igpu=Gpu(name="UHD 620", vendor=Vendor.INTEL, pci=PciId("8086", "5917")),
        inputs=Input(has_touchpad=True, touchpad_bus="i2c-hid"),
    )


def _intel_desktop_z390():
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand="i9-9900K", vendor=Vendor.INTEL, intel_gen=9, cores=8, threads=16),
        igpu=Gpu(name="UHD 630", vendor=Vendor.INTEL, pci=PciId("8086", "3e98")),
    )


# --- machine -> menu ops ----------------------------------------------------


def test_plan_ops_amd_is_just_ec_and_usbx():
    assert ssdtgen.plan_ops(_amd_desktop()) == [("2", "FakeEC"), ("4", "USBX")]


def test_plan_ops_intel_laptop():
    keys = [k for k, _ in ssdtgen.plan_ops(_intel_laptop())]
    assert keys == ["2", "4", "5", "7", "0"]   # PLUG + RTCAWAC + PNLF, no PMC (laptop)


def test_plan_ops_intel_desktop_300_series():
    keys = [k for k, _ in ssdtgen.plan_ops(_intel_desktop_z390())]
    assert keys == ["2", "4", "5", "6", "7"]   # PMC + RTCAWAC, no PNLF (desktop)


# --- stdin script ---------------------------------------------------------


def test_build_stdin_shape():
    ops = [("2", "FakeEC"), ("4", "USBX")]
    script = ssdtgen.build_stdin(Path("/acpi/in"), ops)
    lines = script.splitlines()
    assert lines[0] == "D"
    assert lines[1] == str(Path("/acpi/in"))
    assert "2" in lines and "4" in lines
    assert script.rstrip().endswith("Q")   # the last real keystroke is a quit
    assert script.endswith("\n")


# --- Results/ parser ----------------------------------------------------------


def test_parse_results_reads_aml_and_patches():
    res = ssdtgen._parse_results(FIXT, "log", ["FakeEC", "USBX"])
    assert res.ok and res.error is None
    assert {p.name for p in res.aml} == {
        "SSDT-EC.aml", "SSDT-USBX.aml", "SSDT-PLUG.aml", "SSDT-RTCAWAC.aml"
    }
    # the Add entry with no matching .aml is dropped
    assert {a["Path"] for a in res.acpi_add} == {p.name for p in res.aml}
    assert len(res.acpi_patch) == 1
    assert res.acpi_patch[0]["Find"] == b"AWAC"


def test_parse_results_no_aml_is_an_error(tmp_path):
    res = ssdtgen._parse_results(tmp_path, "", ["FakeEC"])
    assert not res.ok
    assert "no .aml" in res.error


def test_run_reports_missing_ssdttime(tmp_path):
    res = ssdtgen.run(tmp_path, tmp_path, [("2", "FakeEC")])
    assert not res.ok and "not found" in res.error


# --- config merge ---------------------------------------------------------


def test_assemble_uses_ssdttime_acpi_over_precompiled():
    plan = make(_amd_desktop())
    sm = generate(plan.smbios_model, macserial=None)
    gen = ssdtgen._parse_results(FIXT, "", ["FakeEC"])

    cfg = cfgmod.assemble(plan, sm, acpi_add=gen.acpi_add, acpi_patch=gen.acpi_patch,
                          acpi_delete=gen.acpi_delete)
    reparsed = plistlib.loads(cfgmod.dump(cfg))

    paths = [e["Path"] for e in reparsed["ACPI"]["Add"]]
    assert paths == ["SSDT-EC.aml", "SSDT-USBX.aml", "SSDT-PLUG.aml", "SSDT-RTCAWAC.aml"]
    assert reparsed["ACPI"]["Patch"][0]["Replace"] == b"XWAC"


def test_assemble_without_override_keeps_precompiled_selection():
    plan = make(_amd_desktop())
    cfg = cfgmod.assemble(plan, generate(plan.smbios_model, None))
    assert [e["Path"] for e in cfg["ACPI"]["Add"]] == ["SSDT-EC-USBX.aml"]


# --- Dortania-derived boot-arg -----------------------------------------------


def test_navi_dgpu_gets_agdpmod_pikera():
    assert "agdpmod=pikera" in make(_amd_desktop()).boot_args


def test_polaris_dgpu_does_not_get_agdpmod():
    m = _amd_desktop()
    m.dgpu = Gpu(name="RX 580", vendor=Vendor.AMD, pci=PciId("1002", "67df"), discrete=True)
    assert "agdpmod=pikera" not in make(m).boot_args
