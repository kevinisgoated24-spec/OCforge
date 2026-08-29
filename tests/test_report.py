from urllib.parse import parse_qs, urlparse

from ocforge import __version__, report, spec
from ocforge.model import Chassis, Cpu, Firmware, Gpu, Machine, NetIf, PciId, Storage, Vendor


def _machine():
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand="AMD Ryzen 5 5600X", vendor=Vendor.AMD, family="Zen 3", cores=6, threads=12),
        dgpu=Gpu(name="RX 6800", vendor=Vendor.AMD, pci=PciId("1002", "73bf"), discrete=True),
        net=[NetIf(name="RTL8125", vendor=Vendor.REALTEK, pci=PciId("10ec", "8125"))],
        storage=Storage(has_nvme=True),
        firmware=Firmware(board_vendor="ASUS", board_name="TUF B550-PLUS"),
    )


def test_format_machine():
    text = report.format_machine(_machine())
    assert "chassis   desktop" in text
    assert "cpu       AMD Ryzen 5 5600X  [amd / Zen 3]  6c/12t" in text
    assert "gpu       dGPU: RX 6800 (amd)  [1002:73bf]" in text
    assert "eth       RTL8125 (realtek)" in text
    assert "storage   nvme=yes" in text
    assert "board     ASUS TUF B550-PLUS" in text


def test_build_url_from_a_spec_file(tmp_path):
    p = tmp_path / "spec.json"
    spec.save(_machine(), p)

    url = report.build_url(spec_path=str(p), title="[Bug]: still panics")
    assert url.startswith(f"https://github.com/{report.REPO}/issues/new?")

    qs = parse_qs(urlparse(url).query)
    assert qs["template"] == ["bug_report.yml"]
    assert qs["labels"] == ["bug"]
    assert qs["title"] == ["[Bug]: still panics"]
    assert qs["ocforge-version"] == [__version__]
    assert qs["os"][0] in ("Windows", "macOS", "Linux")
    assert "AMD Ryzen 5 5600X" in qs["hardware"][0]


def test_build_url_falls_back_when_spec_missing(tmp_path):
    # a bogus spec path shouldn't crash report generation, only degrade it
    url = report.build_url(spec_path=str(tmp_path / "nope.json"))
    assert url.startswith(f"https://github.com/{report.REPO}/issues/new?")
    qs = parse_qs(urlparse(url).query)
    assert "hardware" in qs and qs["hardware"][0]  # never empty
