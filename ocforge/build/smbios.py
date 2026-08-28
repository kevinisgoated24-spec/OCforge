"""SMBIOS identity for the PlatformInfo section.

Serial + MLB come from ``macserial`` (shipped in the OpenCore release zip);
UUID and ROM are generated locally. ``generate()`` takes the path to a
macserial binary so the caller controls where it comes from.
"""

from __future__ import annotations

import re
import secrets
import subprocess
import uuid
from dataclasses import dataclass

# Apple OUIs — the first 3 bytes of a genuine Mac's primary NIC MAC, reused for ROM.
_APPLE_OUIS = ("001451", "0017f2", "3c0754", "8863df", "a4d18c", "f0dbe2")


@dataclass(frozen=True)
class SmbiosData:
    model: str
    serial: str
    mlb: str
    uuid: str
    rom: bytes  # 6 bytes

    @property
    def rom_hex(self) -> str:
        return self.rom.hex()


def _random_uuid() -> str:
    return str(uuid.uuid4()).upper()


def _random_rom() -> bytes:
    return bytes.fromhex(secrets.choice(_APPLE_OUIS)) + secrets.token_bytes(3)


_MACSERIAL_LINE = re.compile(r"^([A-Z0-9]{10,12})\s*\|\s*([A-Z0-9]{13,17})\s*$")


def _run_macserial(binary: str, model: str) -> tuple[str, str]:
    out = subprocess.run(
        [binary, "--model", model, "--num", "1"],
        capture_output=True, text=True, timeout=20, check=True,
    ).stdout
    for line in out.splitlines():
        if m := _MACSERIAL_LINE.match(line.strip()):
            return m.group(1), m.group(2)
    raise RuntimeError(f"macserial produced no usable serial for {model}:\n{out}")


def generate(model: str, macserial: str | None) -> SmbiosData:
    if macserial:
        serial, mlb = _run_macserial(macserial, model)
    else:  # plan / offline: structurally valid placeholders, clearly not real
        serial, mlb = "C02OCFORGE01", "C02OCFORGE01FORGE1"
    return SmbiosData(
        model=model,
        serial=serial,
        mlb=mlb,
        uuid=_random_uuid(),
        rom=_random_rom(),
    )
