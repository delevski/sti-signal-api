"""Rich HTML reports with Chart.js."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any


def render(signal: dict[str, Any], price_history: list[dict] | None = None, signal_history: list[dict] | None = None) -> str:
    ticker = signal.get("ticker", "?")
    rec = signal.get("recommendation", "Hold")
    conf = signal.get("confidence_pct", 0)
    cal = signal.get("confidence_calibration", {})
    color = {"Strong Buy": "#16a34a", "Buy": "#22c55e", "Hold": "#eab308", "Sell": "#ef4444", "Strong Sell": "#b91c1c"}.get(rec, "#6b7280")

    # Score breakdown table
    breakdown_rows = ""
    for row in signal.get("score_breakdown", []):
        breakdown_rows += f"""<tr>
          <td>{html.escape(row.get('agent',''))}</td>
          <td>{html.escape(str(row.get('signal','')))}</td>
          <td>{row.get('weight',0):.3f}</td>
          <td>{row.get('signal_score',0)}</td>
          <td>{row.get('agent_confidence_pct',0)}%</td>
          <td><code>{html.escape(row.get('formula_term',''))}</code></td>
          <td>{row.get('contribution',0):.4f}</td>
        </tr>"""

    explain = signal.get("explainability", {})
    quality = signal.get("quality_issues", [])
    formula = signal.get("formula") or {}
    formula_text = formula.get("plain_english", "")
    formula_expr = formula.get("expression", "")

    prices_json = json.dumps([r.get("close") for r in (price_history or [])[-60:]])
    dates_json = json.dumps([r.get("date") for r in (price_history or [])[-60:]])
    hist_labels = json.dumps([h.get("date") for h in reversed(signal_history or [])])
    hist_recs = json.dumps([h.get("recommendation") for h in reversed(signal_history or [])])

    agent_perf = signal.get("agent_performance", {})
    perf_rows = "".join(
        f"<tr><td>{html.escape(a)}</td><td>{m.get('win_rate',0)*100:.1f}%</td><td>{m.get('avg_return',0):.2f}%</td></tr>"
        for a, m in agent_perf.items()
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><title>STI — {html.escape(ticker)}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:1.5rem}}
.wrap{{max-width:1100px;margin:0 auto}}
.card{{background:#1e293b;border-radius:12px;padding:1.25rem;margin:1rem 0;border:1px solid #334155}}
.rec{{font-size:2.2rem;font-weight:700;color:{color}}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}}
table{{width:100%;border-collapse:collapse;font-size:.9rem}}
th,td{{border:1px solid #334155;padding:.45rem;text-align:left}}
code{{font-size:.8rem}}
.issue{{color:#f87171}} .ok{{color:#86efac}}
canvas{{max-height:280px}}
h2{{margin-top:0;font-size:1.1rem}}
</style></head><body><div class="wrap">
<h1>{html.escape(ticker)} — Stock Signal Intelligence v2</h1>
<p style="color:#94a3b8">Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>

<div class="card">
  <div class="rec">{html.escape(rec)}</div>
  <p>Calibrated confidence: <strong>{conf}%</strong>
    (interval {cal.get('confidence_interval_low','?')}–{cal.get('confidence_interval_high','?')}%,
    uncertainty: {cal.get('uncertainty','?')})</p>
  <p>Risk: {html.escape(signal.get('risk_level',''))} |
     R/R: {signal.get('risk_reward_ratio','N/A')} |
     Position: {signal.get('position_size_pct','N/A')}%</p>
  <p>Stop: {signal.get('stop_loss')} | Targets: {signal.get('take_profit_targets')}</p>
</div>

<div class="card"><h2>How the score was calculated</h2>
<p>{html.escape(formula_text)}</p>
<p><code>{html.escape(formula_expr)}</code></p>
<table>
<tr><th>Agent</th><th>Signal</th><th>Weight</th><th>Score</th><th>Conf</th><th>Term</th><th>Contribution</th></tr>
{breakdown_rows}
</table>
</div>

<div class="card"><h2>Plain English</h2>
<p>{html.escape(explain.get('plain_english',''))}</p>
<h3>Supporting</h3><ul>{''.join(f'<li>{html.escape(s)}</li>' for s in explain.get('supporting_data',[])[:6])}</ul>
<h3>Contradicting</h3><ul>{''.join(f'<li class="issue">{html.escape(s)}</li>' for s in explain.get('contradicting_data',[])[:5])}</ul>
<h3>Could invalidate</h3><ul>{''.join(f'<li>{html.escape(s)}</li>' for s in explain.get('could_invalidate',[])[:4])}</ul>
</div>

<div class="grid2">
  <div class="card"><h2>Price history</h2><canvas id="priceChart"></canvas></div>
  <div class="card"><h2>Signal history</h2><canvas id="sigChart"></canvas></div>
</div>

<div class="card"><h2>Agent performance (historical)</h2>
<table><tr><th>Agent</th><th>Win rate</th><th>Avg return</th></tr>{perf_rows or '<tr><td colspan=3>No history yet</td></tr>'}</table>
</div>

<div class="card"><h2>Quality control</h2>
{'<ul>' + ''.join(f'<li class="issue">[{html.escape(i.get("severity",""))}] {html.escape(i.get("message",""))}</li>' for i in quality) + '</ul>' if quality else '<p class="ok">No quality issues detected</p>'}
</div>

<p style="color:#64748b;font-size:.85rem">{html.escape(signal.get('disclaimer',''))}</p>
</div>
<script>
new Chart(document.getElementById('priceChart'),{{type:'line',data:{{labels:{dates_json},datasets:[{{label:'Close',data:{prices_json},borderColor:'#38bdf8',tension:.2}}]}},options:{{plugins:{{legend:{{labels:{{color:'#e2e8f0'}}}}}},scales:{{x:{{ticks:{{color:'#94a3b8'}}}},y:{{ticks:{{color:'#94a3b8'}}}}}}}}}});
new Chart(document.getElementById('sigChart'),{{type:'bar',data:{{labels:{hist_labels},datasets:[{{label:'Signal',data:{hist_recs},backgroundColor:'#6366f1'}}]}},options:{{plugins:{{legend:{{display:false}}}}}}}});
</script>
</body></html>"""
