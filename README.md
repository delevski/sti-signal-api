# Stock Signal Intelligence API

A deployable market-analysis API that turns live price data into technical signals, opportunity scans, performance history, and Telegram bot responses. It packages the project's signal pipeline behind a FastAPI service designed for Vercel serverless deployments.

## What it does

- Generates a signal and an expanded report for a ticker
- Scans a configurable watchlist for opportunities
- Exposes alerts, signal history, and agent performance
- Uses Yahoo Finance market data with optional Finnhub, Alpha Vantage, and FRED inputs
- Supports API-key protection through the `X-Api-Key` header
- Includes Telegram webhook commands for checking signals from chat
- Persists lightweight serverless cache data between pipeline runs

## Stack

- Python
- FastAPI
- pandas, NumPy, and yfinance
- Vercel serverless functions
- Telegram Bot API

## Run locally

```bash
git clone https://github.com/delevski/sti-signal-api.git
cd sti-signal-api
python -m venv .venv
source .venv/bin/activate # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload
```

Open `http://localhost:8000/docs` for the interactive API documentation.

## Main endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health check |
| `GET` | `/signal/{ticker}` | Current signal for one ticker |
| `GET` | `/signal/{ticker}/report` | Expanded signal report |
| `GET` | `/scan` | Scan a comma-separated ticker list |
| `GET` | `/opportunities` | Ranked watchlist opportunities |
| `GET` | `/agent-performance` | Signal-agent performance data |
| `GET` | `/alerts` | Recent alerts |
| `GET` | `/history/{ticker}` | Historical signals for a ticker |
| `POST` | `/telegram/webhook` | Telegram bot webhook |

Protected endpoints expect `X-Api-Key` when `STI_API_KEY` is configured.

## Configuration

Copy `.env.example` to `.env` and add only the services you need. Core market data works through Yahoo Finance; other providers and Telegram are optional. Never commit real keys.

## Deploy to Vercel

The repository includes `vercel.json`, `build.sh`, and `deploy.sh`.

```bash
bash build.sh
vercel --prod
```

After adding environment variables in Vercel, verify the deployment:

```bash
curl https://YOUR-APP.vercel.app/health
```

## Notes

Vercel functions have an ephemeral filesystem and execution limits. The included cache layer is suitable for lightweight signal data, not durable application storage. Financial signals are informational and are not investment advice.
