# OCforgeReporter (Discord bot)

A `/report` slash command for a Discord server: it opens a form (version, OS,
hardware, what happened, repro steps) and files a GitHub issue on
[OCforge](https://github.com/kevinisgoated24-spec/OCforge) directly.

This is a different trust model from `ocforge report` (CLI) or the GUI's bug
icon — those never hold a credential, they just open a prefilled
`github.com/.../issues/new` and *you* click submit under your own GitHub
account. This bot files the issue **on your behalf**, using a token *it*
holds. That token is scoped as narrowly as GitHub allows (issues on this one
repo, nothing else) and the bot rate-limits itself — see **Security** below
— but it's still a real credential sitting on whatever machine runs the bot.
If that's not a trade-off you want, use `ocforge report` / the GUI instead;
nothing here replaces those.

There's no hosted instance of this — you run your own copy, in your own
server, with your own tokens.

## 1. Create the Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → name it (e.g. "OCforgeReporter").
2. **Bot** tab (left sidebar) → **Reset Token** → copy it. This is `DISCORD_TOKEN`. Treat it like a password — anyone with it can control the bot.
3. Leave **Privileged Gateway Intents** all off — `/report` only needs slash commands and modals, not message content or member lists.
4. **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: just **Send Messages** (that's all it needs)
5. Open the generated URL, pick your server, authorize. The bot joins but does nothing yet.

## 2. Create a scoped GitHub token

Use a **fine-grained personal access token**, not a classic one — a classic
token's scopes are all-or-nothing across every repo you can see; fine-grained
lets you lock it to exactly this.

1. [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)
2. **Repository access** → **Only select repositories** → `kevinisgoated24-spec/OCforge`
3. **Permissions → Repository permissions → Issues** → **Read and write**. Leave every other permission at **No access**.
4. Generate, copy it. This is `GITHUB_TOKEN`. If you don't own the repo, whoever does needs to approve the fine-grained token request (or grant you issue-write access) before it works.

## 3. Configure and run

```bash
cd discordbot
python -m venv .venv && . .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env   # fill in DISCORD_TOKEN and GITHUB_TOKEN
```

Load `.env` however you prefer (`python-dotenv`, your shell, your process
manager) and run:

```bash
python bot.py
```

`/report` should appear in the server within a minute or two (instant if you
set `DISCORD_GUILD_ID` — global command registration is slow to propagate,
per-guild is not).

## Keeping it running

This process needs to stay up for the command to work — it's not something
that runs once and exits. Options, cheapest first:

- **Your own always-on machine** (a home server, a Pi): run it under `systemd`,
  `pm2`, or just a `screen`/`tmux` session that survives logout.
- **A small VPS** (same as above, just not at home).
- **A free-tier PaaS** (Railway, Fly.io, Render, etc.): push this folder,
  set `DISCORD_TOKEN`/`GITHUB_TOKEN` as its secret env vars, set the start
  command to `python bot.py`. Any of them work; none are configured here
  since which one makes sense depends on what you already use.

## Security

- **Token scope.** `GITHUB_TOKEN` must be a fine-grained PAT limited to
  *Issues: Read and write* on this one repo (step 2 above). Never use a
  classic PAT or one with `repo` (full control) scope here — if this bot's
  host is ever compromised, the blast radius should be "spam issues," not
  "push code" or "delete the repo."
- **Rate limits** in `bot.py`: `PER_USER_COOLDOWN_SECONDS` (default 300s —
  one report per person per 5 min) and `MAX_ISSUES_PER_HOUR` (default 20,
  shared across everyone). Both are in-memory, so they reset on restart;
  tune them for your server's size.
- **`DISCORD_GUILD_ID`** restricts `/report` to one server. Set it unless
  you deliberately want the bot usable from anywhere it's invited.
- Every filed issue records the reporter's Discord username + ID in the
  body, and is labeled `bug` — same label `ocforge report`/the GUI use — so
  it's traceable and shows up alongside issues filed the normal way.
- This bot has **no other commands and no other GitHub scope** — it cannot
  read private data, close issues, touch code, or do anything besides open
  an issue with the fields the modal collected.
