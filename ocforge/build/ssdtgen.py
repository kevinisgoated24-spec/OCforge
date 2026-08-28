"""Drive corpnewt/SSDTTime against a machine's own ACPI tables.

SSDTTime has no command line — it is an interactive text menu. We feed it a
scripted stdin: point it at the dumped table folder, run the ops this machine
needs, quit. It compiles ``.aml`` files and writes a ``patches_OC.plist`` into
its ``Results/`` folder; we read both back and hand them to the config
assembler.

Only the non-interactive ops are automated — the ones Dortania's "Getting
Started with ACPI" walkthrough runs by just pressing a number:

    2  FakeEC     OS-aware fake EC
    4  USBX       USB power properties for SKL+ SMBIOS
    5  PluginType SSDT-PLUG (X86PlatformPlugin) — Intel only
    6  PMC        native NVRAM on 300-series boards
    7  RTCAWAC    context-aware AWAC disable / RTC fix
    0  PNLF       laptop backlight

XOSI, USB-reset (port mapping) and PCI-bridge need human choices and stay a
manual follow-up.
"""

from __future__ import annotations

import plistlib
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ocforge.model import Machine, Vendor

# extra blank lines fed after every op key: they answer SSDTTime's
# "Press [enter] to return..." pauses, and any left over land on the main
# menu where an empty selection is a harmless no-op.
_PAUSE_PAD = 4


def plan_ops(m: Machine) -> list[tuple[str, str]]:
    """The SSDTTime menu keys this machine needs, in run order."""
    intel = m.cpu.vendor is Vendor.INTEL
    gen = m.cpu.intel_gen or 0
    ops: list[tuple[str, str]] = [("2", "FakeEC"), ("4", "USBX")]
    if intel and gen >= 4:
        ops.append(("5", "PluginType"))
    if intel and not m.is_laptop and gen in (8, 9):
        ops.append(("6", "PMC"))
    if intel and gen >= 8:
        ops.append(("7", "RTCAWAC"))
    if m.is_laptop and m.igpu and m.igpu.vendor is Vendor.INTEL:
        ops.append(("0", "PNLF"))
    return ops


def build_stdin(acpi_dir: Path, ops: list[tuple[str, str]]) -> str:
    """The scripted keystrokes: select the table folder, run each op, quit."""
    lines = ["D", str(acpi_dir)]
    for key, _ in ops:
        lines.append(key)
        lines.extend([""] * _PAUSE_PAD)
    # quit, then slack in case SSDTTime re-prompts on the way out
    lines.extend(["Q", "", "Q", ""])
    return "\n".join(lines) + "\n"


@dataclass
class SsdtResult:
    aml: list[Path] = field(default_factory=list)
    acpi_add: list[dict] = field(default_factory=list)
    acpi_patch: list[dict] = field(default_factory=list)
    acpi_delete: list[dict] = field(default_factory=list)
    ran: list[str] = field(default_factory=list)
    log_text: str = ""
    error: str | None = None
    extra_todo: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.aml)


def _parse_results(results: Path, out: str, ran: list[str]) -> SsdtResult:
    aml = sorted(results.glob("*.aml")) if results.is_dir() else []
    if not aml:
        return SsdtResult(log_text=out, ran=ran, error="SSDTTime produced no .aml files")

    add: list[dict] = []
    patch: list[dict] = []
    delete: list[dict] = []
    pf = results / "patches_OC.plist"
    if pf.is_file():
        try:
            acpi = plistlib.loads(pf.read_bytes()).get("ACPI", {})
        except Exception as exc:  # noqa: BLE001 - a mangled plist shouldn't crash the build
            return SsdtResult(aml=aml, log_text=out, ran=ran,
                              error=f"could not parse patches_OC.plist: {exc}")
        add = list(acpi.get("Add", []))
        patch = list(acpi.get("Patch", []))
        delete = list(acpi.get("Delete", []))

    have = {p.name for p in aml}
    add = [a for a in add if a.get("Path") in have]
    for p in aml:  # SSDTTime always writes an Add entry, but don't rely on it
        if not any(a.get("Path") == p.name for a in add):
            add.append({"Comment": p.stem, "Enabled": True, "Path": p.name})
    return SsdtResult(aml=aml, acpi_add=add, acpi_patch=patch, acpi_delete=delete,
                      ran=ran, log_text=out)


def run(ssdttime_dir: Path, acpi_dir: Path, ops: list[tuple[str, str]], *,
        log=lambda _: None, timeout: int = 600) -> SsdtResult:
    """Run SSDTTime over ``acpi_dir`` and collect ``Results/``.

    Never raises for a SSDTTime-side failure — the error lands in
    :attr:`SsdtResult.error` so the caller can fall back to precompiled SSDTs.
    """
    ssdttime_dir = ssdttime_dir.resolve()
    script = ssdttime_dir / "SSDTTime.py"
    if not script.is_file():
        return SsdtResult(error=f"SSDTTime not found at {script}")
    results = ssdttime_dir / "Results"
    if results.exists():
        shutil.rmtree(results)

    ran = [name for _, name in ops]
    stdin = build_stdin(acpi_dir.resolve(), ops)
    log(f"SSDTTime: {', '.join(ran)} (fetches iasl on first run)")
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ssdttime_dir), input=stdin, text=True,
            capture_output=True, timeout=timeout, check=False,
        )
        out = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as exc:
        joined = (exc.stdout or "") + (exc.stderr or "")
        return SsdtResult(log_text=joined, ran=ran, error="SSDTTime timed out")
    except OSError as exc:
        return SsdtResult(ran=ran, error=f"could not launch SSDTTime: {exc}")

    return _parse_results(results, out, ran)
