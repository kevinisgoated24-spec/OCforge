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
