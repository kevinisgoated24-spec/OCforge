"""Sandy Bridge through Comet/Ice Lake laptop -- cross-checked against
Dortania's own laptop guide for each generation. Same spirit as
test_older_intel_gens.py (the desktop counterpart): values here are taken
directly from each guide's PlatformInfo/DeviceProperties sections.
"""

from ocforge.build import config as cfgmod
from ocforge.build.plan import make
from ocforge.build.smbios import generate
from ocforge.catalog import macos
from ocforge.model import Chassis, Cpu, Gpu, Machine, PciId, Vendor


def _laptop(gen, family="", dgpu=None):
    return Machine(
        chassis=Chassis.LAPTOP,
        cpu=Cpu(brand=f"Intel gen{gen} test CPU", vendor=Vendor.INTEL, intel_gen=gen,
                family=family, cores=4, threads=8, flags=frozenset({"avx2"})),
        igpu=Gpu(name="iGPU", vendor=Vendor.INTEL, pci=PciId("8086", "0000")),
        dgpu=dgpu,
    )


def _amd_dgpu():
    return Gpu(name="RX 580M", vendor=Vendor.AMD, discrete=True)


def _config_for(m, target_major=None, **kw):
    plan = make(m, target_major=target_major, **kw)
    cfg = cfgmod.assemble(plan, generate(plan.smbios_model, None))
    return plan, cfg


# --- SMBIOS -----------------------------------------------------------------


def test_smbios_ivy_bridge_laptop_uses_big_sur_era_models():
    # Ivy Bridge's own laptop models are Catalina-only; ocforge's floor is
    # Big Sur, so it always borrows Haswell's Big-Sur-capable ones.
    no_dgpu, _ = _config_for(_laptop(3))
    dgpu, _ = _config_for(_laptop(3, dgpu=_amd_dgpu()))
    assert no_dgpu.smbios_model == "MacBookAir6,2"
    assert dgpu.smbios_model == "MacBookPro11,3"


def test_smbios_haswell_laptop_bumps_for_monterey():
    big_sur, _ = _config_for(_laptop(4), target_major=11)
    monterey, _ = _config_for(_laptop(4), target_major=12)
    assert big_sur.smbios_model == "MacBookAir6,2"
    assert monterey.smbios_model == "MacBookPro11,4"  # 11,1-11,3 dropped in Monterey


def test_smbios_broadwell_laptop_same_model_big_sur_and_monterey():
    big_sur, _ = _config_for(_laptop(5), target_major=11)
    monterey, _ = _config_for(_laptop(5), target_major=12)
    assert big_sur.smbios_model == monterey.smbios_model == "MacBookPro12,1"


def test_smbios_skylake_laptop_bumps_to_kaby_lake_for_ventura():
    monterey, _ = _config_for(_laptop(6), target_major=12)
    ventura, _ = _config_for(_laptop(6), target_major=13)
    assert monterey.smbios_model == "MacBookPro13,1"
    assert ventura.smbios_model == "MacBookPro14,1"


def test_smbios_kaby_lake_laptop_no_dgpu_vs_dgpu():
    no_dgpu, _ = _config_for(_laptop(7))
    dgpu, _ = _config_for(_laptop(7, dgpu=_amd_dgpu()))
    assert no_dgpu.smbios_model == "MacBookPro14,1"
    assert dgpu.smbios_model == "MacBookPro14,3"


def test_smbios_coffee_lake_laptop_was_wrong_now_fixed():
    # Regression: every gen>=8 laptop used to flatly get MacBookPro16,1
    # (Comet Lake's model) regardless of actual generation.
    no_dgpu, _ = _config_for(_laptop(8))
    dgpu, _ = _config_for(_laptop(9, dgpu=_amd_dgpu()))
    assert no_dgpu.smbios_model == "MacBookPro15,2"
    assert dgpu.smbios_model == "MacBookPro15,1"


def test_smbios_comet_lake_laptop():
    no_dgpu, _ = _config_for(_laptop(10, family="Comet Lake"), target_major=15)
    dgpu, _ = _config_for(_laptop(10, family="Comet Lake", dgpu=_amd_dgpu()))
    assert no_dgpu.smbios_model == "MacBookPro16,3"
    assert dgpu.smbios_model == "MacBookPro16,1"


def test_smbios_tahoe_uses_the_one_igpu_macbook_pro_tahoe_still_supports():
    # Tahoe dropped MacBookPro16,3 (two-port 2020 13"); on a real machine that
    # meant -no_compat_check and a board Apple's servers won't treat as Tahoe.
    tahoe, _ = _config_for(_laptop(13), target_major=26, experimental_xe_gfx=True)
    sequoia, _ = _config_for(_laptop(13), target_major=15, experimental_xe_gfx=True)
    assert tahoe.smbios_model == "MacBookPro16,2"
    assert "-no_compat_check" not in tahoe.boot_args
    assert sequoia.smbios_model == "MacBookPro16,3"


def test_smbios_ice_lake_is_not_comet_lakes_model():
    # Both "10th gen" in Intel's marketing; Ice Lake needs its own SMBIOS,
    # not whatever Comet Lake (also gen 10) gets.
    ice, _ = _config_for(_laptop(10, family="Ice Lake"))
    comet, _ = _config_for(_laptop(10, family="Comet Lake"))
    assert ice.smbios_model == "MacBookAir9,1"
    assert comet.smbios_model != ice.smbios_model


# --- Ice Lake / Comet Lake disambiguation (probe/base.py) -------------------


def test_intel_generation_distinguishes_ice_lake_from_comet_lake():
    from ocforge.probe.base import intel_generation

    comet_gen, comet_family = intel_generation("Intel(R) Core(TM) i7-10510U CPU @ 1.80GHz")
    ice_gen, ice_family = intel_generation("Intel(R) Core(TM) i7-1065G7 CPU @ 1.30GHz")
    ice_ng_gen, ice_ng_family = intel_generation("Intel(R) Core(TM) i5-1038NG7 CPU @ 2.00GHz")

    assert (comet_gen, comet_family) == (10, "Comet Lake")
    assert (ice_gen, ice_family) == (10, "Ice Lake")
    assert (ice_ng_gen, ice_ng_family) == (10, "Ice Lake")


# --- DeviceProperties (ig-platform-id) --------------------------------------


def test_ivy_bridge_laptop_platform_id():
    _, cfg = _config_for(_laptop(3))
    props = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    assert props["AAPL,ig-platform-id"] == bytes.fromhex("03006601")


def test_coffee_lake_laptop_platform_id_was_wrong_now_fixed():
    # Regression: gen 8/9 laptop used to get 0000C087 -- actually Amber Lake
    # Y / Kaby Lake-R's (gen 7) value, not Coffee/Whiskey Lake's own.
    _, cfg = _config_for(_laptop(8))
    props = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    assert props["AAPL,ig-platform-id"] == bytes.fromhex("00009B3E")


def test_kaby_lake_laptop_platform_id_uses_the_primary_recommendation():
    # Was 00001659 -- the guide's own "NUC" value / laptop fallback, not its
    # primary laptop recommendation (00001B59).
    _, cfg = _config_for(_laptop(7))
    props = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    assert props["AAPL,ig-platform-id"] == bytes.fromhex("00001B59")


def test_ice_lake_laptop_gets_its_own_platform_id_not_comet_lakes():
    _, ice_cfg = _config_for(_laptop(10, family="Ice Lake"))
    _, comet_cfg = _config_for(_laptop(10, family="Comet Lake"))
    ice_props = ice_cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    comet_props = comet_cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    assert ice_props["AAPL,ig-platform-id"] == bytes.fromhex("0000528A")
    assert comet_props["AAPL,ig-platform-id"] == bytes.fromhex("00009B3E")
    # The CFL/CML UHD-620-fake shouldn't apply to a completely different chip.
    assert "device-id" not in ice_props


def test_coffee_lake_laptop_gets_device_id_fake_for_unsupported_igpu():
    # UHD 620 in a Coffee Lake CPU needs faking to 0x3E9B, same as desktop --
    # previously this only ever applied to desktop, never laptop.
    m = _laptop(8)
    m.igpu.pci = PciId("8086", "5917")  # a UHD 620 id, not in the CFL-OK set
    _, cfg = _config_for(m)
    props = cfg["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]
    assert props["device-id"] == bytes.fromhex("9b3e0000")


# --- Ivy Bridge iGPU capped at Big Sur applies to laptops too ---------------


def test_ivy_bridge_laptop_igpu_only_recommends_big_sur_not_monterey():
    assert macos.recommended(_laptop(3)).major == 11


# --- Xe-architecture generations (Tiger/Alder/Raptor Lake, gen 11-13): no --
# --- ig-platform-id entry exists, and the laptop SMBIOS ceiling catches ----
# --- them the same way it already catches Comet Lake (gen 10). ------------


def test_raptor_lake_laptop_gets_no_igpu_platform_id():
    # _IG_PLATFORM only goes up to gen 10 (Comet Lake) -- Tiger Lake and
    # newer are a completely different (Xe) display pipeline that
    # WhateverGreen's framebuffer patches don't cover at all, so ocforge
    # should leave DeviceProperties alone here rather than apply a
    # Coffee/Comet-Lake-style fake meant for the old Gen9.5 UHD 6xx chips.
    # An AMD dGPU drives the display -- iGPU-only gen 11+ has no supported
    # display path at all (see test_catalog_macos.py's dead-end tests) and
    # needs --force-unsupported-os just to reach config assembly.
    m = _laptop(13, family="Raptor Lake", dgpu=_amd_dgpu())
    m.igpu.pci = PciId("8086", "a7ad")  # the Core 3 100U's own iGPU id
    _, cfg = _config_for(m)
    props = cfg["DeviceProperties"]["Add"].get("PciRoot(0x0)/Pci(0x2,0x0)", {})
    assert "AAPL,ig-platform-id" not in props
    assert "device-id" not in props


def test_raptor_lake_laptop_smbios_is_the_newest_real_intel_mac_not_sandy_bridges():
    # Before the gen-13-via-new-naming detection fix, an unrecognized brand
    # string meant gen=0, which this same code treats as Sandy Bridge
    # (`gen <= 2`) -- MacBookPro8,1, a 2011 model, wildly wrong for a 2024+
    # CPU. Once correctly detected, it must fall through to the real
    # ceiling instead (Apple's Intel MacBook Pro line never shipped
    # anything past Comet Lake). An AMD dGPU drives the display, same as
    # the test above -- see that test's note on why.
    plan_dgpu, _ = _config_for(_laptop(13, family="Raptor Lake", dgpu=_amd_dgpu()))
    assert plan_dgpu.smbios_model == "MacBookPro16,1"


# --- --experimental-xe-gfx (WhateverXe): opts an otherwise-dead-end Xe-LP ---
# --- iGPU-only laptop (gen 11-13, no AMD dGPU) back into a real build. -----


def test_experimental_xe_gfx_turns_the_dead_end_into_a_real_build():
    # No dGPU at all -- the true dead end _config_for's own docstring-less
    # helper above sidesteps with an AMD dGPU; here that's the whole point.
    m = _laptop(13, family="Raptor Lake")
    m.igpu.pci = PciId("8086", "a7ad")
    plan, cfg = _config_for(m, experimental_xe_gfx=True)
    assert plan.experimental_xe_gfx is True

    names = {s.kext.name for s in plan.kexts}
    assert "WhateverGreen" not in names
    assert {"WhateverXe", "AMFIPass"} <= names

    assert "-allow3d" in plan.boot_args and "-disablegfxfirmware" in plan.boot_args

    nvram = cfg["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]
    assert nvram["csr-active-config"] == bytes.fromhex("03080000")

    props = cfg["DeviceProperties"]["Add"].get("PciRoot(0x0)/Pci(0x2,0x0)", {})
    assert props.get("framebuffer-patch-enable") == bytes.fromhex("01000000")
    assert props.get("framebuffer-stolenmem") == bytes.fromhex("0000C003")
    assert "AAPL,ig-platform-id" not in props and "device-id" not in props

    assert any("WhateverXe" in w for w in plan.warnings)


def test_experimental_xe_gfx_without_the_flag_is_unchanged():
    # Same dead-end machine, flag off (the default) -- still a dead end,
    # same as before this feature existed.
    m = _laptop(13, family="Raptor Lake")
    m.igpu.pci = PciId("8086", "a7ad")
    try:
        _config_for(m)
    except ValueError as exc:
        assert "Xe graphics has no macOS driver" in str(exc)
    else:
        raise AssertionError("expected a dead-end ValueError with the flag off")


def test_experimental_xe_gfx_does_not_cover_meteor_lake():
    # Xe-LPG/Xe2 (gen 14+, Meteor/Arrow Lake) is WTLIntelGfx's territory, not
    # WhateverXe's -- the flag must not silently pretend it works there.
    m = _laptop(14, family="Meteor Lake")
    try:
        _config_for(m, experimental_xe_gfx=True)
    except ValueError as exc:
        assert "WTLIntelGfx" in str(exc) and "Xe-LPG/Xe2" in str(exc)
    else:
        raise AssertionError("expected gen 14 to still be a dead end under --experimental-xe-gfx")


# --- Gen 11-13 CPUID spoof + ProvideCurrentCpuInfo ---------------------------
# Unlike WhateverXe (graphics, opt-in), this fixes XCPM/kernel panics from a
# CPUID signature macOS has never heard of at all -- applies unconditionally
# to any gen 11-13 build, with or without --experimental-xe-gfx, with or
# without a dGPU driving the display. Values cross-checked against
# lzhoang2801/OpCore-Simplify's own spoof_cpuid() mapping.


def test_raptor_lake_gets_comet_lake_cpuid_spoof():
    _, cfg = _config_for(_laptop(13, family="Raptor Lake", dgpu=_amd_dgpu()))
    emulate = cfg["Kernel"]["Emulate"]
    assert emulate["Cpuid1Data"] == bytes.fromhex("55060a00") + b"\x00" * 12
    assert emulate["Cpuid1Mask"] == bytes.fromhex("ffffffff") + b"\x00" * 12


def test_alder_lake_gets_comet_lake_cpuid_spoof_and_current_cpu_info():
    _, cfg = _config_for(_laptop(12, family="Alder Lake", dgpu=_amd_dgpu()))
    emulate = cfg["Kernel"]["Emulate"]
    assert emulate["Cpuid1Data"] == bytes.fromhex("55060a00") + b"\x00" * 12
    assert cfg["Kernel"]["Quirks"]["ProvideCurrentCpuInfo"] is True


def test_tiger_lake_gets_ice_lake_cpuid_spoof_not_comet_lake():
    # The one exception in the gen 11-13 range: OpCore-Simplify's own mapping
    # special-cases Tiger Lake specifically to Ice Lake, not Comet Lake.
    _, cfg = _config_for(_laptop(11, family="Tiger Lake", dgpu=_amd_dgpu()))
    emulate = cfg["Kernel"]["Emulate"]
    assert emulate["Cpuid1Data"] == bytes.fromhex("e5060700") + b"\x00" * 12


def test_tiger_lake_does_not_get_provide_current_cpu_info():
    # No E-cores on Tiger Lake (that starts at Alder Lake, gen 12) -- the
    # hybrid-topology quirk shouldn't apply here.
    _, cfg = _config_for(_laptop(11, family="Tiger Lake", dgpu=_amd_dgpu()))
    assert cfg["Kernel"]["Quirks"]["ProvideCurrentCpuInfo"] is False


def test_rocket_tiger_ambiguous_family_still_gets_a_spoof():
    # Brand-only gen-11 detection can't always tell Rocket Lake (desktop,
    # Comet-Lake-style spoof target) from Tiger Lake (laptop, Ice-Lake-style
    # target) apart -- family comes back as the combined "Rocket/Tiger Lake"
    # string in that case. Falling through to the Comet Lake default (rather
    # than erroring or spoofing nothing) is the defensible choice given that
    # ambiguity, not a bug.
    _, cfg = _config_for(_laptop(11, family="Rocket/Tiger Lake", dgpu=_amd_dgpu()))
    emulate = cfg["Kernel"]["Emulate"]
    assert emulate["Cpuid1Data"] == bytes.fromhex("55060a00") + b"\x00" * 12


def test_no_xe_gen_cpuid_spoof_outside_gen_11_13():
    # Comet Lake itself (gen 10) keeps its existing Pentium/Celeron-only
    # spoof path -- a real quad-core i3/i5/i7 here gets no spoof at all.
    m = _laptop(10, family="Comet Lake")
    _, cfg = _config_for(m)
    emulate = cfg["Kernel"]["Emulate"]
    assert emulate["Cpuid1Data"] == b"" and emulate["Cpuid1Mask"] == b""


# --- VoodooI2C plugins ---------------------------------------------------------


def _i2c_laptop():
    from ocforge.model import Input
    m = _laptop(13)
    m.inputs = Input(has_touchpad=True, touchpad_bus="i2c-hid")
    return m


def test_i2c_hid_laptop_loads_voodooi2c_plugins_before_voodooi2c():
    # Without these, OpenCore links VoodooI2C against empty stubs (seen on a
    # real boot log: "VoodooGPIO not in Boot KC, using kernel stub").
    _, cfg = _config_for(_i2c_laptop(), experimental_xe_gfx=True)
    paths = [e["BundlePath"] for e in cfg["Kernel"]["Add"]]
    services = paths.index("VoodooI2C.kext/Contents/PlugIns/VoodooI2CServices.kext")
    gpio = paths.index("VoodooI2C.kext/Contents/PlugIns/VoodooGPIO.kext")
    assert services < gpio < paths.index("VoodooI2C.kext") < paths.index("VoodooI2CHID.kext")
    # VoodooI2C's bundled VoodooInput would conflict with the standalone one
    assert not any("PlugIns/VoodooInput" in p for p in paths)


def test_voodooi2c_plugins_drop_out_when_voodooi2c_is_excluded():
    from ocforge.catalog import kexts
    names = {s.kext.name for s in kexts.resolve(
        _i2c_laptop(), macos.by_major(26), exclude=frozenset({"VoodooI2C"}))}
    assert not names & {"VoodooI2C", "VoodooI2CServices", "VoodooGPIO"}
