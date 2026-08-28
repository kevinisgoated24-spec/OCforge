"""Host hardware probing.

``probe()`` dispatches on the running OS. Each backend returns a fully
populated :class:`ocforge.model.Machine`; callers never branch on platform.
"""

from __future__ import annotations

import sys

from ocforge.model import Machine


def probe() -> Machine:
    if sys.platform.startswith("linux"):
        from ocforge.probe import linux

        return linux.probe()
    if sys.platform == "win32":
        from ocforge.probe import windows

        return windows.probe()
    if sys.platform == "darwin":
        from ocforge.probe import darwin

        return darwin.probe()
    raise RuntimeError(f"unsupported host platform: {sys.platform!r}")


__all__ = ["probe"]
