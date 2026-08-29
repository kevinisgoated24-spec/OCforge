# OCforgeReporter (Discord bot)

A `/report` slash command for a Discord server: it opens a form (version, OS,
hardware) and hands back a pre-filled GitHub "New issue" link for
[OCforge](https://github.com/kevinisgoated24-spec/OCforge) — you review it,
add what happened, and click **Submit new issue** yourself.

Same trust model as `ocforge report` (CLI) and the GUI's bug icon: this bot
holds **no GitHub credential**. It never talks to the GitHub API — it just
builds the link client-side, the same way those do. The only secret it needs
is its own Discord bot token.

There's no hosted instance of this — you run your own copy, in your own
server.

## 1. Create the Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → name it (e.g. "OCforgeReporter").
2. **Bot** tab (left sidebar) → **Reset Token** → copy it. This is `DISCORD_TOKEN`. Treat it like a password — anyone with it can control the bot.
3. Leave **Privileged Gateway Intents** all off, and **"Requires OAuth2 Code Grant"** off — `/report` only needs slash commands and modals.
4. **Installation** tab → under **Installation Contexts**, keep only **Guild Install** checked.
5. Build an invite link by hand (the Portal's URL Generator sometimes insists on a redirect URL you don't need for this):
   ```
   https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot%20applications.commands&permissions=2048
   ```
   (`YOUR_CLIENT_ID` is on the **OAuth2 → General** page; `permissions=2048` = Send Messages.)
6. Open that URL, pick your server, Authorize.

## 2. Configure and run

```bash
cd discordbot
python -m venv .venv && . .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env   # fill in DISCORD_TOKEN
```

Load `.env` however you prefer (`python-dotenv`, your shell, your process
manager) and run:

```bash
python bot.py
```

Set `DISCORD_GUILD_ID` in `.env` to your server's ID for instant command
registration; leave it unset and the command still works, it just takes
Discord up to ~an hour to propagate a global command the first time.

## Keeping it running

This process needs to stay up for the command to work — it's not something
that runs once and exits. Options, cheapest first:

- **Your own always-on machine** (a home server, a Pi): run it under `systemd`,
  `pm2`, or just a `screen`/`tmux` session that survives logout.
- **A small VPS** (same as above, just not at home).
- **A free-tier PaaS** (Railway, Fly.io, Render, etc.): push this folder,
  set `DISCORD_TOKEN` as its secret env var, set the start command to
  `python bot.py`. Any of them work; none are configured here since which
  one makes sense depends on what you already use.

## Security

- The only secret is `DISCORD_TOKEN`, kept in `discordbot/.env`
  (git-ignored — never commit it). No GitHub token, no write access to the
  repo, anywhere in this bot.
- `/report` never files anything itself — it hands the reporter a link and
  they submit it under their own GitHub account, so every issue is
  attributed to whoever actually filed it, same as filing one by hand.
- `DISCORD_GUILD_ID` restricts `/report` to one server. Set it unless you
  deliberately want the bot usable from anywhere it's invited.
- A light per-user cooldown (`PER_USER_COOLDOWN_SECONDS` in `bot.py`, default
  30s) just keeps someone from spam-opening the modal — there's no
  credential-abuse risk to rate-limit against here.
