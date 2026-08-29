from pathlib import Path

from ocforge.build.offline_installer import stage
from ocforge.build.plan import make
from ocforge.model import Chassis, Cpu, Gpu, Machine, Vendor


def _machine():
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand="i7-8700K", vendor=Vendor.INTEL, family="Coffee Lake", intel_gen=8,
                cores=6, threads=12, flags=frozenset({"avx2"})),
        igpu=Gpu(name="UHD 630", vendor=Vendor.INTEL, discrete=False),
    )


def _fake_pkg(tmp_path: Path) -> Path:
    p = tmp_path / "downloads" / "InstallAssistant.pkg"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"fake pkg")
    return p


def _fake_script(tmp_path: Path) -> Path:
    p = tmp_path / "UnPlugged.command"
    p.write_text("#!/bin/bash\necho fake\n")
    return p


def _fake_recovery_boot(out: Path) -> Path:
    boot = out / "com.apple.recovery.boot"
    boot.mkdir(parents=True)
    (boot / "BaseSystem.dmg").write_bytes(b"fake dmg")
    return boot


def test_stage_lays_out_exfat_payload(tmp_path, monkeypatch):
    plan = make(_machine(), target_major=13)  # Ventura: no Sonoma+ boot-major split
    pkg = _fake_pkg(tmp_path)
    script = _fake_script(tmp_path)

    monkeypatch.setattr(
        "ocforge.build.offline_installer.gibmacos.download_installer",
        lambda work, version, **kw: pkg,
    )
    monkeypatch.setattr(
        "ocforge.build.offline_installer.unplugged.fetch",
        lambda work: script,
    )
    monkeypatch.setattr(
        "ocforge.build.offline_installer.fetch_recovery.download",
        lambda major, opencore_dir, dest, **kw: _fake_recovery_boot(dest),
    )

    out = tmp_path / "out"
    report = stage(plan, tmp_path / "work", out, log=lambda _: None)

    assert report.boot_major == 13  # no split below Sonoma
    assert not any("Recovery can't mount" in n for n in report.notes)
    assert (out / "ExFAT" / "InstallAssistant.pkg").read_bytes() == b"fake pkg"
    assert (out / "ExFAT" / "UnPlugged.command").exists()
    assert report.recovery_boot == out / "com.apple.recovery.boot"


def test_stage_uses_older_basesystem_for_sonoma_plus(tmp_path, monkeypatch):
    plan = make(_machine(), target_major=15)  # Sequoia
    pkg = _fake_pkg(tmp_path)
    script = _fake_script(tmp_path)
    seen_majors = []

    monkeypatch.setattr(
        "ocforge.build.offline_installer.gibmacos.download_installer",
        lambda work, version, **kw: pkg,
    )
    monkeypatch.setattr(
        "ocforge.build.offline_installer.unplugged.fetch",
        lambda work: script,
    )

    def fake_download(major, opencore_dir, dest, **kw):
        seen_majors.append(major)
        return _fake_recovery_boot(dest)

    monkeypatch.setattr(
        "ocforge.build.offline_installer.fetch_recovery.download", fake_download
    )

    out = tmp_path / "out"
    report = stage(plan, tmp_path / "work", out, log=lambda _: None)

    assert report.boot_major == 12  # Monterey, per UnPlugged's README
    assert seen_majors == [12]  # downloaded the boot image, not target-major (15)
    assert any("Recovery can't mount" in n for n in report.notes)
