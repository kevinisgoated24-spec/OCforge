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


def test_amd_desktop_without_supported_dgpu_blocks_metal_releases():
    m = _amd_desktop(dgpu_vendor=None)
    verdicts = {c.release.major: c for c in macos.evaluate(m)}
    assert not verdicts[15].supported  # Sonoma/Sequoia dropped the non-Metal path
    assert not verdicts[14].supported
    assert verdicts[13].supported      # Ventura still has it
    assert macos.recommended(m).major == 13


def test_amd_with_nvidia_dgpu_is_not_metal_ok():
    m = _amd_desktop(dgpu_vendor=Vendor.NVIDIA)
    assert not {c.release.major: c for c in macos.evaluate(m)}[14].supported


def test_intel_6th_gen_stops_at_ventura():
    verdicts = {c.release.major: c for c in macos.evaluate(_intel_laptop(6))}
    assert verdicts[13].supported
    assert not verdicts[14].supported  # Sonoma needs 7th gen+
    assert macos.recommended(_intel_laptop(6)).major == 13


def test_intel_needs_avx2_for_ventura_plus():
    old = _intel_laptop(8, flags=frozenset())
    verdicts = {c.release.major: c for c in macos.evaluate(old)}
    assert not verdicts[13].supported and "AVX2" in verdicts[13].note
    assert verdicts[12].supported


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
