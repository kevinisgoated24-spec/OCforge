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


def test_kext_resolve_exclude():
    names = {s.kext.name for s in kexts.resolve(ryzen_desktop(), _latest_target())}
    assert "AppleALC" in names
    excluded = {s.kext.name for s in
                kexts.resolve(ryzen_desktop(), _latest_target(), exclude=frozenset({"AppleALC"}))}
    assert "AppleALC" not in excluded
    assert names - {"AppleALC"} == excluded


def test_kext_resolve_include():
    m = ryzen_desktop()
    baseline = {s.kext.name for s in kexts.resolve(m, _latest_target())}
    assert "VoodooPS2Controller" not in baseline  # desktop, not a laptop pick
    included = {s.kext.name for s in
                kexts.resolve(m, _latest_target(), include=frozenset({"VoodooPS2Controller"}))}
    assert "VoodooPS2Controller" in included


def test_kext_resolve_include_unknown_name_raises():
    try:
        kexts.resolve(ryzen_desktop(), _latest_target(), include=frozenset({"NotARealKext"}))
    except ValueError as exc:
        assert "NotARealKext" in str(exc)
    else:
        raise AssertionError("expected ValueError for an unknown kext name")


def test_make_warns_on_kext_override():
    p = make(ryzen_desktop(), exclude_kexts=frozenset({"AppleALC"}))
    assert any("manually overridden" in w for w in p.warnings)
    assert "AppleALC" not in {s.kext.name for s in p.kexts}


def _latest_target():
    from ocforge.catalog import macos

    return macos.recommended(ryzen_desktop())


# --- SMBIOS override -------------------------------------------------------


def test_smbios_override_applies():
    p = make(ryzen_desktop(), smbios_override="iMac19,1")
    assert p.smbios_model == "iMac19,1"
    assert any("SMBIOS manually overridden" in w for w in p.warnings)


def test_smbios_override_bad_format_raises():
    import pytest

    with pytest.raises(ValueError, match="doesn't look like a real SMBIOS model"):
        make(ryzen_desktop(), smbios_override="not-a-model")


def test_smbios_no_override_uses_pick_smbios():
    p = make(ryzen_desktop())
    assert not any("SMBIOS manually overridden" in w for w in p.warnings)


# --- SSDT exclude -----------------------------------------------------------


def test_ssdt_exclude():
    m = intel_laptop()
    names = {s.name for s in acpi.select(m)}
    assert "SSDT-XOSI" in names
    excluded = {s.name for s in acpi.select(m, exclude=frozenset({"SSDT-XOSI"}))}
    assert "SSDT-XOSI" not in excluded
    assert names - {"SSDT-XOSI"} == excluded


def test_ssdt_exclude_drops_its_patch_too():
    m = intel_laptop()
    assert acpi.patches(m)  # SSDT-XOSI's _OSI->XOSI rename, normally present
    assert acpi.patches(m, exclude=frozenset({"SSDT-XOSI"})) == []


def test_make_exclude_ssdts_threads_through():
    p = make(intel_laptop(), exclude_ssdts=frozenset({"SSDT-XOSI"}))
    assert "SSDT-XOSI" not in {s.name for s in p.ssdts}
    assert any("SSDT selection manually overridden" in w for w in p.warnings)


# --- quirk override ----------------------------------------------------------


def test_quirk_override_applies_from_the_plan_automatically():
    # assemble() defaults to plan.quirk_overrides -- a caller doesn't need to
    # pass it again separately, same as kexts/ssdts already living on the plan.
    plan = make(ryzen_desktop(), quirk_overrides={"DevirtualiseMmio": True})
    cfg = cfgmod.assemble(plan, generate(plan.smbios_model, None))
    assert cfg["Booter"]["Quirks"]["DevirtualiseMmio"] is True


def test_quirk_override_unknown_name_raises():
    import pytest

    plan = make(ryzen_desktop(), quirk_overrides={"NotAQuirk": True})
    with pytest.raises(ValueError, match="unknown quirk"):
        cfgmod.assemble(plan, generate(plan.smbios_model, None))


def test_quirk_override_non_boolean_field_raises():
    import pytest

    # SetApfsTrimTimeout is a real Kernel Quirks key, but an integer, not a toggle.
    plan = make(ryzen_desktop(), quirk_overrides={"SetApfsTrimTimeout": True})
    with pytest.raises(ValueError, match="aren't on/off toggles"):
        cfgmod.assemble(plan, generate(plan.smbios_model, None))


# --- device-id spoof --------------------------------------------------------


def test_spoof_device_new_path():
    plan = make(ryzen_desktop(), spoof_devices={
        "PciRoot(0x0)/Pci(0x3,0x0)": {"device-id": 0x73AF, "vendor-id": 0x1002},
    })
    cfg = cfgmod.assemble(plan, generate(plan.smbios_model, None))
    props = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x3,0x0)"]
    assert props["device-id"] == bytes.fromhex("af730000")
    assert props["vendor-id"] == bytes.fromhex("02100000")


def test_spoof_device_device_only_no_vendor_key():
    plan = make(ryzen_desktop(), spoof_devices={"PciRoot(0x0)/Pci(0x3,0x0)": {"device-id": 0x73AF}})
    cfg = cfgmod.assemble(plan, generate(plan.smbios_model, None))
    props = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x3,0x0)"]
    assert props["device-id"] == bytes.fromhex("af730000")
    assert "vendor-id" not in props


def test_spoof_device_merges_into_existing_path():
    # The iGPU path already gets AAPL,ig-platform-id from ocforge's own
    # detection -- a spoof there should add device-id alongside it, not
    # replace the whole entry.
    m = intel_laptop()
    plan = make(m, spoof_devices={"PciRoot(0x0)/Pci(0x2,0x0)": {"device-id": 0x1234}})
    cfg = cfgmod.assemble(plan, generate(plan.smbios_model, None))
    props = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    assert props["device-id"] == bytes.fromhex("34120000")
    assert "AAPL,ig-platform-id" in props


def test_spoof_device_warns_and_stored_on_plan():
    plan = make(ryzen_desktop(), spoof_devices={"PciRoot(0x0)/Pci(0x3,0x0)": {"device-id": 0x73AF}})
    assert plan.spoof_devices == {"PciRoot(0x0)/Pci(0x3,0x0)": {"device-id": 0x73AF}}
    assert any("device-id spoof active" in w for w in plan.warnings)


def test_no_spoof_devices_no_warning():
    plan = make(ryzen_desktop())
    assert plan.spoof_devices == {}
    assert not any("spoof" in w for w in plan.warnings)


def test_spoof_device_forces_debug_build(monkeypatch, tmp_path):
    from ocforge.build import pipeline

    captured: dict[str, bool] = {}

    def fake_fetch(work, *, debug):
        captured["debug"] = debug
        raise RuntimeError("stop-here")  # short-circuit before any real network work

    monkeypatch.setattr(pipeline.opencore, "fetch", fake_fetch)

    plan = make(ryzen_desktop(), spoof_devices={"PciRoot(0x0)/Pci(0x3,0x0)": {"device-id": 0x73AF}})
    import pytest

    with pytest.raises(RuntimeError, match="stop-here"):
        pipeline.build_efi(plan, tmp_path / "work", tmp_path / "out")
    assert captured["debug"] is True


def test_no_spoof_devices_leaves_debug_as_passed(monkeypatch, tmp_path):
    from ocforge.build import pipeline

    captured: dict[str, bool] = {}

    def fake_fetch(work, *, debug):
        captured["debug"] = debug
        raise RuntimeError("stop-here")

    monkeypatch.setattr(pipeline.opencore, "fetch", fake_fetch)

    plan = make(ryzen_desktop())
    import pytest

    with pytest.raises(RuntimeError, match="stop-here"):
        pipeline.build_efi(plan, tmp_path / "work", tmp_path / "out")
    assert captured["debug"] is False


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
    assert "npci=0x3000" in p.boot_args
    assert "-no_compat_check" in p.boot_args
    assert any("core count" in w for w in p.warnings)


def test_plan_forced_macos():
    p = make(ryzen_desktop(), target_major=12)
    assert p.target.major == 12


def test_nvidia_only_dgpu_with_no_igpu_is_rejected():
    # RTX 3050 etc: no macOS driver, and nothing else to drive a display.
    import pytest

    m = intel_laptop()
    m.igpu = None
    m.dgpu = Gpu(name="RTX 3050", vendor=Vendor.NVIDIA, discrete=True)
    with pytest.raises(ValueError, match="no supported graphics"):
        make(m)


def test_nvidia_only_dgpu_with_no_igpu_is_rejected_even_with_macos_forced():
    # Forcing --macos doesn't change what the hardware can actually show.
    import pytest

    m = intel_laptop()
    m.igpu = None
    m.dgpu = Gpu(name="RTX 3050", vendor=Vendor.NVIDIA, discrete=True)
    with pytest.raises(ValueError, match="no supported graphics"):
        make(m, target_major=12)


def test_nvidia_dgpu_alongside_a_working_igpu_just_gets_disabled():
    m = intel_laptop()
    m.dgpu = Gpu(name="RTX 3050", vendor=Vendor.NVIDIA, discrete=True)
    p = make(m)
    assert "nv_disable=1" in p.boot_args
    assert any("RTX 3050" in w and "no macOS driver" in w for w in p.warnings)


def test_unsupported_gpu_can_be_forced_through():
    m = intel_laptop()
    m.igpu = None
    m.dgpu = Gpu(name="RTX 3050", vendor=Vendor.NVIDIA, discrete=True)
    p = make(m, allow_unsupported_gpu=True)  # doesn't raise
    assert any("UNSUPPORTED BUILD" in w for w in p.warnings)


def _kaby_lake_laptop():
    # The real machine behind this bug report: a Dell Inspiron 15-3567
    # (7th-gen Kaby Lake) -- Tahoe's min_intel_gen is 8, so forcing --macos 26
    # used to silently build anyway with zero warning, producing a real
    # install with corrupted/garbled graphics instead of a clean refusal.
    return Machine(
        chassis=Chassis.LAPTOP,
        cpu=Cpu(brand="i5-7200U", vendor=Vendor.INTEL, family="Kaby Lake", intel_gen=7,
                cores=2, threads=4, flags=frozenset({"avx2"})),
        igpu=Gpu(name="HD 620", vendor=Vendor.INTEL, pci=PciId("8086", "5916")),
    )


def test_forcing_an_unsupported_macos_target_now_raises_instead_of_building_silently():
    import pytest

    from ocforge.catalog.macos import UnsupportedReleaseError

    with pytest.raises(UnsupportedReleaseError, match="Tahoe.*8th gen"):
        make(_kaby_lake_laptop(), target_major=26)


def test_forced_unsupported_macos_target_can_be_pushed_through_with_a_warning():
    p = make(_kaby_lake_laptop(), target_major=26, allow_unsupported_os=True)
    assert p.target.major == 26
    assert any("UNSUPPORTED macOS TARGET" in w and "Tahoe" in w for w in p.warnings)


def test_forcing_an_actually_supported_macos_target_is_unaffected():
    # Sequoia (min_intel_gen 7) IS fine on this CPU -- no error, no warning.
    p = make(_kaby_lake_laptop(), target_major=15)
    assert p.target.major == 15
    assert not any("UNSUPPORTED macOS TARGET" in w for w in p.warnings)


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


def _pentium(brand="Intel(R) Pentium(R) Gold G5500T CPU @ 3.20GHz", gen=8, cores=2):
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand=brand, vendor=Vendor.INTEL, intel_gen=gen, cores=cores, threads=cores * 2,
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
    # a real i5 (6 cores) -> no spoof
    i5 = cfgmod.assemble(make(_pentium("Intel Core i5-8400", cores=6)), generate("iMac19,1", None))
    assert i5["Kernel"]["Emulate"]["Cpuid1Data"] == b""


def test_two_core_coffee_lake_desktop_is_spoofed_even_without_a_pentium_brand():
    # generic CPUID name (broken WMI / VM), 2C/4T, UHD 630 -> treated as Pentium
    m = _pentium("Intel64 Family 6 Model 158 Stepping 10 GenuineIntel", gen=0)
    cfg = cfgmod.assemble(make(m), generate("iMac19,1", None))
    assert m.cpu.intel_gen == 8   # backfilled from the UHD 630 device id
    assert cfg["Kernel"]["Emulate"]["Cpuid1Data"] == bytes.fromhex("ea060900" + "00" * 12)


def test_is_legacy_amd_is_the_inverse_of_a_recognized_zen_family():
    from ocforge.probe.base import is_legacy_amd

    fx = Cpu(brand="AMD FX-8350 Eight-Core Processor", vendor=Vendor.AMD, cores=8, threads=8)
    ryzen = Cpu(brand="AMD Ryzen 5 5600X", vendor=Vendor.AMD, family="Zen 3", cores=6, threads=12)
    intel = Cpu(brand="i7-8650U", vendor=Vendor.INTEL, family="Coffee Lake", intel_gen=8)
    assert is_legacy_amd(Machine(chassis=Chassis.DESKTOP, cpu=fx)) is True
    assert is_legacy_amd(Machine(chassis=Chassis.DESKTOP, cpu=ryzen)) is False
    assert is_legacy_amd(Machine(chassis=Chassis.DESKTOP, cpu=intel)) is False


def test_legacy_amd_skips_the_ryzen_specific_kexts_but_keeps_mce_disabler():
    fx = _amd_on("990FXA-UD3", "AMD FX-8350 Eight-Core Processor")   # Bulldozer, no Zen family
    names = {s.kext.name for s in make(fx).kexts}
    assert "AMDRyzenCPUPowerManagement" not in names
    assert "SMCAMDProcessor" not in names
    assert "ForgedInvariant" not in names
    assert "AppleMCEReporterDisabler" in names

    ryzen = ryzen_desktop()
    ryzen_names = {s.kext.name for s in make(ryzen).kexts}
    assert {"AMDRyzenCPUPowerManagement", "SMCAMDProcessor", "ForgedInvariant"} <= ryzen_names


def test_legacy_amd_gets_the_legacy_memory_map_by_default_without_the_flag():
    # Dortania's Bulldozer/Jaguar guide wants EnableWriteUnprotector/legacy
    # map as the default -- not just an OEM-firmware --legacy-mmap fallback
    # like it is for modern Intel/Ryzen boards.
    fx = _amd_on("990FXA-UD3", "AMD FX-8350 Eight-Core Processor")
    quirks = cfgmod.assemble(make(fx), generate("MacPro7,1", None))["Booter"]["Quirks"]
    assert quirks["RebuildAppleMemoryMap"] is False
    assert quirks["EnableWriteUnprotector"] is True
    assert quirks["SyncRuntimePermissions"] is False

    ryzen = ryzen_desktop()
    modern = cfgmod.assemble(make(ryzen), generate("MacPro7,1", None))["Booter"]["Quirks"]
    assert modern["RebuildAppleMemoryMap"] is True
    assert modern["EnableWriteUnprotector"] is False


def test_setup_virtual_map_is_on_by_default_off_only_for_newer_amd_chipsets():
    # Both the Ryzen/Threadripper guide (X570/B550/A520/TRx40 exception) and
    # the Bulldozer/Jaguar guide (no exception listed at all -- YES) agree:
    # SetupVirtualMap is on by default, not off for AMD as a whole.
    fx = _amd_on("990FXA-UD3", "AMD FX-8350 Eight-Core Processor")
    assert cfgmod.assemble(make(fx), generate("MacPro7,1", None)) \
        ["Booter"]["Quirks"]["SetupVirtualMap"] is True

    older_am4 = _amd_on("B450 TOMAHAWK MAX")
    older_am4.cpu.family = "Zen 3"
    assert cfgmod.assemble(make(older_am4), generate("MacPro7,1", None)) \
        ["Booter"]["Quirks"]["SetupVirtualMap"] is True

    x570 = _amd_on("X570 AORUS ELITE")
    x570.cpu.family = "Zen 3"
    assert cfgmod.assemble(make(x570), generate("MacPro7,1", None)) \
        ["Booter"]["Quirks"]["SetupVirtualMap"] is False


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
    assert "npci=0x3000" in ba
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
    # gen 8 (Coffee Lake) laptop -- was 0000C087 (Kaby Lake-R/Amber Lake's
    # value, wrong generation entirely) until cross-checked against Dortania's
    # own Coffee Lake/Whiskey Lake laptop guide.
    assert props["AAPL,ig-platform-id"] == bytes.fromhex("00009B3E")
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


def test_bios_checklist_is_vendor_aware():
    from ocforge.catalog import bios

    dell = _pentium()
    dell.firmware = Firmware(board_vendor="Dell Inc.", board_name="03KWTV")
    lines = "\n".join(bios.checklist(dell))
    assert "AHCI" in lines and "Secure Boot" in lines and "CFG Lock" in lines
    assert "Dell notes" in lines and "RAID -> AHCI" in lines
    assert "Above 4G" in lines            # desktop
    assert "DVMT" not in lines            # not a laptop

    lap = intel_laptop()
    lap.firmware = Firmware(board_vendor="LENOVO", board_name="20LES")
    ltxt = "\n".join(bios.checklist(lap))
    assert "DVMT" in ltxt and "Lenovo notes" in ltxt
    assert "Above 4G" not in ltxt

    amd = ryzen_desktop()
    amd.firmware = Firmware(board_vendor="ASUSTeK COMPUTER INC.", board_name="TUF B550")
    atxt = "\n".join(bios.checklist(amd))
    assert "fTPM" in atxt
    assert "CFG Lock" not in atxt and "VT-d" not in atxt   # Intel-only concepts


def test_coffee_lake_desktop_igpu_gets_framebuffer_props():
    m = _pentium()   # UHD 630 (3e92), no dGPU, gen 8, Dell board
    cfg = cfgmod.assemble(make(m), generate("Macmini8,1", None))
    dp = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    assert dp["AAPL,ig-platform-id"] == bytes.fromhex("07009b3e")
    assert dp["framebuffer-patch-enable"] == bytes.fromhex("01000000")
    assert dp["framebuffer-stolenmem"] == bytes.fromhex("00003001")
    assert "device-id" not in dp                      # 3e92 is natively matched

    # an odd CFL desktop iGPU id -> device-id faked to 0x3E9B
    m2 = _pentium()
    m2.igpu = Gpu(name="UHD 630", vendor=Vendor.INTEL, pci=PciId("8086", "3ea0"))
    dp2 = cfgmod.assemble(make(m2), generate("Macmini8,1", None)) \
        ["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    assert dp2["device-id"] == bytes.fromhex("9b3e0000")

    # AMD build has no iGPU props at all
    amd = cfgmod.assemble(make(ryzen_desktop()), generate("MacPro7,1", None))
    assert "PciRoot(0x0)/Pci(0x2,0x0)" not in amd["DeviceProperties"]["Add"]


def test_coffee_lake_desktop_gets_devirtualise_mmio_and_legacy_mmap_toggle():
    m = _pentium()  # CFL desktop, Dell board
    modern = cfgmod.assemble(make(m), generate("Macmini8,1", None))["Booter"]["Quirks"]
    assert modern["DevirtualiseMmio"] is True            # Dortania CFL table
    assert modern["RebuildAppleMemoryMap"] is True and modern["EnableWriteUnprotector"] is False

    legacy = cfgmod.assemble(make(m), generate("Macmini8,1", None),
                             legacy_mmap=True)["Booter"]["Quirks"]
    assert legacy["RebuildAppleMemoryMap"] is False and legacy["EnableWriteUnprotector"] is True
    assert legacy["SyncRuntimePermissions"] is False
    assert legacy["DevirtualiseMmio"] is True            # unaffected by the toggle

    # a Dell build warns about the legacy-mmap fallback
    dell = _pentium()
    dell.firmware = Firmware(board_vendor="Dell Inc.", board_name="03KWTV")
    assert any("legacy-mmap" in w for w in make(dell).warnings)
    assert not any("legacy-mmap" in w for w in make(m).warnings)   # ASUS: no warning
    # a CFL laptop does NOT get DevirtualiseMmio
    assert cfgmod.assemble(make(intel_laptop()), generate("MacBookPro16,1", None)) \
        ["Booter"]["Quirks"]["DevirtualiseMmio"] is False
