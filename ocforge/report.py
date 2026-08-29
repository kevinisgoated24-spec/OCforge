"""OCforgeReporter — build a pre-filled GitHub issue for this machine.

No bot, no server, no shared credentials: this fills in the version and
hardware fields of the repo's bug-report issue form
(``.github/ISSUE_TEMPLATE/bug_report.yml``) via GitHub's URL-prefill support,
then hands the URL to the browser. The user reviews it and clicks
"Submit new issue" under their own GitHub account — the only way GitHub lets
anyone file an issue at all, bot or not.
"""

from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

from ocforge import __version__
from ocforge.model import Machine

REPO = "kevinisgoated24-spec/OCforge"
_OS_NAMES = {"win32": "Windows", "darwin": "macOS"}


def _fmt_gpu(g) -> str:
    kind = "dGPU" if g.discrete else "iGPU"
    pci = f"  [{g.pci}]" if not g.pci.empty else ""
    return f"{kind}: {g.name} ({g.vendor.value}){pci}"


def format_machine(m: Machine) -> str:
    lines = [f"chassis   {m.chassis.value}"]
    c = m.cpu
    fam = f" / {c.family}" if c.family else ""
    gen = f" (Intel gen {c.intel_gen})" if c.intel_gen else ""
    lines.append(f"cpu       {c.brand or '?'}  [{c.vendor.value}{fam}{gen}]  {c.cores}c/{c.threads}t")
    for g in m.gpus:
        lines.append(f"gpu       {_fmt_gpu(g)}")
    for n in m.net:
        tag = "wifi" if n.wireless else "eth "
        pci = f"  [{n.pci}]" if not n.pci.empty else ""
        lines.append(f"{tag}      {n.name or '?'} ({n.vendor.value}){pci}")
    lines.append(f"storage   nvme={'yes' if m.storage.has_nvme else 'no'}")
    if m.firmware.board_name:
        lines.append(f"board     {m.firmware.board_vendor} {m.firmware.board_name}".strip())
    return "\n".join(lines)


def _hardware_text(spec_path: str | None) -> str:
    """The spec at ``spec_path`` if given, else a fresh probe. Never raises —
    falls back to a placeholder so a report can still be filed without it."""
    try:
        if spec_path and Path(spec_path).is_file():
            from ocforge.spec import load

            return format_machine(load(spec_path))
        from ocforge.probe import probe

        return format_machine(probe())
    except Exception as exc:  # noqa: BLE001 - best-effort, never blocks a report
        return f"(couldn't collect automatically: {exc}\npaste your spec.json or `ocforge probe` output here)"


def build_url(*, spec_path: str | None = None, title: str = "") -> str:
    fields = {
        "template": "bug_report.yml",
        "title": title or "[Bug]: ",
        "labels": "bug",
        "ocforge-version": __version__,
        "os": _OS_NAMES.get(sys.platform, "Linux"),
        "hardware": _hardware_text(spec_path),
    }
    return f"https://github.com/{REPO}/issues/new?{urllib.parse.urlencode(fields)}"
