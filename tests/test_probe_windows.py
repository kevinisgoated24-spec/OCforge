import json

from ocforge.model import Chassis, Vendor
from ocforge.probe import windows

_BLOB = json.dumps(
    {
        "cpu": {"name": "AMD Ryzen 9 7900X 12-Core Processor", "mfr": "AuthenticAMD", "cores": 12, "threads": 24},
        "chassis": [3],
        "board": {"vendor": "ASUS", "name": "ROG STRIX X670E-E", "bios": "American Megatrends"},
        "gpus": [
            {"name": "AMD Radeon RX 6800 XT", "pnp": r"PCI\VEN_1002&DEV_73BF&SUBSYS_E4381DA2&REV_C1"},
        ],
        "nics": [
            {"name": "Intel(R) Ethernet Controller I225-V", "pnp": r"PCI\VEN_8086&DEV_15F3&SUBSYS_00001849"},
            {"name": "Intel(R) Wi-Fi 6 AX210 160MHz", "pnp": r"PCI\VEN_8086&DEV_2725&SUBSYS_00000010"},
        ],
        "nvme": [r"SCSI\DISK&VEN_NVME&PROD_SAMSUNG"],
        "i2chid": False,
    }
)


def test_parse_windows_ryzen_desktop():
    m = windows.parse(_BLOB)
    assert m.chassis is Chassis.DESKTOP
    assert m.cpu.vendor is Vendor.AMD and m.cpu.family == "Zen 4"
    assert m.cpu.cores == 12 and m.cpu.threads == 24
    assert m.dgpu is not None and m.dgpu.vendor is Vendor.AMD and m.dgpu.discrete
    assert m.dgpu.pci.vendor == "1002" and m.dgpu.pci.device == "73bf"
    assert m.dgpu.pci.sub == "1da2e438"  # SUBSYS bytes swapped to vendor:device order
    assert m.igpu is None
    assert m.storage.has_nvme
    assert m.wifi is not None and m.wifi.wireless
    assert [n.pci.device for n in m.wired_nics] == ["15f3"]
    assert m.firmware.board_name == "ROG STRIX X670E-E"


def test_pnp_id_extraction():
    pid = windows._pnp_ids(r"PCI\VEN_8086&DEV_A348&SUBSYS_12341462&REV_10")
    assert (pid.vendor, pid.device) == ("8086", "a348")
    assert pid.sub == "14621234"
    assert windows._pnp_ids("garbage").empty
