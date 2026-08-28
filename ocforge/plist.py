"""config.plist <-> JSON for the GUI editor.

plist has types JSON doesn't (``bytes``, ``datetime``); those round-trip
through single-key sentinel objects so a Flutter tree editor can render them:

    b"\\x01\\x00"          <->  {"__data__": "0100"}      (hex)
    datetime(2020, 1, 1)  <->  {"__date__": "2020-01-01T00:00:00"}

Key order is preserved (``sort_keys=False``) so a saved config stays diff-able.
"""

from __future__ import annotations

import datetime as _dt
import json
import plistlib
from pathlib import Path
from typing import Any

_DATA = "__data__"
_DATE = "__date__"


def _default(obj: Any) -> Any:
    if isinstance(obj, (bytes, bytearray)):
        return {_DATA: bytes(obj).hex()}
    if isinstance(obj, _dt.datetime):
        return {_DATE: obj.isoformat()}
    raise TypeError(f"not plist-serialisable: {type(obj).__name__}")


def _object_hook(d: dict[str, Any]) -> Any:
    if len(d) == 1:
        if _DATA in d:
            return bytes.fromhex(d[_DATA] or "")
        if _DATE in d:
            return _dt.datetime.fromisoformat(d[_DATE])
    return d


def to_json(path: str | Path) -> str:
    with open(path, "rb") as fh:
        data = plistlib.load(fh, dict_type=dict)
    return json.dumps(data, indent=2, default=_default, ensure_ascii=False)


def from_json(text: str, path: str | Path) -> None:
    data = json.loads(text, object_hook=_object_hook)
    with open(path, "wb") as fh:
        plistlib.dump(data, fh, fmt=plistlib.FMT_XML, sort_keys=False)
