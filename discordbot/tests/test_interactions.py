"""Tests for the stateless HTTP interactions endpoint. No network, no real
Discord app needed: a throwaway Ed25519 keypair stands in for Discord's, and
Flask's test client drives the route exactly as a real request would.

Run from discordbot/: pip install -r requirements.txt -r requirements-dev.txt
then pytest.
"""

from __future__ import annotations

import json
import os

import pytest
from nacl.signing import SigningKey

# A throwaway keypair, not Discord's — set DISCORD_PUBLIC_KEY before the
# module under test reads it at import time.
_SIGNING_KEY = SigningKey.generate()
os.environ.setdefault("DISCORD_PUBLIC_KEY", _SIGNING_KEY.verify_key.encode().hex())
os.environ.setdefault("GITHUB_REPO", "kevinisgoated24-spec/OCforge")

import interactions as itx  # must follow the env setup above


def _sign(body: bytes, timestamp: str = "1700000000") -> dict[str, str]:
    sig = _SIGNING_KEY.sign(timestamp.encode() + body).signature
    return {"X-Signature-Ed25519": sig.hex(), "X-Signature-Timestamp": timestamp}


@pytest.fixture
def client():
    itx.app.config["TESTING"] = True
    itx._last_call.clear()
    return itx.app.test_client()


# --- signature verification --------------------------------------------------

def test_verify_signature_accepts_genuine_request():
    body = b'{"type":1}'
    headers = _sign(body)
    assert itx.verify_signature(headers["X-Signature-Ed25519"], headers["X-Signature-Timestamp"], body)


def test_verify_signature_rejects_tampered_body():
    body = b'{"type":1}'
    headers = _sign(body)
    assert not itx.verify_signature(
        headers["X-Signature-Ed25519"], headers["X-Signature-Timestamp"], b'{"type":2}'
    )


def test_verify_signature_rejects_garbage():
    assert not itx.verify_signature("not-hex", "1700000000", b"{}")
    assert not itx.verify_signature("", "", b"{}")


def test_route_rejects_unsigned_request(client):
    resp = client.post("/interactions", data=b'{"type":1}', content_type="application/json")
    assert resp.status_code == 401


def test_route_rejects_wrong_signature(client):
    body = b'{"type":1}'
    headers = _sign(body)
    headers["X-Signature-Timestamp"] = "1800000000"  # doesn't match what was signed
    resp = client.post("/interactions", data=body, headers=headers, content_type="application/json")
    assert resp.status_code == 401


# --- PING ---------------------------------------------------------------------

def test_ping_gets_pong(client):
    body = json.dumps({"type": 1}).encode()
    resp = client.post("/interactions", data=body, headers=_sign(body), content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json() == {"type": 1}


# --- /fileissue -> modal -------------------------------------------------------

def test_fileissue_command_opens_modal(client):
    payload = {
        "type": 2,
        "guild_id": "999",
        "member": {"user": {"id": "42"}},
        "data": {"name": "fileissue"},
    }
    body = json.dumps(payload).encode()
    resp = client.post("/interactions", data=body, headers=_sign(body), content_type="application/json")
    out = resp.get_json()
    assert out["type"] == 9  # MODAL
    assert out["data"]["custom_id"] == "fileissue_modal"
    field_ids = [c["components"][0]["custom_id"] for c in out["data"]["components"]]
    assert field_ids == ["ocforge_version", "os_field", "hardware"]


def test_unknown_command_name_rejected(client):
    payload = {"type": 2, "member": {"user": {"id": "42"}}, "data": {"name": "notfileissue"}}
    body = json.dumps(payload).encode()
    resp = client.post("/interactions", data=body, headers=_sign(body), content_type="application/json")
    assert resp.status_code == 400


def test_cooldown_blocks_rapid_repeat(client):
    def invoke():
        payload = {"type": 2, "member": {"user": {"id": "42"}}, "data": {"name": "fileissue"}}
        body = json.dumps(payload).encode()
        return client.post("/interactions", data=body, headers=_sign(body), content_type="application/json").get_json()

    first = invoke()
    assert first["type"] == 9
    second = invoke()
    assert second["type"] == 4
    assert "Try again in" in second["data"]["content"]


def test_guild_restriction(client, monkeypatch):
    monkeypatch.setattr(itx, "ALLOWED_GUILD_ID", "999")
    payload = {"type": 2, "guild_id": "111", "member": {"user": {"id": "7"}}, "data": {"name": "fileissue"}}
    body = json.dumps(payload).encode()
    resp = client.post("/interactions", data=body, headers=_sign(body), content_type="application/json")
    out = resp.get_json()
    assert out["type"] == 4
    assert "isn't enabled in this server" in out["data"]["content"]


# --- modal submit -> GitHub link ----------------------------------------------

def _modal_submit_payload(**values: str) -> dict:
    return {
        "type": 5,
        "data": {
            "custom_id": "fileissue_modal",
            "components": [
                {"type": 1, "components": [{"custom_id": k, "value": v}]}
                for k, v in values.items()
            ],
        },
    }


def test_modal_submit_builds_github_link(client):
    payload = _modal_submit_payload(
        ocforge_version="1.3.0", os_field="macOS 15", hardware="Mac mini, i7-8700B"
    )
    body = json.dumps(payload).encode()
    resp = client.post("/interactions", data=body, headers=_sign(body), content_type="application/json")
    out = resp.get_json()
    assert out["type"] == 4
    assert out["data"]["flags"] == itx._EPHEMERAL
    button = out["data"]["components"][0]["components"][0]
    assert button["style"] == 5  # link button
    url = button["url"]
    assert url.startswith("https://github.com/kevinisgoated24-spec/OCforge/issues/new?")
    assert "ocforge-version=1.3.0" in url
    assert "os=macOS" in url
    assert "interface=Discord" in url


def test_modal_submit_rejects_unknown_custom_id(client):
    payload = {"type": 5, "data": {"custom_id": "someone-elses-modal", "components": []}}
    body = json.dumps(payload).encode()
    resp = client.post("/interactions", data=body, headers=_sign(body), content_type="application/json")
    assert resp.status_code == 400


def test_build_issue_url_truncates_long_fields():
    long_hw = "x" * 5000
    url = itx.build_issue_url(ocforge_version="1.0", os_name="Linux", hardware=long_hw)
    assert "truncated" in urllib_unquote(url)


def urllib_unquote(url: str) -> str:
    import urllib.parse
    return urllib.parse.unquote(url)


def test_extract_modal_values_flattens_rows():
    data = {
        "components": [
            {"type": 1, "components": [{"custom_id": "a", "value": "1"}]},
            {"type": 1, "components": [{"custom_id": "b", "value": "2"}]},
        ]
    }
    assert itx.extract_modal_values(data) == {"a": "1", "b": "2"}


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
