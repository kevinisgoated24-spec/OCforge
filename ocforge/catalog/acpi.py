"""Which SSDTs the config needs.

Every SSDT selected here is a *hotpatch* - it uses ``External`` refs and
``_STA`` conditionals, so it works without recompiling against the machine's
own DSDT. They come straight from Dortania's precompiled set
(``Getting-Started-With-ACPI/extra-files/compiled`` on ``master``).

DSDT-derived tables (e.g. per-board GPIO pinning for I2C trackpads) are out of
scope for now and flagged in the plan as a manual follow-up.
"""

from __future__ import annotations

from dataclasses import dataclass

from ocforge.model import Machine, Vendor

DORTANIA_ACPI = "dortania/Getting-Started-With-ACPI"
_COMPILED = "master/extra-files/compiled/{name}.aml"


@dataclass(frozen=True)
class Ssdt:
    name: str        # local name: the file dropped in EFI/OC/ACPI and listed in config
    remote: str      # Dortania's filename for the compiled .aml
    reason: str

    def source_path(self) -> str:
        return _COMPILED.format(name=self.remote)


# AM4 B550/A520 (and AM5) declare Processor objects in a way macOS trips over;
# X570 and older AM4, and all Threadripper, do NOT need SSDT-CPUR.
_CPUR_CHIPSETS = ("b550", "a520", "a620", "b650", "x670", "b840", "b850", "x870")
_TR_CHIPSETS = ("trx40", "trx50", "wrx80", "wrx90", "x399")


def _needs_cpur(m: Machine) -> bool:
    if m.cpu.vendor is not Vendor.AMD:
        return False
    board = (m.firmware.board_name or "").lower()
    if "threadripper" in (m.cpu.brand or "").lower():
        return False
    if any(t in board for t in _TR_CHIPSETS):
        return False
    return any(c in board for c in _CPUR_CHIPSETS)


def select(m: Machine) -> list[Ssdt]:
    out: list[Ssdt] = []
    gen = m.cpu.intel_gen
    intel = m.cpu.vendor is Vendor.INTEL

    variant = "LAPTOP" if m.is_laptop else "DESKTOP"
    out.append(Ssdt("SSDT-EC-USBX", f"SSDT-EC-USBX-{variant}",
                    "fake EC + USB power properties (USBX)"))

    if _needs_cpur(m):
        out.append(Ssdt("SSDT-CPUR", "SSDT-CPUR",
                        "declare Processor objects for macOS on B550/A520 (and AM5) boards "
                        "-- X570/older AM4 and Threadripper don't need this"))

    if intel and 4 <= gen <= 10:
        out.append(Ssdt("SSDT-PLUG", "SSDT-PLUG-DRTNIA",
                        "set plugin-type on the first CPU (X86PlatformPlugin)"))

    if intel and not m.is_laptop and gen >= 9:
        out.append(Ssdt("SSDT-AWAC", "SSDT-AWAC", "force the legacy RTC over AWAC on 300-series+"))
        out.append(Ssdt("SSDT-PMC", "SSDT-PMC", "restore the native PMC device (NVRAM on Z390)"))

    if m.is_laptop and m.igpu and m.igpu.vendor is Vendor.INTEL:
        out.append(Ssdt("SSDT-PNLF", "SSDT-PNLF", "backlight control (PNLF device)"))

    return out


def needs_generation(m: Machine) -> list[str]:
    todo = []
    if m.is_laptop and m.inputs.touchpad_bus == "i2c-hid":
        todo.append("SSDT-GPIO (I2C-HID trackpad): auto-generated from the DSDT when you pass "
                    "--dsdt / --dump-dsdt (verify the trackpad after); otherwise a manual step")
    return todo
