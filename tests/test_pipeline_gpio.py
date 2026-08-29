"""Auto-triggering ACPI dump (+SSDTTime) for a laptop's I2C-HID trackpad,
without needing --dsdt/--dump-dsdt — see ocforge.build.pipeline._run_ssdttime.

Platform checks are explicitly monkeypatched (pipeline.sys.platform) rather
than relying on whatever host happens to run the suite, so these pass the
same way on a Windows, macOS, or Linux CI runner.
"""

from ocforge.build import pipeline
from ocforge.build.plan import make
from ocforge.build.ssdtgen import SsdtResult
from ocforge.model import Chassis, Cpu, Gpu, Input, Machine, Vendor


def _laptop_i2c_hid():
    return Machine(
        chassis=Chassis.LAPTOP,
        cpu=Cpu(brand="i7-8650U", vendor=Vendor.INTEL, intel_gen=8, cores=4, threads=8,
                flags=frozenset({"avx2"})),
        igpu=Gpu(name="UHD 620", vendor=Vendor.INTEL),
        inputs=Input(has_touchpad=True, touchpad_bus="i2c-hid"),
    )


def _stub_ssdttime(monkeypatch, *, dumped: list, fetched: list, acpidump_fetched: list | None = None,
                   platform: str = "linux"):
    if acpidump_fetched is None:
        acpidump_fetched = []

    def fake_can_dump():
        return platform == "linux"

    def fake_dump_tables(dest, *, acpidump_exe=None):
        dumped.append((dest, acpidump_exe))
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "DSDT.aml").write_bytes(b"DSDT")
        return dest

    def fake_fetch(work):
        fetched.append(work)
        return work / "ssdttime-stub"

    def fake_fetch_acpidump(work):
        acpidump_fetched.append(work)
        return work / "acpidump-stub" / "acpidump.exe"

    def fake_run(ssdttime_dir, acpi_dir, ops, *, log=lambda _: None, timeout=600):
        return SsdtResult(aml=[acpi_dir / "SSDT-FAKE.aml"])

    monkeypatch.setattr(pipeline.sys, "platform", platform)
    monkeypatch.setattr(pipeline.acpi_dump, "can_dump", fake_can_dump)
    monkeypatch.setattr(pipeline.acpi_dump, "dump_tables", fake_dump_tables)
    monkeypatch.setattr(pipeline.fetch_ssdttime, "fetch", fake_fetch)
    monkeypatch.setattr(pipeline.fetch_acpidump, "fetch", fake_fetch_acpidump)
    monkeypatch.setattr(pipeline.ssdtgen, "run", fake_run)
    monkeypatch.setattr(
        "ocforge.build.gpio.generate", lambda acpi_dir, st_dir, out_dir: None
    )


def test_laptop_with_i2c_hid_trackpad_auto_dumps_on_linux(tmp_path, monkeypatch):
    dumped, fetched = [], []
    _stub_ssdttime(monkeypatch, dumped=dumped, fetched=fetched, platform="linux")

    plan = make(_laptop_i2c_hid())
    res = pipeline._run_ssdttime(plan, tmp_path, dsdt=None, dump_dsdt=False, log=lambda _: None)

    assert res is not None and res.ok
    assert dumped  # ACPI dump ran even though dump_dsdt=False


def test_laptop_with_i2c_hid_trackpad_auto_dumps_on_windows(tmp_path, monkeypatch):
    # Windows can dump too, but needs acpidump.exe fetched first (separately
    # from SSDTTime -- see fetch/acpidump.py) -- can_dump() alone is False
    # there; host_can_dump should still be True.
    dumped, fetched, acpidump_fetched = [], [], []
    _stub_ssdttime(monkeypatch, dumped=dumped, fetched=fetched,
                   acpidump_fetched=acpidump_fetched, platform="win32")

    plan = make(_laptop_i2c_hid())
    res = pipeline._run_ssdttime(plan, tmp_path, dsdt=None, dump_dsdt=False, log=lambda _: None)

    assert res is not None and res.ok
    assert dumped
    (_dump_dest, acpidump_exe), = dumped
    assert acpidump_exe is not None  # fetched before the dump was attempted
    assert acpidump_fetched and acpidump_fetched[0] == tmp_path
    assert fetched and fetched[0] == tmp_path  # SSDTTime itself, for iasl


def test_laptop_with_i2c_hid_trackpad_does_not_auto_dump_on_macos(tmp_path, monkeypatch):
    # macOS has no automatic ACPI dump path at all, from ocforge or SSDTTime.
    dumped, fetched = [], []
    _stub_ssdttime(monkeypatch, dumped=dumped, fetched=fetched, platform="darwin")

    plan = make(_laptop_i2c_hid())
    res = pipeline._run_ssdttime(plan, tmp_path, dsdt=None, dump_dsdt=False, log=lambda _: None)

    assert res is None
    assert not dumped
    assert not fetched  # bailed before ever fetching SSDTTime


def test_desktop_does_not_auto_dump(tmp_path, monkeypatch):
    dumped, fetched = [], []
    _stub_ssdttime(monkeypatch, dumped=dumped, fetched=fetched)

    plan = make(_laptop_i2c_hid())
    plan.machine.chassis = Chassis.DESKTOP  # not a laptop -> no auto-trigger
    res = pipeline._run_ssdttime(plan, tmp_path, dsdt=None, dump_dsdt=False, log=lambda _: None)

    assert res is None
    assert not dumped


def test_laptop_without_i2c_hid_touchpad_does_not_auto_dump(tmp_path, monkeypatch):
    dumped, fetched = [], []
    _stub_ssdttime(monkeypatch, dumped=dumped, fetched=fetched)

    m = _laptop_i2c_hid()
    m.inputs.touchpad_bus = "ps2"
    plan = make(m)
    res = pipeline._run_ssdttime(plan, tmp_path, dsdt=None, dump_dsdt=False, log=lambda _: None)

    assert res is None
    assert not dumped


def test_explicit_dsdt_still_wins_over_auto_gpio(tmp_path, monkeypatch):
    dumped, fetched = [], []
    _stub_ssdttime(monkeypatch, dumped=dumped, fetched=fetched)

    def fake_stage(dsdt, dest):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "DSDT.aml").write_bytes(b"DSDT")
        return dest

    monkeypatch.setattr(pipeline.acpi_dump, "stage_supplied", fake_stage)

    supplied = tmp_path / "my-dsdt"
    supplied.mkdir()
    plan = make(_laptop_i2c_hid())
    res = pipeline._run_ssdttime(plan, tmp_path, dsdt=supplied, dump_dsdt=False, log=lambda _: None)

    assert res is not None and res.ok
    assert not dumped  # supplied --dsdt was used, not the auto-dump path


def test_explicit_dump_dsdt_flag_works_on_windows_too(tmp_path, monkeypatch):
    dumped, fetched = [], []
    _stub_ssdttime(monkeypatch, dumped=dumped, fetched=fetched, platform="win32")

    # A desktop (no i2c-hid trackpad, so no auto_gpio) explicitly asking for
    # --dump-dsdt should still work on Windows now.
    plan = make(_laptop_i2c_hid())
    plan.machine.chassis = Chassis.DESKTOP
    res = pipeline._run_ssdttime(plan, tmp_path, dsdt=None, dump_dsdt=True, log=lambda _: None)

    assert res is not None and res.ok
    assert dumped
