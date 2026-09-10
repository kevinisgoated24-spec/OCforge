"""ocforge.probe.acpi_dump's Windows paths.

Two paths are covered:

* ``_dump_windows_native`` -- the driver-free ``GetSystemFirmwareTable`` call,
  with the ctypes helpers (``_get_acpi_table`` / ``_enum_acpi_tables``)
  monkeypatched so nothing touches real firmware.
* ``_dump_windows`` -- the fetched ``acpidump.exe`` fallback, with
  ``subprocess.run`` monkeypatched (that exe is fetched separately by
  fetch/acpidump.py and isn't vendored here).
"""

import subprocess

import pytest

from ocforge.probe import acpi_dump


def _make_exe(tmp_path):
    exe = tmp_path / "acpidump.exe"
    exe.write_bytes(b"not a real exe, just needs to exist")
    return exe


def test_missing_exe_path_raises(tmp_path):
    with pytest.raises(acpi_dump.DsdtUnavailable, match="acpidump.exe"):
        acpi_dump._dump_windows(tmp_path / "out", None)


def test_nonexistent_exe_raises(tmp_path):
    with pytest.raises(acpi_dump.DsdtUnavailable, match="acpidump.exe"):
        acpi_dump._dump_windows(tmp_path / "out", tmp_path / "nope" / "acpidump.exe")


def test_normalizes_names_and_drops_non_dsdt_ssdt_tables(tmp_path, monkeypatch):
    exe = _make_exe(tmp_path)
    out = tmp_path / "out"

    def fake_run(argv, *, cwd, capture_output, text, timeout, check):
        # Simulate `acpidump.exe -b` dumping the whole table set, lowercase
        # names + .dat extension, exactly like the real tool does.
        d = acpi_dump.Path(cwd)
        for name in ("dsdt.dat", "ssdt1.dat", "ssdt2.dat", "facp.dat", "apic.dat"):
            (d / name).write_bytes(b"table")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(acpi_dump.subprocess, "run", fake_run)
    result = acpi_dump._dump_windows(out, exe)

    names = {p.name for p in result.iterdir()}
    assert names == {"DSDT.aml", "SSDT1.aml", "SSDT2.aml"}  # FACP/APIC dropped


def test_falls_back_to_signature_dump_when_no_dsdt_found(tmp_path, monkeypatch):
    exe = _make_exe(tmp_path)
    out = tmp_path / "out"
    calls = []

    def fake_run(argv, *, cwd, capture_output, text, timeout, check):
        calls.append(argv)
        d = acpi_dump.Path(cwd)
        if "-n" in argv:
            (d / "dsdt.dat").write_bytes(b"table")
        else:
            (d / "ssdt1.dat").write_bytes(b"table")  # first pass: no DSDT
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(acpi_dump.subprocess, "run", fake_run)
    result = acpi_dump._dump_windows(out, exe)

    assert (result / "DSDT.aml").exists()
    assert any("-n" in c and "DSDT" in c for c in calls)


def test_nonzero_exit_raises(tmp_path, monkeypatch):
    exe = _make_exe(tmp_path)

    def fake_run(argv, *, cwd, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="access denied")

    monkeypatch.setattr(acpi_dump.subprocess, "run", fake_run)
    with pytest.raises(acpi_dump.DsdtUnavailable, match="access denied"):
        acpi_dump._dump_windows(tmp_path / "out", exe)


def test_can_dump_true_on_windows_false_on_macos(monkeypatch):
    # Windows now has a local path (native GetSystemFirmwareTable, no
    # acpidump.exe download needed), so can_dump() claims it. macOS still
    # has no automatic path at all.
    monkeypatch.setattr(acpi_dump.sys, "platform", "win32")
    assert acpi_dump.can_dump() is True
    monkeypatch.setattr(acpi_dump.sys, "platform", "darwin")
    assert acpi_dump.can_dump() is False


def test_sig_dword_is_little_endian():
    assert acpi_dump._sig_dword(b"DSDT") == 0x54445344
    assert acpi_dump._sig_dword(b"SSDT") == 0x54445353


# ---- native GetSystemFirmwareTable path ----

def _fake_acpi(dsdt=b"DSDT\x00rest", ssdts=(b"SSDT\x00one", b"SSDT\x00two")):
    """Build (get_table, enum_tables) stand-ins for a host with one DSDT and
    the given SSDT payloads. get_table returns the first SSDT for the repeated
    signature, matching the real Win32 limitation."""
    tables = {b"DSDT": dsdt}
    first_ssdt = ssdts[0] if ssdts else None

    def get_table(sig):
        if sig == b"DSDT":
            return dsdt
        if sig == b"SSDT":
            return first_ssdt
        return None

    def enum_tables():
        return [b"FACP", b"DSDT"] + [b"SSDT"] * len(ssdts) + [b"APIC"]

    return get_table, enum_tables


def test_native_dump_writes_dsdt_and_distinct_ssdts(tmp_path, monkeypatch):
    get_table, enum_tables = _fake_acpi(
        dsdt=b"DSDT\x00body", ssdts=(b"SSDT\x00alpha", b"SSDT\x00beta")
    )
    monkeypatch.setattr(acpi_dump, "_get_acpi_table", get_table)
    monkeypatch.setattr(acpi_dump, "_enum_acpi_tables", enum_tables)

    out = acpi_dump._dump_windows_native(tmp_path / "out")

    assert (out / "DSDT.aml").read_bytes() == b"DSDT\x00body"
    names = sorted(p.name for p in out.iterdir())
    # Only the first SSDT is retrievable via GetSystemFirmwareTable, so we get
    # DSDT + that one SSDT (deduped), never a phantom SSDT-2.
    assert names == ["DSDT.aml", "SSDT-1.aml"]
    assert (out / "SSDT-1.aml").read_bytes() == b"SSDT\x00alpha"


def test_native_dump_raises_when_no_dsdt(tmp_path, monkeypatch):
    monkeypatch.setattr(acpi_dump, "_get_acpi_table", lambda sig: None)
    monkeypatch.setattr(acpi_dump, "_enum_acpi_tables", list)
    with pytest.raises(acpi_dump.DsdtUnavailable, match="GetSystemFirmwareTable"):
        acpi_dump._dump_windows_native(tmp_path / "out")


def test_native_dump_rejects_garbage_dsdt(tmp_path, monkeypatch):
    monkeypatch.setattr(acpi_dump, "_get_acpi_table", lambda sig: b"\x00\x00\x00\x00junk")
    monkeypatch.setattr(acpi_dump, "_enum_acpi_tables", lambda: [b"DSDT"])
    with pytest.raises(acpi_dump.DsdtUnavailable):
        acpi_dump._dump_windows_native(tmp_path / "out")


def test_dump_tables_prefers_native_over_acpidump(tmp_path, monkeypatch):
    monkeypatch.setattr(acpi_dump.sys, "platform", "win32")
    monkeypatch.setattr(
        acpi_dump, "_get_acpi_table",
        lambda sig: b"DSDT\x00x" if sig == b"DSDT" else None,
    )
    monkeypatch.setattr(acpi_dump, "_enum_acpi_tables", lambda: [b"DSDT"])

    def boom(*a, **k):
        raise AssertionError("acpidump.exe fallback should not run")

    monkeypatch.setattr(acpi_dump, "_dump_windows", boom)

    out = acpi_dump.dump_tables(tmp_path / "out", acpidump_exe=tmp_path / "acpidump.exe")
    assert (out / "DSDT.aml").exists()


def test_dump_tables_falls_back_to_acpidump_when_native_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(acpi_dump.sys, "platform", "win32")
    monkeypatch.setattr(acpi_dump, "_get_acpi_table", lambda sig: None)
    monkeypatch.setattr(acpi_dump, "_enum_acpi_tables", list)
    called = {}

    def fake_fallback(dest, exe):
        called["exe"] = exe
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "DSDT.aml").write_bytes(b"DSDT\x00fb")
        return dest

    monkeypatch.setattr(acpi_dump, "_dump_windows", fake_fallback)

    exe = tmp_path / "acpidump.exe"
    out = acpi_dump.dump_tables(tmp_path / "out", acpidump_exe=exe)
    assert called["exe"] == exe
    assert (out / "DSDT.aml").read_bytes() == b"DSDT\x00fb"


def test_dump_tables_native_fail_no_fallback_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(acpi_dump.sys, "platform", "win32")
    monkeypatch.setattr(acpi_dump, "_get_acpi_table", lambda sig: None)
    monkeypatch.setattr(acpi_dump, "_enum_acpi_tables", list)
    with pytest.raises(acpi_dump.DsdtUnavailable, match="native ACPI dump failed"):
        acpi_dump.dump_tables(tmp_path / "out", acpidump_exe=None)
