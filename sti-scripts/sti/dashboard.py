"""Generate v2 dashboard from latest scan."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def render(scan: dict[str, Any], macro: dict | None = None) -> str:
    date = scan.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    signals = scan.get("signals", [])
    macro_html = ""
    if macro and macro.get("series"):
        parts = []
        for k, v in macro["series"].items():
            parts.append(f"<span>{html.escape(k.replace('_', ' '))}: {v.get('value')}</span>")
        macro_html = f'<div class="macro"><strong>Macro:</strong> {" ".join(parts)}</div>'

    cards = ""
    for s in signals:
        rec = s.get("recommendation", "Hold")
        cls = "buy" if "Buy" in rec else "sell" if "Sell" in rec else "hold"
        ticker = s.get("ticker", "?")
        cards += f'''<div class="card"><a href="../signals/{ticker}-{date}.html">{html.escape(ticker)}</a>
        <div class="meta {cls}">{html.escape(rec)} · {s.get("confidence_pct",0)}% · R/R {s.get("risk_reward_ratio","?")}</div></div>'''

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>STI Dashboard v2</title>
<style>
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:2rem}}
h1{{margin:0}} .sub{{color:#94a3b8;margin:.5rem 0 1.5rem}}
.badge{{display:inline-block;background:#14532d;color:#86efac;padding:.2rem .6rem;border-radius:6px;font-size:.8rem;margin-bottom:1rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem}}
.card{{background:#1e293b;border-radius:12px;padding:1.25rem;border:1px solid #334155}}
.card a{{color:#38bdf8;font-weight:600;font-size:1.2rem;text-decoration:none}}
.meta{{font-size:.85rem;color:#94a3b8;margin-top:.4rem}}
.buy{{color:#22c55e}} .sell{{color:#ef4444}} .hold{{color:#eab308}}
.macro{{background:#1e293b;padding:1rem;border-radius:8px;margin-bottom:1rem;font-size:.9rem}}
.macro span{{margin-right:1.2rem}}
.api{{margin-top:2rem;color:#94a3b8;font-size:.9rem}}
</style></head><body>
<h1>Stock Signal Intelligence v2</h1>
<p class="sub">Dashboard — {html.escape(date)} · Production engine</p>
<div class="badge">Transparent scoring · Calibrated confidence · Agent tracking</div>
{macro_html}
<div class="grid">{cards}</div>
<div class="api">
<p><strong>API:</strong> <code>uvicorn api.main:app --port 8000</code> from <code>skills/shared/sti-scripts</code></p>
<p>Endpoints: <code>GET /signal/AAPL</code> · <code>POST /scan</code> · <code>GET /opportunities</code> · <code>GET /performance/agents</code></p>
</div>
</body></html>"""


def write_dashboard(reports_dir: Path, scan_path: Path, macro_path: Path | None = None) -> Path:
    scan = json.loads(scan_path.read_text(encoding="utf-8"))
    macro = json.loads(macro_path.read_text()) if macro_path and macro_path.is_file() else None
    out = reports_dir / "dashboard.html"
    out.write_text(render(scan, macro), encoding="utf-8")
    return out
