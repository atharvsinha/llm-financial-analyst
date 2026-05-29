from src.models import AnalystSummary

def render_markdown(summary: AnalystSummary) -> str:
    """
    Compiles the comprehensive, institutional-grade AnalystSummary into a premium Markdown report.
    """
    lines = []
    lines.append(f"# Financial Intelligence Report: {summary.company_name} ({summary.ticker})")
    lines.append(f"**Period:** {summary.period} | **Release Date:** {summary.headline.release_date}\n")
    lines.append("---\n")
    
    # 1. Headline Statistics Table
    lines.append("## Headline Performance")
    lines.append("| Metric | Actual Value | consensus Estimate | YoY Growth | Status | Veracity (F-GVI) |")
    lines.append("|---|---|---|---|---|---|")
    
    h = summary.headline
    metrics = [
        ("Revenue", h.revenue),
        ("EPS", h.eps),
        ("Operating Margin", h.operating_margin),
        ("Net Income", h.net_income)
    ]
    
    for name, m in metrics:
        lines.append(f"| {name} | **{m.actual}** | {m.estimate} | {m.yoy_growth} | **{m.beat_miss}** | {m.confidence * 100:.0f}% |")
    lines.append("\n")
    
    # 2. Segment Performance
    lines.append("## Segment & Regional Breakdown")
    for s in summary.segments:
        lines.append(f"### 🧩 {s.name}")
        lines.append(f"- **Revenue:** {s.revenue} | **YoY Growth:** {s.growth}")
        lines.append(f"> Verbatim Citation: *\"{s.citation_span}\"*\n")
        
    # 3. Guidance Matrix
    lines.append("## Future Guidance Matrix")
    if summary.guidance:
        lines.append("| Metric | Guided Period | Low Target | High Target | Midpoint/Target |")
        lines.append("|---|---|---|---|---|")
        for g in summary.guidance:
            lines.append(f"| {g.metric} | {g.period} | {g.range_low} | {g.range_high} | **{g.range_mid}** |")
    else:
        lines.append("*No future guidance ranges guided in this release.*")
    lines.append("\n")
    
    # 4. Bull & Bear Takeaways
    lines.append("## Bull vs. Bear Debate Synthesis")
    lines.append("### 🐂 Bull Takeaways")
    for idx, b in enumerate(summary.bull_takeaways, 1):
        lines.append(f"{idx}. **Takeaway:** {b.text} (F-GVI: {b.confidence*100:.0f}%)")
        lines.append(f"   > *\"{b.citation_span}\"*\n")
        
    lines.append("### 🐻 Bear Takeaways")
    for idx, b in enumerate(summary.bear_takeaways, 1):
        lines.append(f"{idx}. **Takeaway:** {b.text} (F-GVI: {b.confidence*100:.0f}%)")
        lines.append(f"   > *\"{b.citation_span}\"*\n")
        
    # 5. Categorized Risks
    lines.append("## Core Headwinds & Strategic Risks")
    for r in summary.risks:
        lines.append(f"### ⚠️ {r.category} Risk (F-GVI: {r.confidence*100:.0f}%)")
        lines.append(f"{r.text}")
        lines.append(f"> Citation: *\"{r.citation_span}\"*\n")
        
    # 6. Earnings Call Playbook
    lines.append("## Earnings Call Playbook: Probing Questions")
    for idx, q in enumerate(summary.questions, 1):
        lines.append(f"### 🎙️ Q{idx}: Probing Question (F-GVI: {q.confidence*100:.0f}%)")
        lines.append(f"- **Factual Premise:** {q.premise}")
        lines.append(f"- **Earnings Question:** **{q.text}**")
        lines.append(f"- **Analytical Tension:** *{q.tension}*\n")
        
    # 7. Telemetry & Cost
    lines.append("## Telemetry & Cost\n")
    lines.append("| Phase | Input Tokens | Output Tokens | USD Cost | Model |")
    lines.append("|---|---|---|---|---|")
    
    if summary.cost_log.calls:
        for call in summary.cost_log.calls:
            lines.append(f"| {call['phase']} | {call['input_tokens']} | {call['output_tokens']} | ${call['usd_cost']:.5f} | {call['model']} |")
        lines.append(f"| **Total** | **{summary.cost_log.input_tokens}** | **{summary.cost_log.output_tokens}** | **${summary.cost_log.usd_cost:.5f}** | **{summary.cost_log.model}** |")
    else:
        lines.append(f"| Total | {summary.cost_log.input_tokens} | {summary.cost_log.output_tokens} | ${summary.cost_log.usd_cost:.5f} | {summary.cost_log.model} |")
    
    return "\n".join(lines)
