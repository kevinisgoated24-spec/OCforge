"""OCforgeReporter — Discord HTTP Interactions endpoint.

A `/fileissue` slash command that opens a modal (version, OS, hardware) and
hands back a pre-filled GitHub "New issue" link — same fields, same issue
form (`.github/ISSUE_TEMPLATE/bug_report.yml`), same `ocforge report` / GUI
bug-button logic, just reached from Discord.

This used to be a Gateway bot (a process holding a persistent websocket to
Discord, `discord.py`'s ``Client.run()``). It's now a plain HTTP endpoint:
Discord POSTs each interaction (the slash command, then the modal submit)
straight to whatever URL is set as this application's "Interactions Endpoint
URL" in the Developer Portal, and this handles it like any other web
request. No process has to stay connected to anything.

Matches their trust model exactly: this still holds **no GitHub credential**
and never talks to the GitHub API — it just builds a URL and hands it back.
It's actually a step better than the Gateway version: ``DISCORD_TOKEN`` (the
one secret that can control the bot) is no longer read by this running
service at all — it's only ever used by ``register_commands.py``, by hand,
when the command needs (re)registering. What this process holds is
``DISCORD_PUBLIC_KEY``, which isn't a secret: it's published on the
application's own Developer Portal page and exists only to verify that a
request genuinely came from Discord (anyone can already see it).
"""

from __future__ import annotations

import os
import threading
import time
import urllib.parse

from flask import Flask, abort, jsonify, request
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

# --- configuration (env vars; see README.md) --------------------------------

PUBLIC_KEY = os.environ["DISCORD_PUBLIC_KEY"]
GITHUB_REPO = os.environ.get("GITHUB_REPO", "kevinisgoated24-spec/OCforge")

_guild_env = os.environ.get("DISCORD_GUILD_ID")
ALLOWED_GUILD_ID = _guild_env if _guild_env else None

COMMAND_NAME = "fileissue"
MODAL_CUSTOM_ID = "fileissue_modal"
PER_USER_COOLDOWN_SECONDS = 30
FIELD_MAX_LEN = 1500  # each modal field is truncated before going in the URL

# Discord interaction types (the subset this endpoint handles).
_TYPE_PING = 1
_TYPE_APPLICATION_COMMAND = 2
_TYPE_MODAL_SUBMIT = 5

# Response types this endpoint sends back.
_RESP_PONG = 1
_RESP_CHANNEL_MESSAGE = 4
_RESP_MODAL = 9

_EPHEMERAL = 1 << 6

app = Flask(__name__)
_verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
_cooldown_lock = threading.Lock()
_last_call: dict[str, float] = {}  # user id -> monotonic time of last /fileissue


def verify_signature(signature: str, timestamp: str, body: bytes) -> bool:
    """True if ``body`` really came from Discord, per the Ed25519 scheme
    Discord's own docs describe: sign ``timestamp + body`` with the
    application's public key."""
    try:
        _verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False


def _truncate(s: str) -> str:
    s = s.strip()
    if len(s) <= FIELD_MAX_LEN:
        return s
    return s[:FIELD_MAX_LEN] + f"\n\n…(truncated at {FIELD_MAX_LEN} chars)"


def build_issue_url(*, ocforge_version: str, os_name: str, hardware: str) -> str:
    fields = {
        "template": "bug_report.yml",
        "title": "[Bug]: ",
        "labels": "bug",
        "ocforge-version": _truncate(ocforge_version),
        "os": _truncate(os_name),
        "interface": "Discord",
        "hardware": _truncate(hardware),
    }
    return f"https://github.com/{GITHUB_REPO}/issues/new?{urllib.parse.urlencode(fields)}"


def modal_response() -> dict:
    def row(custom_id: str, label: str, *, style: int, max_length: int, placeholder: str = "") -> dict:
        field: dict = {
            "type": 4,
            "custom_id": custom_id,
            "label": label,
            "style": style,
            "max_length": max_length,
            "required": True,
        }
        if placeholder:
            field["placeholder"] = placeholder
        return {"type": 1, "components": [field]}

    return {
        "type": _RESP_MODAL,
        "data": {
            "custom_id": MODAL_CUSTOM_ID,
            "title": "OCforgeReporter: file a bug",
            "components": [
                row("ocforge_version", "ocforge version (ocforge --version)",
                    style=1, max_length=40, placeholder="e.g. 0.4.16"),
                row("os_field", "OS", style=1, max_length=40,
                    placeholder="Windows / macOS / Linux"),
                row("hardware", "Hardware (paste `ocforge probe` output)",
                    style=2, max_length=FIELD_MAX_LEN),
            ],
        },
    }


def extract_modal_values(data: dict) -> dict[str, str]:
    """Flatten a MODAL_SUBMIT payload's ``components`` (a list of action
    rows, each holding one text-input component) into {custom_id: value}."""
    out: dict[str, str] = {}
    for row in data.get("components", []):
        for field in row.get("components", []):
            cid = field.get("custom_id")
            if cid:
                out[cid] = field.get("value", "")
    return out


def _ephemeral_message(content: str, *, components: list | None = None) -> dict:
    msg: dict = {"flags": _EPHEMERAL, "content": content}
    if components:
        msg["components"] = components
    return {"type": _RESP_CHANNEL_MESSAGE, "data": msg}


def _check_cooldown(user_id: str) -> float:
    """Returns 0 if the call is allowed (and records it), else the number of
    seconds left to wait."""
    now = time.monotonic()
    with _cooldown_lock:
        last = _last_call.get(user_id)
        if last is not None and now - last < PER_USER_COOLDOWN_SECONDS:
            return PER_USER_COOLDOWN_SECONDS - (now - last)
        _last_call[user_id] = now
        return 0


def handle_command(payload: dict) -> dict:
    guild_id = payload.get("guild_id")
    if ALLOWED_GUILD_ID and guild_id != ALLOWED_GUILD_ID:
        return _ephemeral_message("OCforgeReporter isn't enabled in this server.")

    user_id = (payload.get("member", {}).get("user") or payload.get("user") or {}).get("id", "")
    wait = _check_cooldown(user_id) if user_id else 0
    if wait:
        return _ephemeral_message(f"Try again in {wait:.0f}s.")

    return modal_response()


def handle_modal_submit(payload: dict) -> dict:
    data = payload.get("data", {})
    if data.get("custom_id") != MODAL_CUSTOM_ID:
        abort(400, "unknown modal")

    values = extract_modal_values(data)
    url = build_issue_url(
        ocforge_version=values.get("ocforge_version", ""),
        os_name=values.get("os_field", ""),
        hardware=values.get("hardware", ""),
    )
    return _ephemeral_message(
        "Your version/OS/hardware are filled in — add what happened and "
        "hit **Submit new issue** yourself on GitHub:",
        components=[{
            "type": 1,
            "components": [{"type": 2, "style": 5, "label": "Open on GitHub", "url": url}],
        }],
    )


@app.route("/interactions", methods=["POST"])
def interactions():
    signature = request.headers.get("X-Signature-Ed25519", "")
    timestamp = request.headers.get("X-Signature-Timestamp", "")
    body = request.get_data()  # raw bytes, exactly as Discord signed it

    if not signature or not timestamp or not verify_signature(signature, timestamp, body):
        abort(401, "invalid request signature")

    payload = request.get_json(silent=True) or {}
    itype = payload.get("type")

    if itype == _TYPE_PING:
        return jsonify({"type": _RESP_PONG})
    if itype == _TYPE_APPLICATION_COMMAND:
        if payload.get("data", {}).get("name") != COMMAND_NAME:
            abort(400, "unknown command")
        return jsonify(handle_command(payload))
    if itype == _TYPE_MODAL_SUBMIT:
        return jsonify(handle_modal_submit(payload))

    abort(400, f"unhandled interaction type {itype}")


@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200


if __name__ == "__main__":
    # Dev convenience only — see README.md for running this under waitress.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8787")))
