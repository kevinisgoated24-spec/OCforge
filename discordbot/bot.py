"""OCforgeReporter — Discord bot.

A `/report` slash command that opens a modal (version, OS, hardware, what
happened, repro steps) and hands back a pre-filled GitHub "New issue" link —
same fields, same issue form (`.github/ISSUE_TEMPLATE/bug_report.yml`), same
`ocforge report` / GUI bug-button logic, just reached from Discord.

Matches their trust model exactly: this bot holds **no GitHub credential at
all**. It never talks to the GitHub API — it just builds a URL client-side
and hands it back. The reporter clicks it and submits the issue themselves,
under their own GitHub account. If this bot's host were ever compromised,
there is nothing here to steal that grants any access to the repo.

The only secret this needs is DISCORD_TOKEN.
"""

from __future__ import annotations

import os
import urllib.parse

import discord
from discord import app_commands

# --- configuration (env vars; see README.md) --------------------------------

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GITHUB_REPO = os.environ.get("GITHUB_REPO", "kevinisgoated24-spec/OCforge")

# Optional: restrict the bot to one server. Leave unset to allow any server
# it's invited to.
_guild_env = os.environ.get("DISCORD_GUILD_ID")
ALLOWED_GUILD_ID = int(_guild_env) if _guild_env else None

# Light spam guard — nothing to secure here (no credential), just keeps one
# person from re-opening the modal in a loop.
PER_USER_COOLDOWN_SECONDS = 30
FIELD_MAX_LEN = 1500  # each modal field is truncated before going in the URL


def _truncate(s: str) -> str:
    s = s.strip()
    if len(s) <= FIELD_MAX_LEN:
        return s
    return s[:FIELD_MAX_LEN] + f"\n\n…(truncated at {FIELD_MAX_LEN} chars)"


def _build_issue_url(*, ocforge_version: str, os_name: str, hardware: str) -> str:
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

    async def on_submit(self, interaction: discord.Interaction) -> None:
        url = _build_issue_url(
            ocforge_version=self.ocforge_version.value,
            os_name=self.os_field.value,
            hardware=self.hardware.value,
        )
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Open on GitHub", style=discord.ButtonStyle.link, url=url
            )
        )
        await interaction.response.send_message(
            "Your version/OS/hardware are filled in — add what happened and "
            "hit **Submit new issue** yourself on GitHub:",
            view=view,
            ephemeral=True,
        )


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
    name="report", description="Get a pre-filled GitHub bug-report link for OCforge"
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
            f"Try again in {error.retry_after:.0f}s.", ephemeral=True
        )
        return
    raise error


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
