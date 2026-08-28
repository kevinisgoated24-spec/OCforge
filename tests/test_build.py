import plistlib

from ocforge.build import config as cfgmod
from ocforge.build.amdvanilla import splice_core_count
from ocforge.build.plan import make
from ocforge.build.smbios import generate
from ocforge.catalog import acpi, kexts
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


def ryzen_desktop():
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand="AMD Ryzen 5 5600X", vendor=Vendor.AMD, family="Zen 3", cores=6, threads=12),
        dgpu=Gpu(name="RX 6800", vendor=Vendor.AMD, pci=PciId("1002", "73bf"), discrete=True),
        net=[NetIf(name="RTL8125", vendor=Vendor.REALTEK, pci=PciId("10ec", "8125"))],
        storage=Storage(has_nvme=True),
    )


def intel_laptop():
    return Machine(
        chassis=Chassis.LAPTOP,
        cpu=Cpu(brand="i7-8650U", vendor=Vendor.INTEL, family="Coffee Lake", intel_gen=8,
                cores=4, threads=8, flags=frozenset({"avx2"})),
        igpu=Gpu(name="UHD 620", vendor=Vendor.INTEL, pci=PciId("8086", "5917")),
        net=[NetIf(name="I219-V", vendor=Vendor.INTEL, pci=PciId("8086", "15d8")),
             NetIf(name="Intel 8265", vendor=Vendor.INTEL, wireless=True)],
        storage=Storage(has_nvme=True),
        inputs=Input(has_touchpad=True, touchpad_bus="i2c-hid"),
    )


# --- kext resolution ------------------------------------------------------


def test_kext_resolve_ryzen_desktop():
    p = make(ryzen_desktop())
    names = [s.kext.name for s in p.kexts]
    assert names[0] == "Lilu"  # load order 0
    assert {"AMDRyzenCPUPowerManagement", "SMCAMDProcessor", "ForgedInvariant"} <= set(names)
    assert "LucyRTL8125Ethernet" in names          # RTL8125 -> Lucy, not RTL8111
    assert "SMCSuperIO" in names and "SMCBatteryManager" not in names  # desktop
    assert "VoodooI2C" not in names
    assert names == sorted(names, key=lambda n: kexts.get(n).order)


def test_kext_resolve_intel_laptop():
    p = make(intel_laptop())
    names = {s.kext.name for s in p.kexts}
    assert {"VoodooPS2Controller", "VoodooI2C", "VoodooI2CHID", "VoodooInput", "SMCBatteryManager"} <= names
    assert "IntelMausi" in names          # I219-V
    assert "AirportItlwm" in names        # Intel wifi
    assert "BlueToolFixup" in names       # laptop + macOS 12+
    assert "AMDRyzenCPUPowerManagement" not in names
    assert "SMCSuperIO" not in names


def test_kext_resolve_broadcom_wifi():
    m = intel_laptop()
    m.net = [NetIf(name="BCM943602CS", vendor=Vendor.BROADCOM, wireless=True)]
    names = {s.kext.name for s in make(m).kexts}
    assert "AirportBrcmFixup" in names
    assert "AirportItlwm" not in names


# --- ACPI selection -----------------------------------------------------------


def _intel(gen, *, laptop=False, board="", brand="", board_vendor=""):
    return Machine(
        chassis=Chassis.LAPTOP if laptop else Chassis.DESKTOP,
        cpu=Cpu(brand=brand or f"Intel Core i7 gen{gen}", vendor=Vendor.INTEL,
                intel_gen=gen, cores=6, threads=12, flags=frozenset({"avx2"})),
        igpu=Gpu(name="UHD", vendor=Vendor.INTEL, pci=PciId("8086", "3e98")),
        firmware=Firmware(board_vendor=board_vendor, board_name=board),
    )


def _names(m):
    return {s.name for s in acpi.select(m)}


def test_acpi_select():
    desk = acpi.select(ryzen_desktop())
    assert [s.name for s in desk] == ["SSDT-EC-USBX"]
    assert desk[0].remote == "SSDT-EC-USBX-DESKTOP"

    lap = acpi.select(intel_laptop())                    # gen 8 Coffee Lake laptop
    assert {s.name for s in lap} == {
        "SSDT-EC-USBX", "SSDT-PLUG", "SSDT-AWAC", "SSDT-PNLF", "SSDT-XOSI"}
    r = {s.name: s.remote for s in lap}
    assert r["SSDT-EC-USBX"] == "SSDT-EC-USBX-LAPTOP"
    assert r["SSDT-PLUG"] == "SSDT-PLUG-DRTNIA"
    assert acpi.needs_generation(intel_laptop())  # I2C trackpad -> SSDT-GPIO todo


def test_acpi_prebuilt_matrix_intel():
    # Skylake/Kaby desktop: PLUG + EC-USBX only
    assert _names(_intel(6)) == {"SSDT-EC-USBX", "SSDT-PLUG"}
    # Haswell desktop: PLUG + plain SSDT-EC (no USBX before Skylake)
    hsw = acpi.select(_intel(4))
    assert {s.name for s in hsw} == {"SSDT-EC", "SSDT-PLUG"}
    assert next(s for s in hsw if s.name == "SSDT-EC").remote == "SSDT-EC-DESKTOP"
    # Coffee Lake desktop: + AWAC + PMC
    assert _names(_intel(9, board="Z390 AORUS")) == {
        "SSDT-EC-USBX", "SSDT-PLUG", "SSDT-AWAC", "SSDT-PMC"}
    # ...but a Z370 board drops PMC
    assert "SSDT-PMC" not in _names(_intel(9, board="Z370 AORUS"))
    # Sandy Bridge + 7-series -> IMEI; Ivy + 6-series -> IMEI (desktop + mobile PCH)
    assert "SSDT-IMEI" in _names(_intel(2, board="P8Z77-V"))
    assert "SSDT-IMEI" in _names(_intel(3, board="P8Z68-V"))
    assert "SSDT-IMEI" in _names(_intel(2, laptop=True, board="Base Board HM77"))
    assert "SSDT-IMEI" in _names(_intel(3, laptop=True, board="ThinkPad HM65"))
    assert "SSDT-IMEI" not in _names(_intel(2, board="X79 DELUXE"))
    assert "SSDT-IMEI" not in _names(_intel(3, laptop=True, board="HM77"))   # normal Ivy pairing


def test_acpi_rhub_and_xosi_and_hedt():
    # Asus 400-series desktop -> RHUB; Gigabyte 400-series -> not
    assert "SSDT-RHUB" in _names(_intel(10, board="ROG STRIX Z490-E", board_vendor="ASUSTeK"))
    assert "SSDT-RHUB" not in _names(_intel(10, board="Z490 AORUS", board_vendor="Gigabyte"))
    # Ice Lake laptop -> RHUB
    assert "SSDT-RHUB" in _names(_intel(10, laptop=True, brand="Intel Core i7-1065G7"))

    # every Intel laptop -> XOSI + its _OSI rename
    pats = acpi.patches(_intel(8, laptop=True))
    assert len(pats) == 1 and pats[0]["Find"] == b"_OSI" and pats[0]["Replace"] == b"XOSI"

    # HEDT: Haswell-E -> UNC + RTC0-RANGE; Skylake-X -> RTC0-RANGE, no UNC
    assert {"SSDT-UNC", "SSDT-RTC0-RANGE-HEDT"} <= _names(_intel(5, board="X99-DELUXE"))
    sklx = _names(_intel(7, board="X299 PRIME"))
    assert "SSDT-RTC0-RANGE-HEDT" in sklx and "SSDT-UNC" not in sklx


def _amd_on(board: str, brand: str = "AMD Ryzen 5 5600X") -> Machine:
    m = ryzen_desktop()
    m.cpu = Cpu(brand=brand, vendor=Vendor.AMD, cores=6, threads=12)
    m.firmware = Firmware(board_vendor="ASUS", board_name=board)
    return m


def test_ssdt_cpur_only_for_b550_a520_am5_not_x570_or_threadripper():
    def has_cpur(board, brand="AMD Ryzen 5 5600X"):
        return any(s.name == "SSDT-CPUR" for s in acpi.select(_amd_on(board, brand)))

    assert has_cpur("TUF GAMING B550-PLUS")
    assert has_cpur("PRIME A520M-K")
    assert has_cpur("ROG STRIX B650E-F")          # AM5 "and newer"
    assert not has_cpur("X570 AORUS ELITE")       # X570 -> no
    assert not has_cpur("B450 TOMAHAWK MAX")      # older AM4 -> no
    assert not has_cpur("TRX40 DESIGNARE", "AMD Ryzen Threadripper 3960X")
    assert not has_cpur("")                        # unknown board -> no (plan warns instead)


# --- BuildPlan --------------------------------------------------------------


def test_plan_amd():
    p = make(ryzen_desktop())
    assert p.is_amd
    assert p.smbios_model == "MacPro7,1"       # AMD + Navi dGPU
    assert "npci=0x2000" in p.boot_args
    assert "-no_compat_check" in p.boot_args
    assert any("core count" in w for w in p.warnings)


def test_plan_forced_macos():
    p = make(ryzen_desktop(), target_major=12)
    assert p.target.major == 12


def test_amd_gets_mce_reporter_disabler_as_a_codeless_kext():
    plan = make(ryzen_desktop())
    sel = next((s for s in plan.kexts if s.kext.name == "AppleMCEReporterDisabler"), None)
    assert sel is not None and sel.kext.codeless and sel.kext.url.endswith(".zip")

    cfg = cfgmod.assemble(plan, generate(plan.smbios_model, None))
    entry = next(e for e in cfg["Kernel"]["Add"]
                 if e["BundlePath"] == "AppleMCEReporterDisabler.kext")
    assert entry["ExecutablePath"] == ""          # plist-only -> no binary path
    assert entry["PlistPath"] == "Contents/Info.plist"

    # AMD: no VT-d, so DisableIoMapper is left off
    assert cfg["Kernel"]["Quirks"]["DisableIoMapper"] is False


def _pentium(brand="Intel(R) Pentium(R) Gold G5500T CPU @ 3.20GHz", gen=8):
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand=brand, vendor=Vendor.INTEL, intel_gen=gen, cores=2, threads=4,
                flags=frozenset({"avx2", "sse4_2"})),
        igpu=Gpu(name="UHD 630", vendor=Vendor.INTEL, pci=PciId("8086", "3e92")),
        firmware=Firmware(board_vendor="ASUS", board_name="PRIME B360M-A"),
    )


def test_pentium_gold_is_detected_as_coffee_lake():
    from ocforge.probe.base import intel_generation
    assert intel_generation("Intel(R) Pentium(R) Gold G5500T CPU @ 3.20GHz")[0] == 8
    assert intel_generation("Pentium Gold G6400")[0] == 10
    assert intel_generation("Celeron G3930")[0] == 6
    assert intel_generation("Intel Core i5-8400")[0] == 8   # unchanged


def test_pentium_gets_cpuid_spoof_to_the_gen_i3():
    plan = make(_pentium())
    cfg = cfgmod.assemble(plan, generate(plan.smbios_model, None))
    emu = cfg["Kernel"]["Emulate"]
    assert emu["Cpuid1Data"] == bytes.fromhex("ea060900" + "00" * 12)   # i3-8100
    assert emu["Cpuid1Mask"] == bytes.fromhex("ffffffff" + "00" * 12)
    assert any("Pentium/Celeron" in w for w in plan.warnings)
    # a plain i5 of the same gen -> no spoof
    i5 = cfgmod.assemble(make(_pentium("Intel Core i5-8400")), generate("iMac19,1", None))
    assert i5["Kernel"]["Emulate"]["Cpuid1Data"] == b""


def test_threadripper_enables_devirtualise_mmio():
    tr = _amd_on("ROG ZENITH II EXTREME", "AMD Ryzen Threadripper 3970X")
    b450 = _amd_on("B450 TOMAHAWK")
    assert cfgmod.assemble(make(tr), generate("MacPro7,1", None))["Booter"]["Quirks"]["DevirtualiseMmio"] is True
    assert cfgmod.assemble(make(b450), generate("MacPro7,1", None))["Booter"]["Quirks"]["DevirtualiseMmio"] is False


# --- config assembly ------------------------------------------------------


def test_config_is_valid_plist_and_shaped_right():
    plan = make(ryzen_desktop())
    sm = generate(plan.smbios_model, macserial=None)
    amd = [{"Comment": "algrey - cpuid_cores_per_package", "Replace": b"\xb8\x00\x00\x00"}]
    cfg = cfgmod.assemble(plan, sm, amd_patches=amd)

    # round-trips through plistlib
    reparsed = plistlib.loads(cfgmod.dump(cfg))
    assert set(reparsed) == {"ACPI", "Booter", "DeviceProperties", "Kernel", "Misc", "NVRAM", "PlatformInfo", "UEFI"}

    assert reparsed["PlatformInfo"]["Generic"]["SystemProductName"] == "MacPro7,1"
    assert reparsed["PlatformInfo"]["Generic"]["ROM"] == sm.rom
    ba = reparsed["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]
    assert "npci=0x2000" in ba
    assert reparsed["Kernel"]["Quirks"]["ProvideCurrentCpuInfo"] is True   # AMD
    assert reparsed["Kernel"]["Quirks"]["AppleXcpmCfgLock"] is False       # AMD
    assert [e["Path"] for e in reparsed["ACPI"]["Add"]] == ["SSDT-EC-USBX.aml"]
    assert len(reparsed["Kernel"]["Add"]) == len(plan.kexts)
    assert len(reparsed["Kernel"]["Patch"]) == 1


def test_config_has_the_keys_ocvalidate_1_0_7_requires():
    cfg = cfgmod.assemble(make(intel_laptop()), generate("iMac20,1", None))
    ui = cfg["UEFI"]
    assert "Unload" in ui and "ReservedMemory" in ui
    assert {"ConsoleFont", "InitialMode", "UIScale"} <= set(ui["Output"])
    assert ui["Output"]["InitialMode"] in ("Auto", "Text", "Graphics")
    assert {"PointerDwellClickTimeout", "PointerDwellDoubleClickTimeout",
            "PointerDwellRadius"} <= set(ui["AppleInput"])
    assert "PciIo" in ui["ProtocolOverrides"]
    assert "ShimRetainProtocol" in ui["Quirks"]
    # UIScale must not be doubled up in NVRAM
    assert "UIScale" not in cfg["NVRAM"]["Add"]["4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14"]


def test_config_intel_sets_ig_platform_id():
    plan = make(intel_laptop())
    sm = generate(plan.smbios_model, macserial=None)
    cfg = cfgmod.assemble(plan, sm)
    props = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    assert props["AAPL,ig-platform-id"] == bytes.fromhex("0000C087")   # gen 8 laptop
    assert cfg["Kernel"]["Quirks"]["ProvideCurrentCpuInfo"] is False


# --- AMD_Vanilla splice ----------------------------------------------------


def test_splice_core_count():
    patches = [
        {"Comment": "algrey - Force cpuid_cores_per_package", "Replace": b"\xb8\x00\x00\x00\x00\x00"},
        {"Comment": "unrelated patch", "Replace": b"\x00\x00\x00"},
    ]
    out = splice_core_count(patches, 12)
    assert out[0]["Replace"] == b"\xb8\x0c\x00\x00\x00\x00"
    assert out[1]["Replace"] == b"\x00\x00\x00"   # untouched


def test_splice_rejects_absurd_core_count():
    import pytest

    with pytest.raises(ValueError):
        splice_core_count([], 999)
