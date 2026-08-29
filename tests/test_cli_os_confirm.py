"""_resolve_plan's "unsupported macOS target, continue anyway?" flow --
the OS-version counterpart of test_cli_gpu_confirm.py's GPU flow.

Real-world motivation: a Dell Inspiron 15-3567 (7th-gen Kaby Lake) forced
through --macos 26 (Tahoe, needs 8th gen+) used to build with zero warning
and produced a real install with corrupted/garbled graphics on first boot.
"""

import pytest

from ocforge.cli import UNSUPPORTED_OS_EXIT, _resolve_plan
from ocforge.model import Chassis, Cpu, Gpu, Machine, PciId, Vendor


def _kaby_lake_laptop():
    return Machine(
        chassis=Chassis.LAPTOP,
        cpu=Cpu(brand="i5-7200U", vendor=Vendor.INTEL, family="Kaby Lake", intel_gen=7,
                cores=2, threads=4, flags=frozenset({"avx2"})),
        igpu=Gpu(name="HD 620", vendor=Vendor.INTEL, pci=PciId("8086", "5916")),
    )


def test_force_flag_skips_the_prompt_entirely(monkeypatch):
    called = False

    def boom(*a, **kw):
        nonlocal called
        called = True
        raise AssertionError("should not prompt when already forced")

    monkeypatch.setattr("builtins.input", boom)
    plan = _resolve_plan(_kaby_lake_laptop(), 26, force_unsupported_gpu=False,
                         force_unsupported_os=True)
    assert plan is not None
    assert not called


def test_non_interactive_exits_with_the_sentinel_code_instead_of_hanging(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    def boom(*a, **kw):
        raise AssertionError("must not block on input() with no tty")

    monkeypatch.setattr("builtins.input", boom)
    with pytest.raises(SystemExit) as exc:
        _resolve_plan(_kaby_lake_laptop(), 26, force_unsupported_gpu=False,
                      force_unsupported_os=False)
    assert exc.value.code == UNSUPPORTED_OS_EXIT


def test_interactive_yes_proceeds(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    plan = _resolve_plan(_kaby_lake_laptop(), 26, force_unsupported_gpu=False,
                         force_unsupported_os=False)
    assert plan is not None
    assert any("UNSUPPORTED macOS TARGET" in w for w in plan.warnings)


def test_interactive_no_declines(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    plan = _resolve_plan(_kaby_lake_laptop(), 26, force_unsupported_gpu=False,
                         force_unsupported_os=False)
    assert plan is None


def test_a_supported_forced_target_never_prompts(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("a supported --macos shouldn't hit the prompt at all")

    monkeypatch.setattr("builtins.input", boom)
    plan = _resolve_plan(_kaby_lake_laptop(), 15, force_unsupported_gpu=False,
                         force_unsupported_os=False)
    assert plan is not None and plan.target.major == 15
