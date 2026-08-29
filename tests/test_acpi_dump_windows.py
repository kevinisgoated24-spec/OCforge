"""ocforge.probe.acpi_dump's Windows path (the fetched acpidump.exe).

subprocess.run is monkeypatched throughout -- these never invoke a real
acpidump.exe (fetched separately by fetch/acpidump.py; not vendored in this
repo), just the file-handling logic around it.
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


def test_can_dump_stays_linux_only(monkeypatch):
    # can_dump() itself stays Linux-only -- Windows needs acpidump.exe
    # fetched first, which pipeline._run_ssdttime checks via sys.platform
    # instead. Just a sanity check that can_dump() doesn't quietly start
    # claiming Windows/macOS support too.
    monkeypatch.setattr(acpi_dump.sys, "platform", "win32")
    assert acpi_dump.can_dump() is False
    monkeypatch.setattr(acpi_dump.sys, "platform", "darwin")
    assert acpi_dump.can_dump() is False
