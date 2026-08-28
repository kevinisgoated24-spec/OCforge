"""Host hardware probing.

``probe()`` dispatches on the running OS. Each backend returns a fully
populated :class:`ocforge.model.Machine`; callers never branch on platform.
"""

from __future__ import annotations

import sys

from ocforge.model import Machine


def probe() -> Machine:
    from ocforge.probe.base import backfill_intel_gen

    if sys.platform.startswith("linux"):
        from ocforge.probe import linux

        m = linux.probe()
    elif sys.platform == "win32":
        from ocforge.probe import windows

        m = windows.probe()
    elif sys.platform == "darwin":
        from ocforge.probe import darwin

        m = darwin.probe()
    else:
        raise RuntimeError(f"unsupported host platform: {sys.platform!r}")

    backfill_intel_gen(m)  # recover Intel gen from the iGPU when the brand didn't parse
    return m


__all__ = ["probe"]
