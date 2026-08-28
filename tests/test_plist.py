import datetime
import json
import plistlib

from ocforge import plist as plistio


def _write(tmp_path, data):
    p = tmp_path / "config.plist"
    with open(p, "wb") as fh:
        plistlib.dump(data, fh, sort_keys=False)
    return p


SAMPLE = {
    "PlatformInfo": {"Generic": {
        "SystemProductName": "MacPro7,1",
        "ROM": b"\x88\x63\xdf\xac\x69\xba",
        "SpoofVendor": True,
    }},
    "NVRAM": {"Add": {"7C4-guid": {"boot-args": "-v debug=0x100", "csr-active-config": b"\x00\x00\x00\x00"}}},
    "Misc": {"Boot": {"Timeout": 8, "PickerVariant": "Auto"}},
    "when": datetime.datetime(2026, 1, 2, 3, 4, 5),  # noqa: DTZ001 - plist dates are naive
}


def test_roundtrip_is_byte_identical(tmp_path):
    src = _write(tmp_path, SAMPLE)
    text = plistio.to_json(src)

    # JSON is real JSON and uses the hex/date sentinels
    obj = json.loads(text)
    assert obj["PlatformInfo"]["Generic"]["ROM"] == {"__data__": "8863dfac69ba"}
    assert obj["when"] == {"__date__": "2026-01-02T03:04:05"}

    out = tmp_path / "back.plist"
    plistio.from_json(text, out)
    assert plistlib.loads(out.read_bytes()) == SAMPLE


def test_edited_value_survives_roundtrip(tmp_path):
    src = _write(tmp_path, SAMPLE)
    obj = json.loads(plistio.to_json(src))
    obj["Misc"]["Boot"]["Timeout"] = 3
    obj["PlatformInfo"]["Generic"]["ROM"] = {"__data__": "001122334455"}

    plistio.from_json(json.dumps(obj), src)
    got = plistlib.loads(src.read_bytes())
    assert got["Misc"]["Boot"]["Timeout"] == 3
    assert got["PlatformInfo"]["Generic"]["ROM"] == bytes.fromhex("001122334455")
    assert list(got["PlatformInfo"]["Generic"]) == ["SystemProductName", "ROM", "SpoofVendor"]


def test_find_config_locates_efi_layout(tmp_path):
    import argparse

    from ocforge.cli import _find_config

    (tmp_path / "EFI" / "OC").mkdir(parents=True)
    cfg = tmp_path / "EFI" / "OC" / "config.plist"
    cfg.write_bytes(b"x")

    ns = argparse.Namespace(config=None, efi=str(tmp_path))
    assert _find_config(ns) == cfg
    ns = argparse.Namespace(config=str(cfg), efi=None)
    assert _find_config(ns) == cfg
    ns = argparse.Namespace(config=None, efi=str(tmp_path / "nope"))
    assert _find_config(ns) is None
