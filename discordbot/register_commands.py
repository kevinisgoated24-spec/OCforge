"""One-time (or re-run-whenever-the-command-changes) registration of
OCforgeReporter's `/fileissue` slash command with Discord.

This is the *only* thing in this project that still needs ``DISCORD_TOKEN``,
and only for the few seconds this script runs — the live
``interactions.py`` endpoint never reads that token at all. Run it by hand
after setup, and again any time ``COMMAND_NAME``/its description changes.

Registers as a guild command (shows up in that server within seconds) when
``DISCORD_GUILD_ID`` is set, otherwise as a global command (every server the
app is in, but can take up to ~an hour to propagate the first time).

stdlib-only on purpose — this script's trust footprint (it's the one place
holding the real token) shouldn't depend on pulling in a third-party HTTP
library.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://discord.com/api/v10"

COMMAND = {
    "name": "fileissue",
    "description": "Get a pre-filled GitHub bug-report link for OCforge",
    "type": 1,  # CHAT_INPUT
}


def _env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"error: {name} is not set (see discordbot/.env.example)", file=sys.stderr)
        sys.exit(1)
    return val


def main() -> int:
    token = _env("DISCORD_TOKEN")
    app_id = _env("DISCORD_APPLICATION_ID")
    guild_id = os.environ.get("DISCORD_GUILD_ID")

    if guild_id:
        url = f"{API}/applications/{app_id}/guilds/{guild_id}/commands"
        scope = f"guild {guild_id}"
    else:
        url = f"{API}/applications/{app_id}/commands"
        scope = "global (every server this app is in — allow up to ~1h to propagate)"

    body = json.dumps([COMMAND]).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="PUT",  # PUT replaces the whole command set with exactly this list
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        print(f"error: Discord returned {exc.code}: {detail}", file=sys.stderr)
        return 1

    print(f"registered /fileissue as a {scope} command.")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
