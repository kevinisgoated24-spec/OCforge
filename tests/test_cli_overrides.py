"""--exclude-kext/--include-kext/--exclude-ssdt/--smbios/--quirk/--spoof-device CLI wiring."""

import pytest

from ocforge.cli import _parse_quirk_args, _parse_spoof_device_args, build_parser


def test_parse_quirk_args_happy_path():
    assert _parse_quirk_args(["DevirtualiseMmio=true", "SetupVirtualMap=False"]) == {
        "DevirtualiseMmio": True,
        "SetupVirtualMap": False,
    }


def test_parse_quirk_args_empty():
    assert _parse_quirk_args(None) == {}
    assert _parse_quirk_args([]) == {}


def test_parse_quirk_args_missing_equals_raises():
    with pytest.raises(ValueError, match="NAME=true\\|false"):
        _parse_quirk_args(["DevirtualiseMmio"])


def test_parse_quirk_args_bad_value_raises():
    with pytest.raises(ValueError, match="'true' or 'false'"):
        _parse_quirk_args(["DevirtualiseMmio=maybe"])


@pytest.mark.parametrize("cmd", ["plan", "explain", "build", "offline-installer"])
def test_smbios_and_exclude_ssdt_on_every_plan_producing_command(cmd):
    p = build_parser()
    ns = p.parse_args([cmd, "--smbios", "iMac19,1", "--exclude-ssdt", "SSDT-PLUG"])
    assert ns.smbios == "iMac19,1"
    assert ns.exclude_ssdt == ["SSDT-PLUG"]


@pytest.mark.parametrize("cmd", ["build", "offline-installer"])
def test_quirk_flag_only_on_build_commands(cmd):
    p = build_parser()
    ns = p.parse_args([cmd, "--quirk", "DevirtualiseMmio=false"])
    assert ns.quirk == ["DevirtualiseMmio=false"]


@pytest.mark.parametrize("cmd", ["plan", "explain"])
def test_quirk_flag_absent_from_plan_and_explain(cmd):
    p = build_parser()
    ns = p.parse_args([cmd])
    assert not hasattr(ns, "quirk")


def test_parse_spoof_device_args_device_only():
    assert _parse_spoof_device_args(["PciRoot(0x0)/Pci(0x3,0x0)=73AF"]) == {
        "PciRoot(0x0)/Pci(0x3,0x0)": {"device-id": 0x73AF},
    }


def test_parse_spoof_device_args_vendor_and_device():
    assert _parse_spoof_device_args(["PciRoot(0x0)/Pci(0x3,0x0)=1002:73AF"]) == {
        "PciRoot(0x0)/Pci(0x3,0x0)": {"device-id": 0x73AF, "vendor-id": 0x1002},
    }


def test_parse_spoof_device_args_empty():
    assert _parse_spoof_device_args(None) == {}
    assert _parse_spoof_device_args([]) == {}


def test_parse_spoof_device_args_missing_equals_raises():
    with pytest.raises(ValueError, match="PATH=\\[VENDOR:\\]DEVICE"):
        _parse_spoof_device_args(["PciRoot(0x0)/Pci(0x3,0x0)"])


def test_parse_spoof_device_args_empty_path_raises():
    with pytest.raises(ValueError, match="PATH=\\[VENDOR:\\]DEVICE"):
        _parse_spoof_device_args(["=73AF"])


def test_parse_spoof_device_args_bad_device_hex_raises():
    with pytest.raises(ValueError, match="device id must be 1-4 hex digits"):
        _parse_spoof_device_args(["PciRoot(0x0)/Pci(0x3,0x0)=zzzz"])


def test_parse_spoof_device_args_bad_vendor_hex_raises():
    with pytest.raises(ValueError, match="vendor id must be 1-4 hex digits"):
        _parse_spoof_device_args(["PciRoot(0x0)/Pci(0x3,0x0)=zzzz:73AF"])


def test_parse_spoof_device_args_too_long_hex_raises():
    with pytest.raises(ValueError, match="device id must be 1-4 hex digits"):
        _parse_spoof_device_args(["PciRoot(0x0)/Pci(0x3,0x0)=73AFF"])


@pytest.mark.parametrize("cmd", ["build", "offline-installer"])
def test_spoof_device_flag_only_on_build_commands(cmd):
    p = build_parser()
    ns = p.parse_args([cmd, "--spoof-device", "PciRoot(0x0)/Pci(0x3,0x0)=73AF"])
    assert ns.spoof_device == ["PciRoot(0x0)/Pci(0x3,0x0)=73AF"]


@pytest.mark.parametrize("cmd", ["plan", "explain"])
def test_spoof_device_flag_absent_from_plan_and_explain(cmd):
    p = build_parser()
    ns = p.parse_args([cmd])
    assert not hasattr(ns, "spoof_device")
