from ocforge.build import gpio

# a slice of iasl -d output: an I2C-HID trackpad nested under PCI0 > I2C1
_DSL = r'''
DefinitionBlock ("", "DSDT", 2, "X", "Y", 1)
{
    Scope (_SB)
    {
        Device (PCI0)
        {
            Name (_HID, EisaId ("PNP0A08"))
            Device (I2C1)
            {
                Name (_HID, "INT33C3")
                Device (TPD0)
                {
                    Name (_HID, "ELAN1200")
                    Name (_CID, "PNP0C50" /* HID Protocol Device (I2C bus) */)
                    Method (_CRS, 0, NotSerialized)
                    {
                        Name (SBFB, ResourceTemplate ()
                        {
                            I2cSerialBusV2 (0x0015, ControllerInitiated, 0x00061A80,
                                AddressingMode7Bit, "_SB.PCI0.I2C1",
                                0x00, ResourceConsumer, , Exclusive,
                                )
                            GpioInt (Level, ActiveLow, ExclusiveAndWake, PullUp, 0x0000,
                                "_SB.PCI0.GPI0", 0x00, ResourceConsumer, ,
                                )
                                {   // Pin list
                                    0x0049
                                }
                        })
                        Return (SBFB)
                    }
                }
            }

            Device (GPI0)
            {
                Name (_HID, "INT344B")
            }
        }
    }
}
'''

# Real-world shape (an actual HP laptop's DSDT, not a hypothetical): the
# touchpad device exists and its _HID/_CID correctly say "I2C-HID touchpad",
# but its _CRS computes the GpioInt/I2cSerialBus descriptor at runtime from
# helper methods and concatenated buffers (board-variant globals like BADR/
# SPED/TPDM/I2CX) instead of a static ResourceTemplate literal -- so neither
# "GpioInt" nor "I2cSerialBus" appears anywhere as plain text. No regex
# rewrite can recover this; it needs an actual ACPI interpreter. Distinct
# from "no touchpad device at all" (_NO_TOUCHPAD below).
_DYNAMIC_CRS = r'''
DefinitionBlock ("", "DSDT", 2, "X", "Y", 1)
{
    Scope (_SB)
    {
        Device (PC00)
        {
            Device (I2C0)
            {
                Device (TPD0)
                {
                    Name (_HID, "XPNP0C50")
                    Name (_CID, "PNP0C50" /* HID Protocol Device (I2C bus) */)
                    Method (_CRS, 0, NotSerialized)
                    {
                        If ((TPDM == Zero))
                        {
                            Return (ConcatenateResTemplate (I2CM (I2CX, BADR, SPED), SBFG))
                        }
                        Return (ConcatenateResTemplate (I2CM (I2CX, BADR, SPED), SBFI))
                    }
                }
            }
        }
    }
}
'''

_NO_TOUCHPAD = r'''
DefinitionBlock ("", "DSDT", 2, "X", "Y", 1)
{
    Scope (_SB)
    {
        Device (PCI0)
        {
            Device (LAN0)
            {
                Name (_HID, "INT3F0D")
            }
        }
    }
}
'''


def test_scan_finds_the_i2c_hid_trackpad_only():
    found = gpio._scan(_DSL)
    assert len(found) == 1                       # not PCI0, not I2C1, not GPI0
    f = found[0]
    assert f.path == r"\_SB.PCI0.I2C1.TPD0"
    assert f.pin == 0x49
    assert f.controller == r"\_SB.PCI0.GPI0"     # root-anchored even though the DSL wasn't
    assert f.hid == "ELAN1200"


def test_scan_finds_nothing_without_a_touchpad():
    assert gpio._scan(_NO_TOUCHPAD) == []


def test_scan_is_ambiguous_with_two_trackpads():
    doubled = _DSL + _DSL.replace("TPD0", "TPD1").replace("0x0049", "0x0055")
    found = gpio._scan(doubled)
    assert len(found) == 2


def test_scan_finds_nothing_for_a_dynamically_computed_crs():
    # Confirms the premise of the dynamic-detection tests below: _scan()'s
    # literal GpioInt/I2cSerialBus text match genuinely can't see this one,
    # same as if there were no touchpad device at all.
    assert gpio._scan(_DYNAMIC_CRS) == []


def test_hid_hint_scan_finds_the_dynamic_crs_device():
    found = gpio._find_hid_hint_devices(_DYNAMIC_CRS)
    assert found == [(r"\_SB.PC00.I2C0.TPD0", "XPNP0C50")]


def test_hid_hint_scan_finds_nothing_without_a_touchpad():
    assert gpio._find_hid_hint_devices(_NO_TOUCHPAD) == []


def test_hid_hint_scan_ignores_unrelated_devices_with_pnp_ids():
    # The bare "PNP"/"ACPI" prefix _scan() allows (once GpioInt+I2cSerialBus
    # already narrowed things down) would be far too loose here, with no
    # such narrowing -- a generic ACPI device must not show up as a
    # "found a touchpad, just not a static one" false positive.
    generic = r'''
    DefinitionBlock ("", "DSDT", 2, "X", "Y", 1)
    {
        Scope (_SB)
        {
            Device (PCI0)
            {
                Name (_HID, EisaId ("PNP0A08"))
            }
        }
    }
    '''
    assert gpio._find_hid_hint_devices(generic) == []


def test_generate_reports_dynamic_crs_distinctly_from_nothing_found(monkeypatch, tmp_path):
    # generate() needs a real iasl to decompile/compile; stub both steps so
    # this test exercises just the _scan-found-nothing -> hid-hint-fallback
    # wiring, not iasl itself (which test_pipeline_gpio.py's stubs already
    # keep out of every other test here too).
    monkeypatch.setattr(gpio, "_find_iasl", lambda ssdttime_dir: tmp_path / "iasl")
    monkeypatch.setattr(gpio, "_decompile", lambda dsdt_dir, iasl: _DYNAMIC_CRS)

    finding = gpio.generate(tmp_path, tmp_path, tmp_path / "out")

    assert finding is not None and finding.dynamic and finding.generated is None
    assert finding.path == r"\_SB.PC00.I2C0.TPD0" and finding.hid == "XPNP0C50"
    assert "computed at runtime" in finding.todo()
    assert "manual SSDT-GPIO guide" in finding.todo()


def test_generate_returns_none_when_truly_nothing_is_there(monkeypatch, tmp_path):
    monkeypatch.setattr(gpio, "_find_iasl", lambda ssdttime_dir: tmp_path / "iasl")
    monkeypatch.setattr(gpio, "_decompile", lambda dsdt_dir, iasl: _NO_TOUCHPAD)
    assert gpio.generate(tmp_path, tmp_path, tmp_path / "out") is None


def test_todo_line_shape():
    f = gpio.GpioFinding(path=r"\_SB.PCI0.I2C1.TPD0", pin=0x2D,
                         controller=r"\_SB.GPO0", hid="SYNA3602")
    line = f.todo()
    assert line.startswith("SSDT-GPIO: touchpad \\_SB.PCI0.I2C1.TPD0 (SYNA3602)")
    assert "pin 0x2D" in line and "\\_SB.GPO0" in line
    assert line.isascii()


# Real-world shape (an actual HP laptop's DSDT, same device whose BADR/SPED/
# etc. drive _DYNAMIC_CRS above): the GPIO *controller* itself gates its own
# _STA/_HID behind a single variable, independent of whatever the touchpad
# device's own _CRS looks like. Dortania's manual guide documents this exact
# pattern (their own two named examples are GPEN and GPHD, with opposite
# polarity), and it's fully static -- unlike the touchpad's pin, it needs no
# live hardware value to resolve.
_GPHD_GATE = r'''
        Device (GPI0)
        {
            Method (_HID, 0, NotSerialized)
            {
                If ((GPHD == One))
                {
                    Return ("PNP0C02")
                }
                Return ("INTC1055")
            }
            Method (_STA, 0, NotSerialized)  // _STA: Status
            {
                If ((GPHD == One))
                {
                    Return (0x08)
                }
                Return (0x0F)
            }
        }
'''

_GPEN_GATE = r'''
        Device (GPI0)
        {
            Method (_STA, 0, NotSerialized)
            {
                If ((GPEN == Zero))
                {
                    Return (Zero)
                }
                Return (0x0F)
            }
        }
'''


def test_find_controller_gate_detects_gphd_style():
    assert gpio.find_controller_gate(_GPHD_GATE, r"\_SB.GPI0") == ("GPHD", "Zero")


def test_find_controller_gate_detects_gpen_style():
    # opposite polarity from GPHD above -- confirms the detection isn't
    # hardcoded to one variable name or one "true means degraded" direction
    assert gpio.find_controller_gate(_GPEN_GATE, r"\_SB.GPI0") == ("GPEN", "One")


def test_find_controller_gate_returns_none_without_a_gate():
    # _DSL's own GPI0 has no _STA at all
    assert gpio.find_controller_gate(_DSL, r"\_SB.PCI0.GPI0") is None


def test_find_controller_gate_returns_none_when_else_branch_is_not_fully_enabled():
    not_a_gate = r'''
        Device (GPI0)
        {
            Method (_STA, 0, NotSerialized)
            {
                If ((FOOB == One))
                {
                    Return (Zero)
                }
                Return (Zero)
            }
        }
    '''
    assert gpio.find_controller_gate(not_a_gate, r"\_SB.GPI0") is None


def test_generate_populates_controller_gate_on_the_success_path(monkeypatch, tmp_path):
    monkeypatch.setattr(gpio, "_find_iasl", lambda ssdttime_dir: tmp_path / "iasl")
    monkeypatch.setattr(gpio, "_decompile", lambda dsdt_dir, iasl: _DSL + _GPHD_GATE)
    monkeypatch.setattr(gpio, "_iasl", lambda *a, **k: None)  # no real iasl to compile with

    finding = gpio.generate(tmp_path, tmp_path, tmp_path / "out")

    assert finding is not None and finding.controller_gate == ("GPHD", "Zero")
    assert "GPHD" in finding.todo() and "forcing GPHD = Zero" in finding.todo()


def test_generate_populates_controller_gate_on_the_dynamic_path(monkeypatch, tmp_path):
    monkeypatch.setattr(gpio, "_find_iasl", lambda ssdttime_dir: tmp_path / "iasl")
    # _DYNAMIC_CRS's touchpad lives under \_SB.PC00.I2C0.TPD0 with no GPI0 of
    # its own; splice in a GPI0 at \_SB.GPI0 purely to exercise the dynamic
    # path wiring -- find_controller_gate() isn't told a controller path by
    # the hint-scan (it never learned one), so this only proves generate()
    # doesn't crash when dynamic and still returns dynamic=True untouched.
    monkeypatch.setattr(gpio, "_decompile", lambda dsdt_dir, iasl: _DYNAMIC_CRS)

    finding = gpio.generate(tmp_path, tmp_path, tmp_path / "out")

    assert finding is not None and finding.dynamic
    assert finding.controller_gate is None
