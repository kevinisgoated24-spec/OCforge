"""A firmware-settings checklist for the target machine.

Distilled from Dortania's per-platform "BIOS settings" pages, then narrowed by
vendor / CPU / chassis. Returns plain lines grouped ENABLE / DISABLE / notes —
``ocforge bios`` prints them and they ride along in ``ocforge plan``.
"""

from __future__ import annotations

from ocforge.model import Machine, Vendor

_OEMS = ("dell", "hp", "hewlett", "lenovo", "asus", "asustek", "gigabyte", "msi", "asrock")


def _oem(m: Machine) -> str:
    v = (m.firmware.board_vendor or "").lower()
    for name in _OEMS:
        if name in v:
            return "hp" if name == "hewlett" else ("asus" if name == "asustek" else name)
    return ""


def checklist(m: Machine) -> list[str]:
    intel = m.cpu.vendor is Vendor.INTEL
    lap = m.is_laptop
    oem = _oem(m)
    out: list[str] = []

    out.append("ENABLE")
    out.append("  UEFI boot mode (no Legacy/CSM)")
    out.append("  SATA / storage mode = AHCI   (NOT RAID / Intel RST / Optane)")
    out.append("  XHCI Hand-off")
    if not lap:
        out.append("  Above 4G Decoding / '>4GB MMIO'   (if present)")
        out.append("  Re-Size BAR / Resizable BAR       (only if you also set "
                   "ResizeAppleGpuBars=0; otherwise leave OFF)")
    if lap:
        out.append("  Hyper-Threading, VT-x")
        out.append("  DVMT Pre-Allocated = 64MB or higher   (if the option exists)")

    out.append("DISABLE")
    out.append("  Secure Boot   (clear/erase the keys if it won't switch off)")
    out.append("  CSM / Legacy OpROM / Legacy Boot")
    out.append("  Fast Boot / Ultra Fast Boot")
    out.append("  Serial (COM) / Parallel (LPT) port, if present")
    out.append("  fTPM / PTT / firmware TPM")
    if intel:
        out.append("  Intel SGX")
        out.append("  CFG Lock / 'Overclock Lock' / MSR 0xE2   (if exposed - "
                   "otherwise ocforge sets AppleXcpmCfgLock)")
        out.append("  VT-d   (or leave ON - ocforge sets DisableIoMapper)")
    if lap:
        out.append("  Discrete GPU / 'Switchable Graphics' if it's an unsupported dGPU")

    if oem == "dell":
        out.append("Dell notes")
        out.append("  CFG-Lock and Above-4G are usually NOT in the menu - fine, ocforge handles CFG-Lock")
        out.append("  Switching RAID -> AHCI makes an installed Windows unbootable until you switch back")
        out.append("  Turn off: UEFI Network Stack, Thunderbolt Boot Support, SupportAssist OS Recovery")
    elif oem == "hp":
        out.append("HP notes")
        out.append("  Disable 'Sure Start' / 'Boot Guard' if possible; some HP boards reject OpenCore outright")
        out.append("  Set an admin BIOS password to unlock the advanced menus")
    elif oem == "lenovo":
        out.append("Lenovo notes")
        out.append("  Disable 'OS Optimized Defaults'; clear Secure Boot keys")
    elif intel and oem in ("asus", "gigabyte", "msi", "asrock"):
        out.append(f"{oem.upper()} notes")
        out.append("  CFG Lock is usually hidden - unlock it (Dortania 'Fixing CFG Lock') "
                   "or rely on AppleXcpmCfgLock")

    return out
