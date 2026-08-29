"""Sandy Bridge through Kaby Lake desktop -- cross-checked against Dortania's
desktop guides (Sandy Bridge, Ivy Bridge, Haswell/Broadwell, Skylake, Kaby
Lake, Coffee Lake, Comet Lake). Values here (SMBIOS, ig-platform-id, quirks)
are taken directly from those guides' PlatformInfo/DeviceProperties/Kernel/
UEFI sections.
"""

from ocforge.build import config as cfgmod
from ocforge.build.plan import make
from ocforge.build.smbios import generate
from ocforge.catalog import acpi, macos
from ocforge.model import Chassis, Cpu, Gpu, Machine, PciId, Vendor


def _desktop(gen, dgpu=None):
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand=f"Intel gen{gen} test CPU", vendor=Vendor.INTEL, intel_gen=gen,
                cores=4, threads=8, flags=frozenset({"avx2"})),
        igpu=Gpu(name="iGPU", vendor=Vendor.INTEL, pci=PciId("8086", "0000")),
        dgpu=dgpu,
    )


def _amd_dgpu():
    return Gpu(name="RX 580", vendor=Vendor.AMD, discrete=True)


def _config_for(m, target_major=None):
    # allow_unsupported_os: this file deliberately forces older generations
    # onto a fixed target_major to check the resulting config in isolation
    # (SMBIOS/ig-platform-id/quirks) regardless of whether that combination
    # is something ocforge would actually recommend -- e.g. Sandy Bridge
    # forced to Monterey, well past its real driver support.
    plan = make(m, target_major=target_major, allow_unsupported_os=True)
    cfg = cfgmod.assemble(plan, generate(plan.smbios_model, None))
    return plan, cfg


# --- SMBIOS -----------------------------------------------------------------


def test_smbios_sandy_bridge_is_macpro6_1():
    plan, _ = _config_for(_desktop(2), target_major=12)
    assert plan.smbios_model == "MacPro6,1"


def test_forcing_sandy_bridge_onto_monterey_needs_the_override_flag():
    # Sandy Bridge's HD 3000 has no Monterey driver (min_intel_gen 3) -- an
    # explicit --macos 12 without --force-unsupported-os must not silently
    # build anyway (this was the actual bug: a real machine forced onto an
    # unsupported target this way produced a broken/corrupted display).
    import pytest

    from ocforge.catalog.macos import UnsupportedReleaseError

    with pytest.raises(UnsupportedReleaseError):
        make(_desktop(2), target_major=12)


def test_smbios_ivy_bridge_igpu_big_sur():
    plan, _ = _config_for(_desktop(3), target_major=11)
    assert plan.smbios_model == "iMac14,4"


def test_smbios_ivy_bridge_dgpu_big_sur_vs_monterey():
    # Monterey drops Ivy Bridge iGPU drivers entirely -- dGPU path needs
    # MacPro6,1 there instead of Big Sur's iMac15,1 (Dortania Ivy Bridge).
    big_sur, _ = _config_for(_desktop(3, _amd_dgpu()), target_major=11)
    monterey, _ = _config_for(_desktop(3, _amd_dgpu()), target_major=12)
    assert big_sur.smbios_model == "iMac15,1"
    assert monterey.smbios_model == "MacPro6,1"


def test_smbios_haswell_bumps_to_broadwell_for_monterey():
    big_sur, _ = _config_for(_desktop(4), target_major=11)
    monterey, _ = _config_for(_desktop(4), target_major=12)
    assert big_sur.smbios_model == "iMac14,4"
    assert monterey.smbios_model == "iMac16,2"  # own model (14,4) dropped in Monterey


def test_smbios_broadwell_same_model_big_sur_and_monterey():
    big_sur, _ = _config_for(_desktop(5), target_major=11)
    monterey, _ = _config_for(_desktop(5), target_major=12)
    assert big_sur.smbios_model == monterey.smbios_model == "iMac16,2"


def test_smbios_skylake_bumps_to_kaby_lake_for_ventura():
    monterey, _ = _config_for(_desktop(6), target_major=12)
    ventura, _ = _config_for(_desktop(6), target_major=13)
    assert monterey.smbios_model == "iMac17,1"
    assert ventura.smbios_model == "iMac18,1"


def test_smbios_kaby_lake_igpu_vs_dgpu():
    igpu, _ = _config_for(_desktop(7))
    dgpu, _ = _config_for(_desktop(7, _amd_dgpu()))
    assert igpu.smbios_model == "iMac18,1"
    assert dgpu.smbios_model == "iMac18,3"


def test_smbios_coffee_lake_refresh_with_dgpu_is_imac19_not_20():
    # Regression: gen9 (CFL-R) with a dGPU used to fall into the >=9 branch
    # and get iMac20,1 (Comet Lake) instead of Coffee Lake's own iMac19,1.
    plan, _ = _config_for(_desktop(9, _amd_dgpu()))
    assert plan.smbios_model == "iMac19,1"


def test_smbios_comet_lake_with_dgpu_is_imac20():
    plan, _ = _config_for(_desktop(10, _amd_dgpu()))
    assert plan.smbios_model == "iMac20,1"


# --- CFG-Lock split at Haswell ----------------------------------------------


def test_pre_haswell_uses_the_pm_cfglock_quirk_not_xcpm():
    _, cfg = _config_for(_desktop(3), target_major=11)  # Ivy Bridge
    q = cfg["Kernel"]["Quirks"]
    assert q["AppleCpuPmCfgLock"] is True
    assert q["AppleXcpmCfgLock"] is False


def test_haswell_and_newer_use_xcpm_cfglock():
    _, cfg = _config_for(_desktop(4), target_major=11)  # Haswell
    q = cfg["Kernel"]["Quirks"]
    assert q["AppleCpuPmCfgLock"] is False
    assert q["AppleXcpmCfgLock"] is True


# --- IgnoreInvalidFlexRatio (pre-Skylake) -----------------------------------


def test_ignore_invalid_flex_ratio_pre_skylake():
    for gen in (2, 3, 4, 5):
        _, cfg = _config_for(_desktop(gen), target_major=12)
        assert cfg["UEFI"]["Quirks"]["IgnoreInvalidFlexRatio"] is True, gen


def test_ignore_invalid_flex_ratio_off_from_skylake_on():
    for gen in (6, 7, 8, 10):
        _, cfg = _config_for(_desktop(gen), target_major=12 if gen < 8 else None)
        assert cfg["UEFI"]["Quirks"]["IgnoreInvalidFlexRatio"] is False, gen


# --- DeviceProperties (ig-platform-id / snb-platform-id) --------------------


def test_ivy_bridge_igpu_platform_id():
    _, cfg = _config_for(_desktop(3), target_major=11)
    props = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    assert props["AAPL,ig-platform-id"] == bytes.fromhex("0A006601")
    assert "framebuffer-fbmem" not in props  # not needed pre-Haswell


def test_haswell_broadwell_skylake_need_framebuffer_fbmem():
    for gen, pid in ((4, "0300220D"), (5, "07002216"), (6, "00001219")):
        _, cfg = _config_for(_desktop(gen), target_major=12)
        props = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
        assert props["AAPL,ig-platform-id"] == bytes.fromhex(pid), gen
        assert props["framebuffer-fbmem"] == bytes.fromhex("00009000"), gen


def test_kaby_lake_does_not_need_framebuffer_fbmem():
    _, cfg = _config_for(_desktop(7), target_major=12)
    props = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    assert "framebuffer-fbmem" not in props


def test_skylake_headless_platform_id_was_wrong_now_fixed():
    # Regression: headless (dGPU-driven) Skylake used to get 03001219
    # (Kaby Lake's value); Dortania Skylake says 01001219.
    _, cfg = _config_for(_desktop(6, _amd_dgpu()), target_major=12)
    props = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    assert props["AAPL,ig-platform-id"] == bytes.fromhex("01001219")


def test_sandy_bridge_gets_no_device_properties():
    # snb-platform-id is a different key entirely, and moot anyway -- no
    # ocforge target supports the Sandy Bridge iGPU as a display driver.
    _, cfg = _config_for(_desktop(2), target_major=12)
    assert "PciRoot(0x0)/Pci(0x2,0x0)" not in cfg["DeviceProperties"]["Add"]


# --- pre-Haswell ACPI Delete (CpuPm/Cpu0Ist) ---------------------------------


def test_pre_haswell_deletes_stock_pm_tables():
    for gen in (2, 3):
        _, cfg = _config_for(_desktop(gen), target_major=12)
        comments = {d["Comment"] for d in cfg["ACPI"]["Delete"]}
        assert comments == {"Delete CpuPm", "Delete Cpu0Ist"}, gen


def test_haswell_and_newer_do_not_delete_pm_tables():
    _, cfg = _config_for(_desktop(4), target_major=12)
    assert cfg["ACPI"]["Delete"] == []


def test_needs_generation_flags_ssdt_pm_for_pre_haswell():
    todo = acpi.needs_generation(_desktop(3))
    assert any("SSDT-PM" in t for t in todo)
    assert not any("SSDT-PM" in t for t in acpi.needs_generation(_desktop(4)))


# --- Ivy Bridge iGPU capped at Big Sur for auto-recommendation --------------


def test_ivy_bridge_igpu_only_recommends_big_sur_not_monterey():
    assert macos.recommended(_desktop(3)).major == 11


def test_ivy_bridge_with_amd_dgpu_can_reach_monterey():
    assert macos.recommended(_desktop(3, _amd_dgpu())).major == 12
