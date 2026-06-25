#!/usr/bin/env bash
# Deploy STI API + Telegram bot to Vercel
set -euo pipefail
cd "$(dirname "$0")"
bash build.sh
echo "Deploying to Vercel..."
npx --yes vercel deploy --prod "$@"
echo ""
echo "Next steps:"
echo "  1. Set env vars in Vercel dashboard (STI_API_KEY, TELEGRAM_BOT_TOKEN, API keys)"
echo "  2. curl -X POST 'https://YOUR-APP.vercel.app/telegram/set-webhook?url=https://YOUR-APP.vercel.app/telegram/webhook' -H 'X-Api-Key: YOUR_KEY'"
echo "  3. Message your bot: /signal AAPL"
