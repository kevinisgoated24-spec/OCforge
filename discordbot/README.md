# OCforgeReporter (Discord webhook)

A `/fileissue` slash command for a Discord server: it opens a form (version,
OS, hardware) and hands back a pre-filled GitHub "New issue" link for
[OCforge](https://github.com/kevinisgoated24-spec/OCforge) — you review it,
add what happened, and click **Submit new issue** yourself.

Same trust model as `ocforge report` (CLI) and the GUI's bug icon: this
holds **no GitHub credential**. It never talks to the GitHub API — it just
builds the link client-side, the same way those do.

There's no hosted instance of this — you run your own copy, in your own
server.

## What changed from the old `/report` bot

This used to be a **Gateway bot**: a process (`bot.py`, `discord.py`) that
opened a persistent websocket to Discord and had to stay running and
connected the whole time, needing its own systemd service to babysit it.

It's now a **webhook** — Discord's own term for this is an "Interactions
Endpoint": instead of a bot holding a connection open, Discord sends an HTTP
POST straight to a URL you configure, for every interaction (the slash
command, then the modal submit), and gets a response back like any other
web request. `interactions.py` is that endpoint. Nothing has to stay
connected to Discord; it only exists while handling a request.

One side effect worth knowing: `DISCORD_TOKEN` (the one secret that can
fully control the app) is no longer read by the running service **at all**.
It's only ever used by `register_commands.py`, by hand, to tell Discord the
command exists. The thing the live service holds — `DISCORD_PUBLIC_KEY` —
isn't a secret; it's published on the app's own Developer Portal page, and
exists only to prove a request really came from Discord.

The trade-off: a webhook needs a public HTTPS URL for Discord to reach, so
there's a bit more to set up than "run a script that connects outward." See
**Exposing it publicly**, below.

## 1. Create the Discord application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → name it (e.g. "OCforgeReporter").
2. **General Information** page: copy the **Application ID** and the **Public Key**. These are `DISCORD_APPLICATION_ID` and `DISCORD_PUBLIC_KEY` — neither is secret.
3. **Bot** tab → **Reset Token** → copy it. This is `DISCORD_TOKEN` — treat it like a password. Leave **Privileged Gateway Intents** all off; this never connects to the Gateway at all.
4. **Installation** tab → under **Installation Contexts**, keep only **Guild Install** checked.
5. Build an invite link by hand (the Portal's URL Generator sometimes insists on a redirect URL you don't need for this):
   ```
   https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&scope=applications.commands
   ```
6. Open that URL, pick your server, Authorize.

**Leave "Interactions Endpoint URL" (also on General Information) blank for now** — Discord tests that URL the moment you save it (it sends a PING and needs `{"type":1}` back within 3 seconds, or it refuses to save), so the endpoint has to be live first. Come back to it after step 4 below.

## 2. Configure

```bash
cd discordbot
python -m venv .venv && . .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env   # fill in DISCORD_PUBLIC_KEY, DISCORD_APPLICATION_ID, DISCORD_TOKEN
```

Set `DISCORD_GUILD_ID` in `.env` too if you want the command registered to
one server only (near-instant) instead of globally (up to ~1h the first
time).

## 3. Register the `/fileissue` command

One-time (and again any time the command's name/description changes):

```bash
python register_commands.py
```

This is the only script that reads `DISCORD_TOKEN`.

## 4. Run the endpoint

```bash
python -m waitress --host=127.0.0.1 --port=8787 interactions:app
```

(or `PORT=8787 python interactions.py` for quick local testing — single-
threaded, fine for trying it out, not for real traffic).

This only needs `DISCORD_PUBLIC_KEY` (and `GITHUB_REPO`/`DISCORD_GUILD_ID`
if you set them) — `DISCORD_TOKEN` isn't read here.

Keeping this running long-term is the same problem any small web service
has — systemd, pm2, a container, a free-tier PaaS — and much lighter than
the old bot: there's no persistent outbound connection to maintain, so it
can even scale to zero between requests on something like Fly.io or Cloud
Run, if you'd rather not keep a machine on at all.

## 5. Exposing it publicly

Discord needs to reach this over HTTPS from the public internet. Pick one:

- **Cloudflare Tunnel** (`cloudflared`) — no port-forwarding, no cert to
  manage, works behind CGNAT/home NAT. Point a DNS record at the tunnel,
  run `cloudflared` alongside `waitress` (as its own systemd unit), done.
  Good default if you don't already have a public HTTPS setup.
- **Your own reverse proxy** (Caddy/nginx) in front of `waitress`, with a
  domain + port forward you already control — reuse this if you're already
  running something like it for another service.
- **A PaaS that gives you HTTPS for free** (Fly.io, Render, Railway, a
  Cloud Run container) — push `discordbot/`, set the three env vars, point
  its start command at the `waitress` line above. No tunnel or proxy to run
  yourself at all.

Whichever you pick, the endpoint path is `/interactions` — e.g.
`https://your-domain.example/interactions`. A plain `GET /healthz` returns
`ok` once it's reachable, useful for checking the tunnel/proxy before
touching Discord's settings at all.

Once that URL answers successfully, go back to the Developer Portal →
**General Information** → **Interactions Endpoint URL**, paste it in, and
save. Discord will PING it immediately; if that fails, it tells you why and
won't save the URL.

## Security

- The only secret is `DISCORD_TOKEN`, kept in `discordbot/.env`
  (git-ignored — never commit it), and it's **never read by the running
  service** — only by `register_commands.py`, by hand. `DISCORD_PUBLIC_KEY`
  in that same file isn't a secret (it's public on the Developer Portal);
  it's there only so the endpoint can verify a request's Ed25519 signature
  actually came from Discord. No GitHub token, no write access to the repo,
  anywhere in this project.
- Every request to `/interactions` is signature-checked
  (`verify_signature` in `interactions.py`, following Discord's own scheme)
  before anything in it is trusted; an unsigned or mis-signed request gets a
  plain 401.
- `/fileissue` never files anything itself — it hands the reporter a link
  and they submit it under their own GitHub account, so every issue is
  attributed to whoever actually filed it, same as filing one by hand.
- `DISCORD_GUILD_ID` restricts `/fileissue` to one server (and, when set,
  `register_commands.py` registers it as a guild-only command in the first
  place, so it's never even visible elsewhere).
- A light per-user cooldown (`PER_USER_COOLDOWN_SECONDS` in
  `interactions.py`, default 30s, in-process memory) just keeps someone
  from spam-opening the modal — there's no credential-abuse risk to
  rate-limit against here.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

No network and no real Discord app needed — a throwaway Ed25519 keypair
stands in for Discord's, and Flask's test client drives `/interactions`
exactly as a real request would.
