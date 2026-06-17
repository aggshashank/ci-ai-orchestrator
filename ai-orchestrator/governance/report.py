"""
Fairness HTML report generator.

Produces a self-contained HTML page with:
  - Summary table (approval rates by segment)
  - Violation highlights (red)
  - 4/5ths ratio bar chart (inline CSS)
"""
from __future__ import annotations

from governance.disparate_impact import FairnessAnalysisResult


_VIOLATION_STYLE = "background:#fee2e2;color:#991b1b;font-weight:bold;"
_OK_STYLE        = "background:#d1fae5;color:#065f46;"


def _bar(ratio: float, threshold: float) -> str:
    pct   = round(ratio * 100)
    color = "#ef4444" if ratio < threshold else "#22c55e"
    return (
        f'<div style="width:{min(pct,100)}%;background:{color};height:16px;'
        f'border-radius:4px;"></div>'
    )


def generate(result: FairnessAnalysisResult) -> str:
    rows_html = ""
    for seg in sorted(result.segments, key=lambda s: s.ratio_to_best):
        style = _VIOLATION_STYLE if seg.violation else _OK_STYLE
        rows_html += f"""
        <tr style="{style}">
          <td>{seg.segment_name}</td>
          <td>{seg.segment_value}</td>
          <td>{seg.total_decisions}</td>
          <td>{seg.approvals}</td>
          <td>{seg.approval_rate:.1%}</td>
          <td>{_bar(seg.ratio_to_best, result.threshold)}
              {seg.ratio_to_best:.3f}</td>
          <td>{'VIOLATION' if seg.violation else 'OK'}</td>
        </tr>"""

    viol_summary = ""
    if result.has_violations:
        viol_items = "".join(
            f"<li>{v.segment_name}={v.segment_value}: ratio {v.ratio_to_best:.3f} (threshold {result.threshold})</li>"
            for v in result.violations
        )
        viol_summary = f"""
        <div style="background:#fef2f2;border:1px solid #fca5a5;padding:12px;border-radius:6px;margin-bottom:16px;">
          <b>⚠ {len(result.violations)} Disparate Impact Violation(s) Detected</b>
          <ul>{viol_items}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Fairness Report — {result.computed_at[:10]}</title>
  <style>
    body {{ font-family: sans-serif; max-width: 960px; margin: 32px auto; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 8px 12px; text-align: left; }}
    th {{ background: #f9fafb; }}
  </style>
</head>
<body>
  <h1>Fairness Monitoring Report</h1>
  <p>Period: last <b>{result.period_days} days</b>
     &nbsp;|&nbsp; Total decisions: <b>{result.total_decisions}</b>
     &nbsp;|&nbsp; Overall approval rate: <b>{result.overall_approval_rate:.1%}</b>
     &nbsp;|&nbsp; 4/5ths threshold: <b>{result.threshold}</b>
     &nbsp;|&nbsp; Generated: {result.computed_at}</p>
  {viol_summary}
  <table>
    <thead>
      <tr>
        <th>Segment</th><th>Value</th><th>Total</th><th>Approvals</th>
        <th>Approval Rate</th><th>4/5ths Ratio</th><th>Status</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</body>
</html>"""
