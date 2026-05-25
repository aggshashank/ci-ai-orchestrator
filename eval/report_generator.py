"""
report_generator.py — generates a self-contained HTML eval report.
"""
import json
from pathlib import Path
from datetime import datetime, timezone


def _score_color(score: float) -> str:
    if score >= 0.85: return "#1a7a6e"
    if score >= 0.70: return "#c07000"
    return "#c00000"


def _score_bar(score: float, width: int = 120) -> str:
    pct = int(score * 100)
    fill = int(score * width)
    color = _score_color(score)
    return (
        f'<div style="display:inline-flex;align-items:center;gap:8px">'
        f'<div style="width:{width}px;height:8px;background:#e8e8e8;border-radius:4px;overflow:hidden">'
        f'<div style="width:{fill}px;height:100%;background:{color};border-radius:4px"></div></div>'
        f'<span style="font-size:13px;color:{color};font-weight:500">{pct}%</span>'
        f'</div>'
    )


def generate_report(pipeline, output_path: Path):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    reg_html = ""
    if pipeline.regressions:
        rows = ""
        for r in pipeline.regressions:
            sev_color = "#c00000" if r["severity"] == "HIGH" else "#c07000"
            rows += (
                f"<tr>"
                f"<td>{r['agent']}</td>"
                f"<td>{r['dimension']}</td>"
                f"<td style='color:{sev_color};font-weight:500'>{r['severity']}</td>"
                f"<td>{r['baseline']:.3f}</td>"
                f"<td>{r['current']:.3f}</td>"
                f"<td style='color:{sev_color}'>-{r['drop']:.3f}</td>"
                f"</tr>"
            )
        reg_html = f"""
        <h2 style="color:#c00000">⚠ Regressions ({len(pipeline.regressions)})</h2>
        <table><thead><tr>
          <th>Agent</th><th>Dimension</th><th>Severity</th>
          <th>Baseline</th><th>Current</th><th>Drop</th>
        </tr></thead><tbody>{rows}</tbody></table>"""
    else:
        reg_html = '<p style="color:#1a7a6e;font-weight:500">✓ No regressions vs baseline</p>'

    agent_rows = ""
    for agent, scores in pipeline.agent_scores.items():
        agent_rows += (
            f"<tr>"
            f"<td style='font-weight:500'>{agent}</td>"
            f"<td>{_score_bar(scores['correctness'])}</td>"
            f"<td>{_score_bar(scores['format'])}</td>"
            f"<td>{_score_bar(scores['latency'])}</td>"
            f"<td>{_score_bar(scores['cost'])}</td>"
            f"<td>{_score_bar(scores['weighted'])}</td>"
            f"<td style='color:{'#1a7a6e' if scores['pass_rate']>=0.8 else '#c00000'}"
            f";font-weight:500'>{int(scores['pass_rate']*100)}%</td>"
            f"</tr>"
        )

    pipeline_color = _score_color(pipeline.pipeline_score)

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Agent Eval Report — {pipeline.run_id}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     max-width:960px;margin:40px auto;padding:0 24px;color:#1a1a1a;line-height:1.6}}
h1{{font-size:22px;font-weight:600;margin:0 0 4px}}
h2{{font-size:17px;font-weight:600;margin:32px 0 12px;border-bottom:1px solid #e4e4e4;padding-bottom:8px}}
.meta{{color:#666;font-size:13px;margin-bottom:32px}}
.pipeline-score{{display:inline-block;font-size:48px;font-weight:700;
                 color:{pipeline_color};margin:8px 0}}
.summary-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:24px 0}}
.card{{background:#f8f8f8;border:1px solid #e4e4e4;border-radius:8px;
       padding:16px 20px}}
.card-label{{font-size:12px;color:#666;margin:0 0 4px;text-transform:uppercase;
             letter-spacing:.04em}}
.card-value{{font-size:24px;font-weight:600;margin:0}}
table{{width:100%;border-collapse:collapse;font-size:14px;margin:16px 0}}
th{{background:#f0f0f0;padding:10px 14px;text-align:left;font-weight:600;
    font-size:13px;border-bottom:2px solid #ddd}}
td{{padding:10px 14px;border-bottom:1px solid #eeeeee;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:500}}
</style></head><body>

<h1>Agent Evaluation Report</h1>
<p class="meta">Run ID: {pipeline.run_id} &nbsp;·&nbsp; Generated: {now}</p>

<div class="pipeline-score">{int(pipeline.pipeline_score*100)}%</div>
<p style="color:#666;margin:0 0 24px">Overall pipeline score</p>

<div class="summary-grid">
  <div class="card">
    <p class="card-label">Test cases</p>
    <p class="card-value">{pipeline.total_cases}</p>
  </div>
  <div class="card">
    <p class="card-label">Passed</p>
    <p class="card-value" style="color:{'#1a7a6e' if pipeline.passed_cases==pipeline.total_cases else '#c00000'}">
      {pipeline.passed_cases}/{pipeline.total_cases}</p>
  </div>
  <div class="card">
    <p class="card-label">Regressions</p>
    <p class="card-value" style="color:{'#c00000' if pipeline.regressions else '#1a7a6e'}">
      {len(pipeline.regressions)}</p>
  </div>
</div>

<h2>Dimension Scores (pipeline average)</h2>
<div class="summary-grid">
  {"".join(f'<div class="card"><p class="card-label">{dim.title()}</p>'
            f'<div style="margin-top:8px">{_score_bar(score, 140)}</div></div>'
            for dim, score in pipeline.dimension_scores.items())}
</div>

<h2>Agent Scores</h2>
<table>
  <thead><tr>
    <th>Agent</th><th>Correctness</th><th>Format</th>
    <th>Latency</th><th>Cost</th><th>Weighted</th><th>Pass rate</th>
  </tr></thead>
  <tbody>{agent_rows}</tbody>
</table>

<h2>Regression Analysis</h2>
{reg_html}

<h2>Eval Configuration</h2>
<table>
  <thead><tr><th>Agent</th><th>Correctness floor</th><th>Format floor</th>
  <th>Latency ceiling</th><th>Token ceiling</th></tr></thead>
  <tbody>"""

    from eval_config import AGENT_THRESHOLDS
    for agent, t in AGENT_THRESHOLDS.items():
        html += (
            f"<tr><td>{agent}</td><td>{t.correctness_floor}</td>"
            f"<td>{t.format_floor}</td><td>{t.latency_ceiling_s}s</td>"
            f"<td>{t.token_ceiling or 'N/A'}</td></tr>"
        )

    html += "</tbody></table></body></html>"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
