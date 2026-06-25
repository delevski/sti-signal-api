#!/usr/bin/env python3
"""Generate HTML signal report from ensemble JSON."""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path


def render(data: dict, title: str | None = None) -> str:
    ticker = data.get("ticker", "UNKNOWN")
    title = title or f"STI Signal — {ticker}"
    rec = data.get("recommendation", "Hold")
    conf = data.get("confidence_pct", 0)
    risk = data.get("risk_level", "Medium")
    color = {"Strong Buy": "#16a34a", "Buy": "#22c55e", "Hold": "#eab308", "Sell": "#ef4444", "Strong Sell": "#b91c1c"}.get(rec, "#6b7280")

    agents_html = ""
    for agent, info in (data.get("agent_scores") or {}).items():
        if isinstance(info, dict) and "signal" in info:
            agents_html += f"<tr><td>{html.escape(agent)}</td><td>{html.escape(str(info.get('signal')))}</td><td>{info.get('confidence', '')}%</td></tr>"

    evidence = data.get("evidence", {})
    ev_html = f"<pre>{html.escape(json.dumps(evidence, indent=2))}</pre>" if evidence else "<p>No additional evidence.</p>"

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;background:#0f172a;color:#e2e8f0}}
.card{{background:#1e293b;border-radius:12px;padding:1.5rem;margin:1rem 0}}
.rec{{font-size:2rem;font-weight:700;color:{color}}}
table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #334155;padding:.5rem;text-align:left}}
.disclaimer{{font-size:.85rem;color:#94a3b8;margin-top:2rem}}
</style></head><body>
<h1>{html.escape(title)}</h1>
<p>Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
<div class="card"><div class="rec">{html.escape(rec)}</div>
<p>Confidence: <strong>{conf}%</strong> | Risk: <strong>{html.escape(risk)}</strong></p>
<p>Stop-loss: {data.get('stop_loss', 'N/A')} | Take-profit: {data.get('take_profit_targets', 'N/A')}</p>
<p>Position size: {data.get('position_size_pct', 'N/A')}% of portfolio</p></div>
<div class="card"><h2>Agent Scores</h2><table><tr><th>Agent</th><th>Signal</th><th>Confidence</th></tr>{agents_html}</table></div>
<div class="card"><h2>Evidence</h2>{ev_html}</div>
<p class="disclaimer">{html.escape(data.get('disclaimer', 'Probabilistic prediction, not financial advice.'))}</p>
</body></html>"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    Path(args.output).write_text(render(data), encoding="utf-8")
    print(json.dumps({"status": "ok", "output": args.output}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
