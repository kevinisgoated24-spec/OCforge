"""fetch/acpidump.py + fetch/iasl.py: ACPICA stopped publishing Windows .exe
assets at all on its newest release (20260930) -- these pull from "latest"
first, but fall back to the last release known to actually have them
(20260408) when "latest" comes up empty. Real-world motivation: this release
gap, combined with a bug in SSDTTime's own bundled-iasl fallback, produced
zero SSDTs (no menu ever ran) on an otherwise perfectly fine laptop.
"""

import pytest

from ocforge.fetch import acpidump, github, iasl

_LATEST_NO_WINDOWS = {
    "tag_name": "20260930",
    "assets": [
        {"name": "acpidump", "browser_download_url": "https://x/acpidump", "size": 70_000},
        {"name": "iasl", "browser_download_url": "https://x/iasl", "size": 1_500_000},
    ],
}

_PINNED_HAS_WINDOWS = {
    "tag_name": "20260408",
    "assets": [
        {"name": "acpidump.exe", "browser_download_url": "https://x/acpidump.exe",
         "size": 71_000, "digest": "sha256:deadbeef"},
        {"name": "acpidump_dbg.exe", "browser_download_url": "https://x/acpidump_dbg.exe",
         "size": 90_000},
        {"name": "iasl.exe", "browser_download_url": "https://x/iasl.exe",
         "size": 1_600_000, "digest": "sha256:cafef00d"},
        {"name": "iasl_dbg.exe", "browser_download_url": "https://x/iasl_dbg.exe",
         "size": 2_000_000},
    ],
}


def _fake_release_json(repo, tag):
    assert repo == "open-acpica/acpica"
    if tag in (None, "latest"):
        return _LATEST_NO_WINDOWS
    assert tag == "20260408"
    return _PINNED_HAS_WINDOWS


def test_acpidump_falls_back_to_pinned_tag_when_latest_has_no_windows_binaries(monkeypatch, tmp_path):
    monkeypatch.setattr(github, "_release_json", _fake_release_json)
    monkeypatch.setattr(acpidump, "download",
                        lambda url, dest, **kw: dest.parent.mkdir(parents=True, exist_ok=True)
                        or dest.write_bytes(b"fake acpidump.exe"))
    dest = acpidump.fetch(tmp_path)
    assert dest.is_file()
    assert dest.read_bytes() == b"fake acpidump.exe"


def test_iasl_falls_back_to_pinned_tag_when_latest_has_no_windows_binaries(monkeypatch, tmp_path):
    monkeypatch.setattr(github, "_release_json", _fake_release_json)
    monkeypatch.setattr(iasl, "download",
                        lambda url, dest, **kw: dest.parent.mkdir(parents=True, exist_ok=True)
                        or dest.write_bytes(b"fake iasl.exe"))
    dest = iasl.fetch(tmp_path)
    assert dest.is_file()
    assert dest.read_bytes() == b"fake iasl.exe"


def test_iasl_prefers_release_over_debug_build(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(github, "_release_json", _fake_release_json)
    monkeypatch.setattr(iasl, "download",
                        lambda url, dest, **kw: captured.setdefault("url", url) or
                        (dest.parent.mkdir(parents=True, exist_ok=True) or dest.write_bytes(b"x")))
    iasl.fetch(tmp_path)
    assert captured["url"] == "https://x/iasl.exe"  # not iasl_dbg.exe


def test_fetch_raises_when_neither_latest_nor_pinned_has_it(monkeypatch, tmp_path):
    monkeypatch.setattr(github, "_release_json", lambda repo, tag: {"assets": []})
    with pytest.raises(LookupError):
        iasl.fetch(tmp_path)
