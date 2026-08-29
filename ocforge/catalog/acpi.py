"""Which pre-built SSDTs the config needs.

This mirrors Dortania's "Prebuilt SSDTs" matrix
(``Getting-Started-With-ACPI/ssdt-methods/ssdt-prebuilt.html``): pick the row
for the machine's CPU family / chassis and take the listed tables. Every SSDT
here is a *hotpatch* (``External`` refs + ``_STA`` conditionals) served from
Dortania's precompiled set. SSDT-XOSI additionally carries the ``_OSI -> XOSI``
rename it depends on.

DSDT-derived tables (per-board I2C-HID trackpad GPIO pinning) are handled
separately by :mod:`ocforge.build.gpio`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ocforge.model import Machine, Vendor

DORTANIA_ACPI = "dortania/Getting-Started-With-ACPI"
_COMPILED = "master/extra-files/compiled/{name}.aml"


@dataclass(frozen=True)
class AcpiPatch:
    """An OpenCore ACPI byte patch (used by SSDT-XOSI's ``_OSI`` rename)."""

    comment: str
    find: bytes
    replace: bytes
    count: int = 0

    def as_oc(self) -> dict:
        return {
            "Comment": self.comment, "Enabled": True,
            "Find": self.find, "Replace": self.replace,
            "Count": self.count, "Limit": 0,
            "Mask": b"", "ReplaceMask": b"",
            "OemTableId": b"", "TableLength": 0, "TableSignature": b"",
            "Base": "", "BaseSkip": 0, "Skip": 0,
        }


@dataclass(frozen=True)
class Ssdt:
    name: str                       # file dropped in EFI/OC/ACPI and listed in config
    remote: str                     # Dortania's filename for the compiled .aml
    reason: str
    patch: AcpiPatch | None = None  # ACPI rename this SSDT needs (SSDT-XOSI)

    def source_path(self) -> str:
        return _COMPILED.format(name=self.remote)


_XOSI_PATCH = AcpiPatch("_OSI to XOSI rename (pairs with SSDT-XOSI)", b"_OSI", b"XOSI")

# AM4 B550/A520 (and AM5) declare Processor objects macOS trips over; X570 and
# older AM4, and all Threadripper, do NOT need SSDT-CPUR.
_CPUR_CHIPSETS = ("b550", "a520", "a620", "b650", "x670", "b840", "b850", "x870")
_TR_CHIPSETS = ("trx40", "trx50", "wrx80", "wrx90", "x399")

# SSDT-IMEI: a CPU/PCH generation mismatch (Sandy Bridge on a 7-series PCH, or
# Ivy Bridge on a 6-series PCH). Desktop + mobile chipset names.
_PCH_7SERIES = ("b75", "q75", "z75", "h77", "q77", "z77",                   # desktop
                "hm70", "hm75", "hm76", "hm77", "qm77", "um77", "qs77")     # mobile
_PCH_6SERIES = ("h61", "b65", "q65", "p67", "h67", "q67", "z68",            # desktop
                "hm65", "hm67", "qm67", "um67", "qs67")                     # mobile
_ASUS_400SERIES = ("b460", "h410", "h470", "z490", "w480")

_ICE_LAKE = re.compile(r"\bi[3-9][- ]?10\d{2}g[1-9]\b", re.IGNORECASE)


def _board(m: Machine) -> str:
    return (m.firmware.board_name or "").lower()


def _has(hay: str, needles: tuple[str, ...]) -> bool:
    return any(n in hay for n in needles)


def _needs_cpur(m: Machine) -> bool:
    if m.cpu.vendor is not Vendor.AMD:
        return False
    if "threadripper" in (m.cpu.brand or "").lower():
        return False
    board = _board(m)
    if _has(board, _TR_CHIPSETS):
        return False
    return _has(board, _CPUR_CHIPSETS)


def hedt_family(m: Machine) -> str | None:
    """``snb-e`` / ``hsw-e`` / ``skl-x`` for Intel HEDT (X79 / X99 / X299), else None."""
    if m.cpu.vendor is not Vendor.INTEL:
        return None
    board = _board(m)
    brand = (m.cpu.brand or "").lower()
    if _has(board, ("x299", "c422")) or "cascade lake" in brand or re.search(r"xeon w-2\d{3}", brand):
        return "skl-x"
    if "x99" in board or re.search(r"i7-59\d{2}x", brand) or re.search(r"i7-68\d{2}k", brand):
        return "hsw-e"
    if "x79" in board:
        return "snb-e"
    if re.search(r"\bi[79]-\d{3,4}xe?\b", brand):        # generic -X / -XE HEDT part
        return "skl-x" if (m.cpu.cores or 0) >= 10 else "hsw-e"
    return None


def select(m: Machine) -> list[Ssdt]:
    out: list[Ssdt] = []
    gen = m.cpu.intel_gen or 0
    intel = m.cpu.vendor is Vendor.INTEL
    amd = m.cpu.vendor is Vendor.AMD
    lap = m.is_laptop
    board = _board(m)
    variant = "LAPTOP" if lap else "DESKTOP"
    hedt = hedt_family(m)

    # --- Embedded controller: -USBX combined table on Skylake+, AMD and the
    #     newer HEDT rows; plain SSDT-EC on older Intel.
    if amd or hedt in ("hsw-e", "skl-x") or (intel and gen >= 6):
        out.append(Ssdt("SSDT-EC-USBX", f"SSDT-EC-USBX-{variant}",
                        "fake EC + USB power properties (USBX)"))
    else:
        out.append(Ssdt("SSDT-EC", f"SSDT-EC-{variant}", "fake EC"))

    if _needs_cpur(m):
        out.append(Ssdt("SSDT-CPUR", "SSDT-CPUR",
                        "declare Processor objects for macOS on B550/A520 (and AM5) boards "
                        "-- X570/older AM4 and Threadripper don't need this"))

    # --- SSDT-PLUG: Haswell..Comet Lake, plus Haswell-E / Skylake-X
    if (intel and 4 <= gen <= 10) or hedt in ("hsw-e", "skl-x"):
        out.append(Ssdt("SSDT-PLUG", "SSDT-PLUG-DRTNIA",
                        "enable XCPM (set plugin-type on the first CPU)"))

    # --- SSDT-IMEI: Sandy Bridge + 7-series PCH, or Ivy Bridge + 6-series PCH
    if intel and ((gen == 2 and _has(board, _PCH_7SERIES))
                  or (gen == 3 and _has(board, _PCH_6SERIES))):
        out.append(Ssdt("SSDT-IMEI", "SSDT-IMEI",
                        "inject the IMEI device missing from this board's ACPI"))

    # --- SSDT-AWAC: Coffee Lake and newer (desktop + laptop)
    if intel and gen >= 8:
        out.append(Ssdt("SSDT-AWAC", "SSDT-AWAC",
                        "force the legacy RTC over the unsupported AWAC clock"))

    # --- SSDT-PMC: "true" 300-series (desktop gen 8-9, laptop gen 9; not Z370)
    if intel and "z370" not in board and (
            (not lap and gen in (8, 9)) or (lap and gen == 9)):
        out.append(Ssdt("SSDT-PMC", "SSDT-PMC",
                        "native NVRAM on true 300-series boards (Z370 excluded)"))

    # --- SSDT-RHUB: Asus 400-series desktops, or Ice Lake laptops
    if intel and not lap and gen == 10 \
            and "asus" in (m.firmware.board_vendor or "").lower() \
            and _has(board, _ASUS_400SERIES):
        out.append(Ssdt("SSDT-RHUB", "SSDT-RHUB",
                        "reset USB controllers (Asus 400-series ACPI quirk)"))
    elif intel and lap and _ICE_LAKE.search(m.cpu.brand or ""):
        out.append(Ssdt("SSDT-RHUB", "SSDT-RHUB",
                        "reset USB controllers (Ice Lake laptop ACPI quirk)"))

    # --- SSDT-PNLF: every Intel laptop
    if lap and (m.igpu is None or m.igpu.vendor is Vendor.INTEL):
        out.append(Ssdt("SSDT-PNLF", "SSDT-PNLF", "internal-display backlight control"))

    # --- SSDT-XOSI (+ the _OSI rename it needs): every Intel laptop
    if lap and intel:
        out.append(Ssdt("SSDT-XOSI", "SSDT-XOSI",
                        "spoof _OSI to a Windows build so laptop ACPI paths light up",
                        patch=_XOSI_PATCH))

    # --- HEDT extras
    if hedt in ("snb-e", "hsw-e"):
        out.append(Ssdt("SSDT-UNC", "SSDT-UNC",
                        "disable dead uncore bridges (else IOPCIFamily panic on Big Sur+)"))
    if hedt in ("hsw-e", "skl-x"):
        out.append(Ssdt("SSDT-RTC0-RANGE-HEDT", "SSDT-RTC0-RANGE-HEDT",
                        "legacy RTC range fix for HEDT (also fixes early-boot halts)"))

    return out


def patches(m: Machine) -> list[dict]:
    """OC ACPI ``Patch`` entries the selected SSDTs require (currently XOSI)."""
    return [s.patch.as_oc() for s in select(m) if s.patch]


def needs_generation(m: Machine) -> list[str]:
    todo = []
    if m.cpu.vendor is Vendor.INTEL and 0 < m.cpu.intel_gen < 4:
        todo.append("SSDT-PM (CPU power management, Sandy/Ivy Bridge): the stock ACPI PM "
                    "tables are already dropped (ACPI -> Delete) but the replacement needs "
                    "Pike's ssdtPRGen.sh -- not automated here, see the Dortania guide's "
                    "Post-Install page")
    if m.is_laptop and m.inputs.touchpad_bus == "i2c-hid":
        todo.append("SSDT-GPIO (I2C-HID trackpad): auto-generated on a Linux or Windows host "
                    "(no flag needed -- verify the trackpad after); on macOS, or if the DSDT "
                    "scan finds no single clear candidate, pass --dsdt yourself instead")
    if hedt_family(m):
        todo.append(f"HEDT ({hedt_family(m)}): SSDTs are selected but HEDT SMBIOS/quirks "
                    "aren't fully modelled -- cross-check against the Dortania HEDT guide")
    return todo
