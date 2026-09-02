"""--exclude-kext/--include-kext/--exclude-ssdt/--smbios/--quirk CLI wiring."""

import pytest

from ocforge.cli import _parse_quirk_args, build_parser


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
