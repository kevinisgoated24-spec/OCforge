import io
import zipfile
from pathlib import Path

from ocforge.fetch.kexts import _extract_bundle


def _make_zip(tmp_path: Path, entries: dict[str, bytes]) -> Path:
    zp = tmp_path / "rel.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return zp


def test_extract_bundle_from_nested_zip(tmp_path):
    zp = _make_zip(tmp_path, {
        "Kexts/Release/Lilu.kext/Contents/Info.plist": b"<plist/>",
        "Kexts/Release/Lilu.kext/Contents/MacOS/Lilu": b"\x00binary",
        "Kexts/Debug/Lilu.kext/Contents/Info.plist": b"<plist/>",  # should be ignored
        "README.md": b"hi",
    })
    out = tmp_path / "kexts"
    bundle = _extract_bundle(zp, "Lilu.kext", out)
    assert bundle == out / "Lilu.kext"
    assert (bundle / "Contents" / "Info.plist").read_bytes() == b"<plist/>"
    assert (bundle / "Contents" / "MacOS" / "Lilu").read_bytes() == b"\x00binary"


def test_extract_bundle_at_zip_root(tmp_path):
    zp = _make_zip(tmp_path, {
        "SMCAMDProcessor.kext/Contents/Info.plist": b"<plist/>",
        "AMDRyzenCPUPowerManagement.kext/Contents/Info.plist": b"<plist/>",
    })
    out = tmp_path / "k"
    assert _extract_bundle(zp, "SMCAMDProcessor.kext", out) == out / "SMCAMDProcessor.kext"
    assert _extract_bundle(zp, "AMDRyzenCPUPowerManagement.kext", out) is not None
    assert (out / "AMDRyzenCPUPowerManagement.kext" / "Contents" / "Info.plist").exists()


def test_extract_bundle_missing_returns_none(tmp_path):
    zp = _make_zip(tmp_path, {"Something.kext/Contents/Info.plist": b""})
    assert _extract_bundle(zp, "NotThere.kext", tmp_path / "k") is None


def test_ocbinary_tarball_shape():
    # just assert the module builds a sane URL — no network
    from ocforge.fetch import ocbinary

    assert ocbinary.TARBALL.endswith("refs/heads/master")
    assert "OcBinaryData" in ocbinary.TARBALL
    _ = io  # keep import used


def test_fetch_all_resolves_plugins_from_the_parent_bundle(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from ocforge.catalog import kexts as catalog
    from ocforge.fetch import kexts as fetch_kexts

    zp = _make_zip(tmp_path, {
        "VoodooI2C.kext/Contents/Info.plist": b"<plist/>",
        "VoodooI2C.kext/Contents/PlugIns/VoodooGPIO.kext/Contents/Info.plist": b"<plist/>",
        "VoodooI2CHID.kext/Contents/Info.plist": b"<plist/>",
    })
    monkeypatch.setattr(fetch_kexts, "latest_asset",
                        lambda repo, asset: SimpleNamespace(name="rel.zip", url="u", sha256=None, size=0))
    monkeypatch.setattr(fetch_kexts, "download",
                        lambda url, dest, **kw: dest.write_bytes(zp.read_bytes()))

    selected = [catalog.Selected(catalog.get(n), 0, 0) for n in
                ("VoodooI2CServices", "VoodooGPIO", "VoodooI2C", "VoodooI2CHID")]
    res = {r.name: r for r in fetch_kexts.fetch_all(selected, tmp_path / "w", tmp_path / "out")}

    gpio = res["VoodooGPIO"]
    assert gpio.nested and gpio.bundle_dir == tmp_path / "out" / "VoodooI2C.kext" / "Contents" / "PlugIns" / "VoodooGPIO.kext"
    # not in this (fake) release's VoodooI2C.kext -> reported, not silently dropped
    assert res["VoodooI2CServices"].bundle_dir is None
    assert "not found inside VoodooI2C.kext" in res["VoodooI2CServices"].error
    assert not res["VoodooI2C"].nested


def test_tahoe_recovery_uses_opencores_board_and_latest(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from ocforge.fetch import recovery

    seen = {}

    def fake_run(argv, **kw):
        seen["argv"] = argv
        boot = Path(argv[argv.index("-o") + 1])
        (boot / "BaseSystem.dmg").write_bytes(b"")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(recovery, "_resolve_script", lambda oc, work: tmp_path / "macrecovery.py")
    monkeypatch.setattr(recovery.subprocess, "run", fake_run)

    recovery.download(26, tmp_path, tmp_path / "dest")
    argv = seen["argv"]
    # OpenCorePkg's recovery_urls.txt; without -os latest this board serves Catalina
    assert argv[argv.index("-b") + 1] == "Mac-CFF7D910A743CAAF"
    assert argv[argv.index("-os") + 1] == "latest"

    recovery.download(15, tmp_path, tmp_path / "dest15")
    assert "-os" not in seen["argv"]
