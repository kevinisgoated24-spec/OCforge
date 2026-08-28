
import pytest

from ocforge import spec
from ocforge.fetch import github
from ocforge.model import Chassis, Cpu, Gpu, Machine, NetIf, PciId, Vendor


def _machine():
    return Machine(
        chassis=Chassis.LAPTOP,
        cpu=Cpu(brand="i7-8650U", vendor=Vendor.INTEL, family="Coffee Lake", intel_gen=8,
                cores=4, threads=8, flags=frozenset({"avx2", "sse4_2"})),
        igpu=Gpu(name="UHD 620", vendor=Vendor.INTEL, pci=PciId("8086", "5917")),
        dgpu=None,
        net=[NetIf(name="I219-V", vendor=Vendor.INTEL, pci=PciId("8086", "15d8"))],
    )


def test_spec_roundtrip():
    m = _machine()
    m.source = "spec"  # to_json drops source; from_json always restores it as "spec"
    back = spec.from_json(spec.to_json(m))
    assert back == m
    assert isinstance(back.cpu.flags, frozenset)
    assert back.cpu.flags == m.cpu.flags
    assert back.igpu.pci.device == "5917"
    assert back.dgpu is None


def test_spec_roundtrip_is_stable():
    m = _machine()
    once = spec.to_json(m)
    twice = spec.to_json(spec.from_json(once))
    assert once == twice


_RELEASE_JSON = {
    "tag_name": "1.0.5",
    "assets": [
        {"name": "OpenCore-1.0.5-RELEASE.zip", "browser_download_url": "https://x/rel.zip",
         "size": 8_000_000, "digest": "sha256:abc123"},
        {"name": "OpenCore-1.0.5-DEBUG.zip", "browser_download_url": "https://x/dbg.zip", "size": 9_000_000},
        {"name": "OpenCore-1.0.5-RELEASE.zip.sha256", "browser_download_url": "https://x/sum", "size": 90},
    ],
}


def test_latest_asset_picks_release_not_debug(monkeypatch):
    monkeypatch.setattr(github, "_release_json", lambda repo, tag: _RELEASE_JSON)
    a = github.latest_asset("acidanthera/OpenCorePkg", r"^OpenCore-[\d.]+-RELEASE\.zip$")
    assert a.name == "OpenCore-1.0.5-RELEASE.zip"
    assert a.sha256 == "abc123"
    assert a.release_tag == "1.0.5"


def test_latest_asset_raises_when_nothing_matches(monkeypatch):
    monkeypatch.setattr(github, "_release_json", lambda repo, tag: {"assets": []})
    with pytest.raises(LookupError):
        github.latest_asset("a/b", r"nope")
