from ocforge.catalog import macos
from ocforge.model import Chassis, Cpu, Gpu, Machine, Vendor


def _amd_desktop(dgpu_vendor=Vendor.AMD):
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand="AMD Ryzen 5 5600X", vendor=Vendor.AMD, family="Zen 3", cores=6, threads=12),
        dgpu=Gpu(name="RX 6800", vendor=dgpu_vendor, discrete=True) if dgpu_vendor else None,
    )


def _intel_laptop(gen, flags=frozenset({"avx2"})):
    return Machine(
        chassis=Chassis.LAPTOP,
        cpu=Cpu(brand=f"i7-{gen}650U", vendor=Vendor.INTEL, intel_gen=gen, flags=flags),
        igpu=Gpu(name="UHD 620", vendor=Vendor.INTEL, discrete=False),
    )


def test_amd_desktop_with_amd_dgpu_runs_everything():
    verdicts = {c.release.major: c for c in macos.evaluate(_amd_desktop())}
    assert verdicts[26].supported and verdicts[11].supported
    assert macos.recommended(_amd_desktop()).major == 26


def test_amd_desktop_without_supported_dgpu_blocks_every_release():
    # AMD has no iGPU; with no dGPU at all there's nothing to drive a
    # display on *any* release, not just the Metal-required ones.
    m = _amd_desktop(dgpu_vendor=None)
    assert not macos.has_display_path(m)
    verdicts = {c.release.major: c for c in macos.evaluate(m)}
    assert not any(v.supported for v in verdicts.values())
    assert macos.recommended(m) is None


def test_amd_with_nvidia_dgpu_is_not_metal_ok():
    # NVIDIA doesn't count as a display path either -- same as no dGPU.
    m = _amd_desktop(dgpu_vendor=Vendor.NVIDIA)
    assert not macos.has_display_path(m)
    assert macos.recommended(m) is None


def test_intel_igpu_with_nvidia_dgpu_still_works():
    # The common "gaming laptop" case: NVIDIA dGPU is unsupported, but the
    # Intel iGPU is right there and drives the display fine.
    m = _intel_laptop(8)
    m.dgpu = Gpu(name="RTX 3050", vendor=Vendor.NVIDIA, discrete=True)
    assert macos.has_display_path(m)
    assert macos.recommended(m) is not None


def test_intel_6th_gen_stops_at_ventura():
    verdicts = {c.release.major: c for c in macos.evaluate(_intel_laptop(6))}
    assert verdicts[13].supported
    assert not verdicts[14].supported  # Sonoma needs 7th gen+
    assert macos.recommended(_intel_laptop(6)).major == 13


def test_pentium_celeron_capped_at_monterey_no_avx2():
    pen = _intel_laptop(8, flags=frozenset())
    pen.cpu.brand = "Intel(R) Pentium(R) Gold G5500T CPU @ 3.20GHz"
    verdicts = {c.release.major: c for c in macos.evaluate(pen)}
    assert not verdicts[13].supported and "AVX2" in verdicts[13].note
    assert verdicts[12].supported
    assert macos.recommended(pen).major == 12


def test_iseries_with_unknown_flags_is_assumed_avx2_capable():
    # Windows/macOS probe reports no feature flags — a Core i-series still
    # gets Ventura+ (they all have AVX2 from Haswell on).
    i5 = _intel_laptop(8, flags=frozenset())
    i5.cpu.brand = "Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz"
    verdicts = {c.release.major: c for c in macos.evaluate(i5)}
    assert verdicts[13].supported
    # but a linux probe that positively lacks avx2 is still blocked
    noavx = _intel_laptop(8, flags=frozenset({"sse4_2"}))
    noavx.cpu.brand = "Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz"
    assert not {c.release.major: c for c in macos.evaluate(noavx)}[13].supported


def test_11th_gen_laptop_is_a_dead_end():
    m = _intel_laptop(11)
    assert macos.recommended(m) is None or not any(
        c.supported for c in macos.evaluate(m)
    )


def test_11th_gen_desktop_with_amd_dgpu_is_ok():
    m = Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand="i5-11400", vendor=Vendor.INTEL, intel_gen=11, flags=frozenset({"avx2"})),
        igpu=Gpu(name="UHD 730", vendor=Vendor.INTEL),
        dgpu=Gpu(name="RX 6600", vendor=Vendor.AMD, discrete=True),
    )
    assert macos.recommended(m).major == 26
