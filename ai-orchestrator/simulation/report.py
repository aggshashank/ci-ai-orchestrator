"""
HTML simulation report generator — no external dependencies, pure stdlib + inline SVG.
"""
from __future__ import annotations

from simulation.comparator import interpret_p_value
from simulation.models import ChangedDecision, RecommendationDistribution


def generate_html_report(
    simulation_id: str,
    strategy_version: str,
    baseline: RecommendationDistribution,
    simulated: RecommendationDistribution,
    changed: list[ChangedDecision],
    p_value: float,
    sample_size: int,
    date_range: str,
) -> str:
    change_rate = len(changed) / max(sample_size, 1) * 100
    interpretation = interpret_p_value(p_value)

    categories = ["APPROVE", "DECLINE", "MANUAL_REVIEW"]
    b_counts = [getattr(baseline, c) for c in categories]
    s_counts = [getattr(simulated, c) for c in categories]
    b_total = max(baseline.total, 1)
    s_total = max(simulated.total, 1)
    b_pcts = [round(c / b_total * 100, 1) for c in b_counts]
    s_pcts = [round(c / s_total * 100, 1) for c in s_counts]

    bars_html = _grouped_bar_chart(categories, b_pcts, s_pcts)
    changed_rows = _changed_table(changed[:100])  # cap display at 100

    colour_map = {"APPROVE": "#22c55e", "DECLINE": "#ef4444", "MANUAL_REVIEW": "#f59e0b"}

    dist_rows = ""
    for cat in categories:
        bc = getattr(baseline, cat)
        sc = getattr(simulated, cat)
        delta = sc - bc
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        colour = colour_map[cat]
        dist_rows += (
            f"<tr><td><span style='color:{colour};font-weight:600'>{cat}</span></td>"
            f"<td>{bc} ({b_pcts[categories.index(cat)]}%)</td>"
            f"<td>{sc} ({s_pcts[categories.index(cat)]}%)</td>"
            f"<td>{delta_str}</td></tr>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Simulation Report — {strategy_version}</title>
<style>
  body {{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;color:#1e293b;line-height:1.5}}
  h1 {{font-size:1.5rem;font-weight:700;margin-bottom:.25rem}}
  h2 {{font-size:1.1rem;font-weight:600;margin-top:2rem;border-bottom:1px solid #e2e8f0;padding-bottom:.25rem}}
  .meta {{color:#64748b;font-size:.875rem;margin-bottom:1.5rem}}
  .stat-grid {{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin:1rem 0}}
  .stat {{background:#f8fafc;border:1px solid #e2e8f0;border-radius:.5rem;padding:.75rem 1rem}}
  .stat-val {{font-size:1.75rem;font-weight:700}}
  .stat-lbl {{font-size:.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
  table {{width:100%;border-collapse:collapse;font-size:.875rem;margin-top:.5rem}}
  th {{background:#f1f5f9;text-align:left;padding:.5rem .75rem;font-weight:600}}
  td {{padding:.5rem .75rem;border-bottom:1px solid #f1f5f9}}
  .badge {{display:inline-block;padding:.15rem .5rem;border-radius:.25rem;font-size:.75rem;font-weight:600}}
  .badge-approve {{background:#dcfce7;color:#16a34a}}
  .badge-decline {{background:#fee2e2;color:#dc2626}}
  .badge-review {{background:#fef9c3;color:#d97706}}
  .interp {{background:#eff6ff;border-left:4px solid #3b82f6;padding:.75rem 1rem;border-radius:.25rem;margin:.5rem 0}}
  .warn {{background:#fff7ed;border-left:4px solid #f97316;padding:.75rem 1rem;border-radius:.25rem}}
</style>
</head>
<body>
<h1>Decision Simulation Report</h1>
<div class="meta">
  Simulation ID: <code>{simulation_id}</code> &nbsp;|&nbsp;
  Strategy: <strong>{strategy_version}</strong> &nbsp;|&nbsp;
  Sample: {sample_size} decisions ({date_range})
</div>

<div class="stat-grid">
  <div class="stat"><div class="stat-val">{sample_size}</div><div class="stat-lbl">Decisions Sampled</div></div>
  <div class="stat"><div class="stat-val">{len(changed)}</div><div class="stat-lbl">Changed</div></div>
  <div class="stat"><div class="stat-val">{change_rate:.1f}%</div><div class="stat-lbl">Change Rate</div></div>
  <div class="stat"><div class="stat-val">{p_value:.4f}</div><div class="stat-lbl">p-value (χ²)</div></div>
</div>

<div class="interp">{interpretation}</div>
{"<div class='warn'>⚠️ High change rate detected (&gt;10%). Review changed decisions before activating this strategy.</div>" if change_rate > 10 else ""}

<h2>Recommendation Distribution</h2>
<table>
  <tr><th>Outcome</th><th>Baseline</th><th>Simulated</th><th>Δ Count</th></tr>
  {dist_rows}
</table>

<h2>Distribution Chart (%)</h2>
{bars_html}

<h2>Changed Decisions ({len(changed)} total{", first 100 shown" if len(changed) > 100 else ""})</h2>
{changed_rows}

</body>
</html>"""


def _grouped_bar_chart(
    categories: list[str],
    baseline_pcts: list[float],
    simulated_pcts: list[float],
) -> str:
    colours = {"APPROVE": "#22c55e", "DECLINE": "#ef4444", "MANUAL_REVIEW": "#f59e0b"}
    bar_width = 30
    group_gap = 60
    chart_height = 200
    max_val = max(max(baseline_pcts), max(simulated_pcts), 1)

    def bar(x: float, pct: float, colour: str, label: str) -> str:
        h = int(pct / max_val * chart_height)
        y = chart_height - h + 40
        return (
            f'<rect x="{x:.0f}" y="{y}" width="{bar_width}" height="{h}" '
            f'fill="{colour}" opacity="0.9"/>'
            f'<text x="{x + bar_width/2:.0f}" y="{y - 4}" text-anchor="middle" '
            f'font-size="10" fill="#374151">{pct}%</text>'
        )

    svg_parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="700" height="280" '
                 'style="font-family:system-ui,sans-serif">']
    svg_parts.append(f'<line x1="40" y1="{chart_height+40}" x2="660" y2="{chart_height+40}" '
                     f'stroke="#e2e8f0" stroke-width="1"/>')

    for i, cat in enumerate(categories):
        gx = 60 + i * (bar_width * 2 + group_gap)
        col = colours.get(cat, "#94a3b8")
        svg_parts.append(bar(gx, baseline_pcts[i], col, "baseline"))
        svg_parts.append(bar(gx + bar_width + 4, simulated_pcts[i], col, "simulated"))
        label_x = gx + bar_width
        svg_parts.append(
            f'<text x="{label_x}" y="{chart_height + 60}" text-anchor="middle" '
            f'font-size="11" fill="#1e293b">{cat}</text>'
        )

    # Legend
    svg_parts.append(
        '<rect x="300" y="255" width="12" height="12" fill="#94a3b8" opacity="0.5"/>'
        '<text x="316" y="265" font-size="11" fill="#64748b">Baseline</text>'
        '<rect x="380" y="255" width="12" height="12" fill="#94a3b8" opacity="0.9"/>'
        '<text x="396" y="265" font-size="11" fill="#64748b">Simulated</text>'
    )
    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _changed_table(changed: list[ChangedDecision]) -> str:
    if not changed:
        return "<p style='color:#64748b'>No decisions changed.</p>"

    _badge = {
        "APPROVE": "badge-approve",
        "DECLINE": "badge-decline",
        "MANUAL_REVIEW": "badge-review",
    }

    def badge(val: str) -> str:
        cls = _badge.get(val, "")
        return f'<span class="badge {cls}">{val}</span>'

    rows = "".join(
        f"<tr><td><code>{c.correlation_id[:12]}…</code></td>"
        f"<td>{badge(c.original)}</td><td>{badge(c.simulated)}</td></tr>\n"
        for c in changed
    )
    return (
        "<table><tr><th>Correlation ID</th><th>Original</th><th>Simulated</th></tr>"
        + rows
        + "</table>"
    )
