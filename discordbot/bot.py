"""OCforgeReporter — Discord bot.

A `/report` slash command that opens a modal and files a GitHub issue on
kevinisgoated24-spec/OCforge directly, using a token *this bot* holds.

That's a real change from the CLI/`ocforge report`/GUI version of
OCforgeReporter: those never touch a credential — they just build a
prefilled github.com/.../issues/new URL and the reporter submits it under
their own GitHub account. This bot instead files the issue itself, so the
token it holds is the thing standing between "anybody in the Discord server"
and the repo's issue tracker. Two things keep that narrow:

  * The token must be a **fine-grained PAT** scoped to *this one repo*,
    permission **Issues: Read and write** only. Not a classic PAT, not
    "all repos" — see README.md for exactly how to mint one. If it leaks,
    the blast radius is "someone can open/edit issues on this repo",
    nothing else.
  * Simple abuse limits below: a per-user cooldown and a rolling hourly cap
    shared by everyone. Tune both to taste.

Every issue is opened with the reporter's Discord identity in the body, and
labeled `bug` — same label the CLI/GUI path uses — so nothing downstream
needs to know an issue came in via Discord vs. the web form.
"""

from __future__ import annotations

import os
import time
from collections import deque

import discord
import requests
from discord import app_commands

# --- configuration (env vars; see README.md) --------------------------------

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO = os.environ.get("GITHUB_REPO", "kevinisgoated24-spec/OCforge")

# Optional: restrict the bot to one server. Leave unset to allow any server
# it's invited to.
_guild_env = os.environ.get("DISCORD_GUILD_ID")
ALLOWED_GUILD_ID = int(_guild_env) if _guild_env else None

# Abuse limits.
PER_USER_COOLDOWN_SECONDS = 300  # one report per user per 5 minutes
MAX_ISSUES_PER_HOUR = 20  # shared across everyone, rolling window
FIELD_MAX_LEN = 1500  # each modal field is truncated to this before filing

_recent_issue_times: deque[float] = deque()


def _hourly_cap_ok() -> bool:
    now = time.time()
    while _recent_issue_times and now - _recent_issue_times[0] > 3600:
        _recent_issue_times.popleft()
    return len(_recent_issue_times) < MAX_ISSUES_PER_HOUR


def _record_issue_filed() -> None:
    _recent_issue_times.append(time.time())


def _truncate(s: str) -> str:
    s = s.strip()
    if len(s) <= FIELD_MAX_LEN:
        return s
    return s[:FIELD_MAX_LEN] + f"\n\n…(truncated at {FIELD_MAX_LEN} chars)"


def _file_github_issue(*, title: str, body: str) -> str:
    """Returns the new issue's HTML URL, or raises requests.HTTPError."""
    resp = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"title": title, "body": body, "labels": ["bug"]},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["html_url"]


class ReportModal(discord.ui.Modal, title="OCforgeReporter: file a bug"):
    ocforge_version = discord.ui.TextInput(
        label="ocforge version (ocforge --version)",
        placeholder="e.g. 0.4.16",
        required=True,
        max_length=40,
    )
    os_field = discord.ui.TextInput(
        label="OS",
        placeholder="Windows / macOS / Linux",
        required=True,
        max_length=40,
    )
    hardware = discord.ui.TextInput(
        label="Hardware (paste `ocforge probe` output)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=FIELD_MAX_LEN,
    )
    what_happened = discord.ui.TextInput(
        label="What happened",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=FIELD_MAX_LEN,
    )
    steps = discord.ui.TextInput(
        label="Steps to reproduce (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=FIELD_MAX_LEN,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not _hourly_cap_ok():
            await interaction.response.send_message(
                "OCforgeReporter has hit its shared hourly limit — please try again "
                "later, or file directly at "
                f"https://github.com/{GITHUB_REPO}/issues/new/choose",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        title = f"[Bug]: {_truncate(self.what_happened.value)[:80].splitlines()[0]}"
        body = (
            f"**ocforge version:** {_truncate(self.ocforge_version.value)}\n"
            f"**OS:** {_truncate(self.os_field.value)}\n"
            f"**Interface:** Discord (`/report`)\n\n"
            f"### Hardware\n```\n{_truncate(self.hardware.value)}\n```\n\n"
            f"### What happened\n{_truncate(self.what_happened.value)}\n\n"
            f"### Steps to reproduce\n{_truncate(self.steps.value) or '_none given_'}\n\n"
            f"---\n"
            f"Filed via OCforgeReporter (Discord) by "
            f"{interaction.user} (`{interaction.user.id}`)"
            + (f" in **{interaction.guild.name}**" if interaction.guild else "")
            + "."
        )

        try:
            url = _file_github_issue(title=title, body=body)
        except requests.HTTPError as e:
            await interaction.followup.send(
                f"Filing the issue failed ({e.response.status_code}): "
                f"{e.response.text[:300]}",
                ephemeral=True,
            )
            return
        except requests.RequestException as e:
            await interaction.followup.send(f"Filing the issue failed: {e}", ephemeral=True)
            return

        _record_issue_filed()
        await interaction.followup.send(f"Filed: {url}", ephemeral=True)


class OCforgeReporterClient(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.none())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        if ALLOWED_GUILD_ID:
            guild = discord.Object(id=ALLOWED_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


client = OCforgeReporterClient()


@client.tree.command(
    name="report", description="File an OCforge bug report on GitHub"
)
@app_commands.checks.cooldown(1, PER_USER_COOLDOWN_SECONDS)
async def report(interaction: discord.Interaction) -> None:
    if ALLOWED_GUILD_ID and (
        interaction.guild is None or interaction.guild.id != ALLOWED_GUILD_ID
    ):
        await interaction.response.send_message(
            "OCforgeReporter isn't enabled in this server.", ephemeral=True
        )
        return
    await interaction.response.send_modal(ReportModal())


@report.error
async def report_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"You can file another report in {error.retry_after:.0f}s.",
            ephemeral=True,
        )
        return
    raise error


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
