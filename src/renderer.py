from src.models import AnalystSummary

def render_markdown(summary: AnalystSummary) -> str:
    """
    Renders the structured AnalystSummary into a clean 1-page Markdown report.
    Includes Highlights, Risk, Question, and Cost telemetry.
    """
    lines = []
    lines.append("# Analyst Summary\n")
    
    # Highlights
    lines.append("## Highlights")
    for idx, h in enumerate(summary.highlights, 1):
        lines.append(f"### {idx}. {h.metric_label} (Confidence: {h.confidence * 100:.0f}%)")
        lines.append(f"{h.text}\n")
        lines.append(f"> {h.citation_span}\n")
        
    # Risk
    lines.append("## Primary Risk")
    lines.append(f"**Confidence:** {summary.risk.confidence * 100:.0f}%\n")
    lines.append(f"{summary.risk.text}\n")
    lines.append(f"> {summary.risk.citation_span}\n")
    
    # Question
    lines.append("## Analyst Question")
    lines.append(f"**Confidence:** {summary.question.confidence * 100:.0f}%\n")
    lines.append(f"**Premise:** {summary.question.premise}\n")
    lines.append(f"**Question:** {summary.question.text}\n")
    
    # Cost Log Table
    lines.append("## Telemetry & Cost")
    lines.append("| Input Tokens | Output Tokens | USD Cost | Model |")
    lines.append("|---|---|---|---|")
    lines.append(f"| {summary.cost_log.input_tokens} | {summary.cost_log.output_tokens} | ${summary.cost_log.usd_cost:.5f} | {summary.cost_log.model} |")
    
    return "\n".join(lines)
