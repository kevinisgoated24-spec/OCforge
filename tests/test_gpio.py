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


def test_todo_line_shape():
    f = gpio.GpioFinding(path=r"\_SB.PCI0.I2C1.TPD0", pin=0x2D,
                         controller=r"\_SB.GPO0", hid="SYNA3602")
    line = f.todo()
    assert line.startswith("SSDT-GPIO: touchpad \\_SB.PCI0.I2C1.TPD0 (SYNA3602)")
    assert "pin 0x2D" in line and "\\_SB.GPO0" in line
    assert line.isascii()
