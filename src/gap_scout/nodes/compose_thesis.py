"""Node 6: render the final HTML brief from surviving tickers + regime.

Deliberately NOT an LLM call. Every piece of content used here (catalyst,
category_label, thesis, plan_bias, plan_action, conviction, market_regime)
already exists in state by this point, generated upstream by research_ticker
(per-ticker, in parallel, with full headline context) and market_regime.
Templating this deterministically in Python means the visual structure --
colored bias dots, the market-regime callout box, the high-conviction
cards, the pass-list table -- renders identically every single run,
instead of varying run-to-run the way an LLM asked to freehand-write HTML
would. All styling is inline (no <style> blocks, no external CSS) since
most email clients, including Gmail, strip anything else.
"""
from __future__ import annotations

import html

from src.gap_scout.state import GraphState, TickerAssessment

# A ticker with conviction >= this goes in the "High-Conviction" section
# with the full Catalyst/Thesis/Plan card; below it, it goes in the
# "Low-Conviction / Pass" table instead.
HIGH_CONVICTION_THRESHOLD = 4


def _esc(text: str) -> str:
    return html.escape(str(text), quote=False)


def _regime_box(market_regime: str) -> str:
    return f"""
<h2 style="margin:24px 0 8px;">📊 Market Regime</h2>
<div style="background:#f4f4f6;border-left:4px solid #333;border-radius:6px;
padding:14px 16px;color:#222;line-height:1.5;">
{_esc(market_regime)}
</div>
"""


def _high_conviction_card(t: TickerAssessment) -> str:
    dot = "🟢" if t["plan_bias"] == "Long" else "🔴"
    bias_word = "LONG" if t["plan_bias"] == "Long" else "SHORT"
    sign = "+" if t["gap_pct"] >= 0 else ""
    return f"""
<h3 style="margin:20px 0 6px;">{dot} {_esc(t['ticker'])} ({sign}{t['gap_pct']:.2f}%) | {_esc(t['category_label'])}</h3>
<ul style="margin:0 0 4px;padding-left:20px;line-height:1.5;">
<li><b>Catalyst:</b> {_esc(t['category_label'])}. {_esc(t['summary'])}</li>
<li><b>Thesis:</b> {_esc(t['thesis'])}</li>
<li><b>Plan:</b> <b>BIAS: {bias_word}.</b> {_esc(t['plan_action'])}</li>
</ul>
"""


def _pass_table(rows: list[TickerAssessment]) -> str:
    if not rows:
        return "<p>Nothing in the low-conviction list today.</p>"

    header = """
<tr style="background:#f4f4f6;text-align:left;">
<th style="padding:8px;border-bottom:1px solid #ccc;">Ticker</th>
<th style="padding:8px;border-bottom:1px solid #ccc;">Gap %</th>
<th style="padding:8px;border-bottom:1px solid #ccc;">Category</th>
<th style="padding:8px;border-bottom:1px solid #ccc;">Bias / Core Action Plan</th>
</tr>
"""
    body_rows = []
    for t in rows:
        sign = "+" if t["gap_pct"] >= 0 else ""
        body_rows.append(f"""
<tr>
<td style="padding:8px;border-bottom:1px solid #eee;font-weight:600;">{_esc(t['ticker'])}</td>
<td style="padding:8px;border-bottom:1px solid #eee;">{sign}{t['gap_pct']:.2f}%</td>
<td style="padding:8px;border-bottom:1px solid #eee;">{_esc(t['category_label'])}</td>
<td style="padding:8px;border-bottom:1px solid #eee;"><b>PASS.</b> {_esc(t['thesis'])}</td>
</tr>
""")
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        + header
        + "".join(body_rows)
        + "</table>"
    )


def compose_thesis(state: GraphState) -> dict:
    assessed = sorted(state["assessed"], key=lambda t: t["conviction"], reverse=True)

    high = [t for t in assessed if t["conviction"] >= HIGH_CONVICTION_THRESHOLD]
    low = [t for t in assessed if t["conviction"] < HIGH_CONVICTION_THRESHOLD]

    parts = [
        f'<h1 style="margin:0 0 4px;">☀️ Pre-Market Thesis Brief: {_esc(state["run_date"])}</h1>',
        _regime_box(state["market_regime"]),
    ]

    if not assessed:
        parts.append(
            '<h2 style="margin:24px 0 8px;">Today\'s Gappers</h2>'
            "<p>No gappers cleared the scan today. Sit on hands and let the setup come to you.</p>"
        )
    else:
        if high:
            parts.append('<h2 style="margin:24px 0 8px;">🔥 High-Conviction Stocks In Play</h2>')
            parts.extend(_high_conviction_card(t) for t in high)
        if low:
            parts.append('<h2 style="margin:24px 0 8px;">⚠️ Low-Conviction / Pass List</h2>')
            parts.append(_pass_table(low))

    return {"email_body": "\n".join(parts)}