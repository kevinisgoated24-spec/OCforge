"""_resolve_plan's "unsupported GPU, continue anyway?" flow."""

import pytest

from ocforge.cli import UNSUPPORTED_GPU_EXIT, _resolve_plan
from ocforge.model import Chassis, Cpu, Gpu, Machine, Vendor


def _no_display_path_machine():
    return Machine(
        chassis=Chassis.DESKTOP,
        cpu=Cpu(brand="i5-11400F", vendor=Vendor.INTEL, intel_gen=11, cores=6, threads=12,
                flags=frozenset({"avx2"})),
        dgpu=Gpu(name="RTX 3050", vendor=Vendor.NVIDIA, discrete=True),
    )


def test_force_flag_skips_the_prompt_entirely(monkeypatch):
    called = False

    def boom(*a, **kw):
        nonlocal called
        called = True
        raise AssertionError("should not prompt when already forced")

    monkeypatch.setattr("builtins.input", boom)
    plan = _resolve_plan(_no_display_path_machine(), None, force_unsupported_gpu=True)
    assert plan is not None
    assert not called


def test_non_interactive_exits_with_the_sentinel_code_instead_of_hanging(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    def boom(*a, **kw):
        raise AssertionError("must not block on input() with no tty")

    monkeypatch.setattr("builtins.input", boom)
    with pytest.raises(SystemExit) as exc:
        _resolve_plan(_no_display_path_machine(), None, force_unsupported_gpu=False)
    assert exc.value.code == UNSUPPORTED_GPU_EXIT


def test_interactive_yes_proceeds(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    plan = _resolve_plan(_no_display_path_machine(), None, force_unsupported_gpu=False)
    assert plan is not None
    assert any("UNSUPPORTED BUILD" in w for w in plan.warnings)


def test_isatty_lying_true_but_no_real_input_exits_cleanly(monkeypatch):
    # Seen under some Windows/MSYS shells: isatty() reports True with no
    # stdin actually attached. Must not crash with a raw EOFError traceback.
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def eof(*_a, **_kw):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    with pytest.raises(SystemExit) as exc:
        _resolve_plan(_no_display_path_machine(), None, force_unsupported_gpu=False)
    assert exc.value.code == UNSUPPORTED_GPU_EXIT


def test_interactive_no_declines(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    plan = _resolve_plan(_no_display_path_machine(), None, force_unsupported_gpu=False)
    assert plan is None
