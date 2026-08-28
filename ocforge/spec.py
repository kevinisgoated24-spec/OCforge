"""Serialize a Machine to/from JSON so a build can be planned off-target.

``ocforge probe --save machine.json`` on the real box, then
``ocforge plan --spec machine.json`` anywhere.
"""

from __future__ import annotations

import json
import types
import typing
from dataclasses import asdict, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, get_args, get_origin

from ocforge import model
from ocforge.model import Machine

_HINTS: dict[type, dict[str, Any]] = {}


def _hints(cls: type) -> dict[str, Any]:
    if cls not in _HINTS:
        _HINTS[cls] = typing.get_type_hints(cls, vars(model))
    return _HINTS[cls]


def to_json(machine: Machine) -> str:
    def enc(o: Any) -> Any:
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, (set, frozenset)):
            return sorted(o)
        raise TypeError(type(o))

    data = asdict(machine)
    data.pop("source", None)  # runtime provenance, not part of the machine
    return json.dumps(data, indent=2, default=enc)


def _build(tp: Any, data: Any) -> Any:
    if data is None:
        return None
    origin = get_origin(tp)
    if origin in (list, tuple):
        args = get_args(tp) or (Any,)
        return [_build(args[0], x) for x in data]
    if origin is typing.Union or origin is types.UnionType:  # Optional[X] / X | None
        inner = next((a for a in get_args(tp) if a is not type(None)), Any)
        return _build(inner, data)
    if is_dataclass(tp):
        h = _hints(tp)
        return tp(**{f.name: _build(h[f.name], data[f.name]) for f in fields(tp) if f.name in data})
    if isinstance(tp, type) and issubclass(tp, Enum):
        return tp(data)
    if tp in (frozenset, set) or origin in (frozenset, set):
        return frozenset(data)
    return data


def from_json(text: str) -> Machine:
    m = _build(Machine, json.loads(text))
    m.source = "spec"
    return m


def load(path: str | Path) -> Machine:
    return from_json(Path(path).read_text())


def save(machine: Machine, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(to_json(machine))
