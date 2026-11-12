"""`ocforge build`/`offline-installer` used to print every ``plan.manual_acpi``
item twice, verbatim: once from the plan summary printed before building
(``_print_plan``), and again because the final build report's own
"still to do by hand" list (``report.manual_todo``, see
``build/pipeline.py``) already folds ``plan.manual_acpi`` back in. Real-world
report: a laptop's SSDT-GPIO (I2C-HID trackpad) note showing up twice in the
GUI's "issues in this build" list for one single build.

``cmd_plan`` (just the plan, no build) still shows the full picture once,
which is why the suppression is a parameter, not a hardcoded removal.
"""

from types import SimpleNamespace

from ocforge.cli import _print_plan


def _fake_plan(manual_acpi):
    target = SimpleNamespace(name="Ventura", major=13, darwin=22)
    return SimpleNamespace(
        target=target, smbios_model="MacBookPro15,2", boot_args=["-v"],
        kexts=[], ssdts=[], manual_acpi=manual_acpi, bios=[], warnings=[],
    )


def test_print_plan_shows_manual_acpi_by_default(capsys):
    _print_plan(_fake_plan(["SSDT-GPIO note"]))
    out = capsys.readouterr().out
    assert out.count("SSDT-GPIO note") == 1
    assert "manual ACPI" in out


def test_print_plan_can_suppress_manual_acpi_for_a_build_that_prints_its_own(capsys):
    # cmd_build/cmd_offline_installer pass this -- their own final build
    # report already shows the complete "still to do" list, manual_acpi
    # included, so printing it here too would just duplicate it verbatim.
    _print_plan(_fake_plan(["SSDT-GPIO note"]), show_manual_acpi=False)
    out = capsys.readouterr().out
    assert "SSDT-GPIO note" not in out
    assert "manual ACPI" not in out
    # everything else a build still wants to see up front is untouched
    assert "smbios" in out and "MacBookPro15,2" in out
