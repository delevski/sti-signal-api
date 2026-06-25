# STI on Vercel

Deploy the Stock Signal Intelligence API + Telegram bot to Vercel serverless.

## Prerequisites

- [Vercel account](https://vercel.com)
- API keys in Vercel project env (see below)
- Telegram bot token from [@BotFather](https://t.me/BotFather)

## Deploy

### Option A — One-click import (recommended)

Open this link while logged into Vercel:

**https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fdelevski%2Fsti-signal-api&project-name=sti-signal-api&teamSlug=oris-projects-1434bdbc**

1. Click **Continue with GitHub** → **Deploy**
2. Add env vars from [`.env.example`](.env.example) in Vercel dashboard
3. Redeploy once env vars are saved

### Option B — CLI

```bash
cd sti-platform/vercel
vercel login
bash deploy.sh
```

### Option C — GitHub Actions

Add secrets to the repo: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` (from `.vercel/project.json` after first deploy).

Repo: **https://github.com/delevski/sti-signal-api**

```bash
cd sti-platform/vercel
bash build.sh
npx vercel --prod
```

Or link the repo in Vercel dashboard with **Root Directory** = `sti-platform/vercel`.

## Environment variables (Vercel dashboard)

| Variable | Required | Description |
|----------|----------|-------------|
| `STI_API_KEY` | Recommended | Protects API endpoints (`X-Api-Key` header) |
| `STI_FINNHUB_KEY` | Optional | News via Finnhub |
| `STI_ALPHA_VANTAGE_KEY` | Optional | Extra data |
| `STI_FRED_KEY` | Optional | Macro series |
| `TELEGRAM_BOT_TOKEN` | For bot | From BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | Recommended | Random string; set on webhook |

`VERCEL=1` is set automatically in `vercel.json`.

## After deploy

1. **Health check**
   ```bash
   curl https://YOUR-APP.vercel.app/health
   ```

2. **Signal (external API)**
   ```bash
   curl -H "X-Api-Key: YOUR_KEY" https://YOUR-APP.vercel.app/signal/JPM
   ```

3. **Register Telegram webhook** (once)
   ```bash
   curl -X POST "https://YOUR-APP.vercel.app/telegram/set-webhook?url=https://YOUR-APP.vercel.app/telegram/webhook" \
     -H "X-Api-Key: YOUR_KEY"
   ```

4. **Use the bot** — message your bot: `/signal NVDA`

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| GET | `/signal/{ticker}` | Full JSON signal |
| GET | `/signal/{ticker}/report` | HTML report |
| POST | `/scan` | Run watchlist scan |
| GET | `/opportunities` | Ranked opportunities |
| GET | `/performance/agents` | Agent stats |
| GET | `/alerts` | Recent alerts |
| GET | `/history/{ticker}` | Signal history |
| POST | `/telegram/webhook` | Telegram updates |
| POST | `/telegram/set-webhook` | Register webhook |

Interactive docs: `https://YOUR-APP.vercel.app/docs`

## Limitations on Vercel

- **60s max** per request (Pro plan). Single-ticker `/signal` fits; full `/scan` may timeout on large watchlists.
- **Ephemeral storage** — SQLite and cache live in `/tmp` and reset between cold starts. Use Render/Docker for persistent learning history.
- **No vectorbt backtests** in this deploy bundle (slim `requirements.txt`).

For heavy workloads, use `sti-platform/Dockerfile` on Render/Railway and point your Telegram bot or clients at that URL instead.

## Local test (Vercel-style)

```bash
cd sti-platform/vercel
bash build.sh
export VERCEL=1 STI_API_KEY=test TELEGRAM_BOT_TOKEN=...
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```
