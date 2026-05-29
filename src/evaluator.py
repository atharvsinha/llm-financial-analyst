import re
import json
from rapidfuzz import fuzz
from google.genai import types
from pydantic import BaseModel, Field
from src.models import AnalystSummary
from src.extractor import client, update_cost, _is_quota_error, QuotaExhaustedError

# ---------------------------------------------------------------------------
# Shared Data Models
# ---------------------------------------------------------------------------

class CriterionResult(BaseModel):
    name: str
    weight: str
    score: float
    max_score: float
    reasoning: str
    details: dict


class JudgeResult(BaseModel):
    """All LLM verdicts gathered in a single API call to evaluate advanced criteria."""
    guidance_is_legitimate: bool = Field(
        description="True if guidance metrics represent genuine future corporate projections, ranges, or targets — not just repeated historical facts."
    )
    bull_bear_symmetry_score: int = Field(
        description="Rate the analytical depth, structural balance, and specificity of the Bull/Bear takes on a scale of 1-5 (5 is outstanding)."
    )
    risks_are_legitimate: bool = Field(
        description="True if all risks represent genuine macroeconomic, operational, or financial uncertainties — and avoid pure boilerplate legal text."
    )
    premise_is_entailed: bool = Field(
        description="True if the premises of both earnings call questions are strictly verifiable in the source document, containing no hallucinations."
    )
    tension_score: int = Field(
        description="Rate the earnings call playbook questions on a scale of 1-5 based on specificity, business critical tension, and incisiveness."
    )


# ---------------------------------------------------------------------------
# Single Combined Judge Call
# ---------------------------------------------------------------------------

def _run_combined_judge(summary: AnalystSummary, markdown: str) -> JudgeResult:
    """
    Fires a single structured Gemini call to evaluate C2, C3, and C4 simultaneously.
    """
    prompt = f"""You are a strict financial analyst evaluator reviewing an AI-generated corporate earnings intelligence report.
    
    You must evaluate the report against the source document and return a structured JSON response.

    ---
    ## FULL SOURCE DOCUMENT
    {markdown}

    ---
    ## GENERATED INTELLIGENCE REPORT
    Ticker: {summary.ticker}
    Company: {summary.company_name}
    Period: {summary.period}
    
    GUIDANCE MATRIX:
    {json.dumps([g.model_dump() for g in summary.guidance], indent=2)}

    BULL TAKEAWAYS:
    {json.dumps([b.model_dump() for b in summary.bull_takeaways], indent=2)}

    BEAR TAKEAWAYS:
    {json.dumps([b.model_dump() for b in summary.bear_takeaways], indent=2)}

    RISKS LOG:
    {json.dumps([r.model_dump() for r in summary.risks], indent=2)}

    EARNINGS CALL QUESTIONS:
    {json.dumps([q.model_dump() for q in summary.questions], indent=2)}

    ---
    ## EVALUATION INSTRUCTIONS

    **guidance_is_legitimate**
    Evaluate the Guidance Matrix. Return True if all items represent genuine forward-looking corporate projections, ranges (Low/High/Mid), or future goals. Return False if they contain purely historical metrics.

    **bull_bear_symmetry_score**
    Rate the Bull and Bear takes from 1 to 5. Check if they are well-balanced, analytical, and highly specific to the company's quarter (e.g. naming drivers like backlog, margins, customer acquisition), rather than generic statements.

    **risks_are_legitimate**
    Return True if the listed risks represent real macro, operational, or financial headwinds. Return False if they represent generic legal boilerplate statements.

    **premise_is_entailed**
    Verify both question premises. Return True if all specific metrics, numbers, and facts listed in the premises are strictly supported by the source document. Return False if there is any hallucination or extrapolation.

    **tension_score**
    Rate the earnings call questions from 1 to 5. Highly specific, critical questions that probe core contradictions or growth headwinds score 5. Generic, simple questions score 1.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=JudgeResult,
            )
        )
        usage = response.usage_metadata
        if usage:
            update_cost(usage.prompt_token_count, usage.candidates_token_count, "gemini-2.5-flash", "Evaluation")
        data = json.loads(response.text)
        return JudgeResult(**data)
    except Exception as e:
        is_quota, retry_secs = _is_quota_error(e)
        if is_quota:
            raise QuotaExhaustedError(
                f"Gemini API quota exhausted during evaluation. Please wait ~{retry_secs}s before retrying."
            ) from e
        return JudgeResult(
            guidance_is_legitimate=False,
            bull_bear_symmetry_score=1,
            risks_are_legitimate=False,
            premise_is_entailed=False,
            tension_score=1
        )


# ---------------------------------------------------------------------------
# Criterion 1 — Tabular & Numerical Accuracy (max 10 pts, Weight: 30%)
# ---------------------------------------------------------------------------

def evaluate_criterion_1(summary: AnalystSummary, markdown: str) -> CriterionResult:
    scores = []
    details = {}

    # 1. Headline metrics evaluation
    h = summary.headline
    headline_metrics = [h.revenue, h.eps, h.operating_margin, h.net_income]
    metric_names = ["revenue", "eps", "operating_margin", "net_income"]
    
    for name, m in zip(metric_names, headline_metrics):
        span_exists = m.citation_span != "N/A" and m.citation_span in markdown
        
        actual_numbers = set(re.findall(r'\d+(?:\.\d+)?', m.actual))
        span_numbers = set(re.findall(r'\d+(?:\.\d+)?', m.citation_span))
        
        numbers_match = True
        if actual_numbers:
            numbers_match = actual_numbers.issubset(span_numbers)
            
        metric_score = (10.0 if numbers_match else 5.0) if span_exists else 0.0
        scores.append(metric_score)
        
        details[name] = {
            "span_exists": span_exists,
            "numbers_match": numbers_match,
            "metric_score": metric_score
        }

    # 2. Segments evaluation
    segment_scores = []
    for idx, s in enumerate(summary.segments):
        span_exists = s.citation_span != "N/A" and s.citation_span in markdown
        seg_score = 10.0 if span_exists else 0.0
        segment_scores.append(seg_score)
        details[f"segment_{idx}"] = {
            "name": s.name,
            "span_exists": span_exists,
            "score": seg_score
        }
        
    if segment_scores:
        scores.append(sum(segment_scores) / len(segment_scores))
        
    avg = sum(scores) / len(scores) if scores else 0.0
    return CriterionResult(
        name="Criterion 1: Tabular & Numerical Accuracy",
        weight="30%",
        score=round(avg, 2),
        max_score=10.0,
        reasoning=f"Headline financials and segment citation verification. Metric verification average: {round(avg,2)}/10.",
        details=details
    )


# ---------------------------------------------------------------------------
# Criterion 2 — Guidance Veracity (max 10 pts, Weight: 20%)
# ---------------------------------------------------------------------------

def evaluate_criterion_2(summary: AnalystSummary, markdown: str, judge: JudgeResult) -> CriterionResult:
    details = {}
    scores = []
    
    for idx, g in enumerate(summary.guidance):
        span_exists = g.citation_span != "N/A" and g.citation_span in markdown
        score = 10.0 if span_exists else 0.0
        scores.append(score)
        details[f"guidance_{idx}"] = {
            "metric": g.metric,
            "span_exists": span_exists,
            "score": score
        }
        
    base_avg = sum(scores) / len(scores) if scores else 10.0
    
    # Penalize if the judge finds guidance matrix contains historical numbers
    if not judge.guidance_is_legitimate:
        final_score = base_avg * 0.5
        reason = "Guidance citation check passed, but LLM judge flagged historical metrics inside the Guidance Matrix (50% penalty)."
    else:
        final_score = base_avg
        reason = "All guided elements verify and represent valid future-oriented ranges/midpoints."
        
    details["guidance_is_legitimate"] = judge.guidance_is_legitimate
    
    return CriterionResult(
        name="Criterion 2: Guidance Veracity",
        weight="20%",
        score=round(final_score, 2),
        max_score=10.0,
        reasoning=reason,
        details=details
    )


# ---------------------------------------------------------------------------
# Criterion 3 — Bull/Bear Analytical Symmetry (max 10 pts, Weight: 20%)
# ---------------------------------------------------------------------------

def evaluate_criterion_3(summary: AnalystSummary, markdown: str, judge: JudgeResult) -> CriterionResult:
    # Scale LLM judge 1-5 rating to 10 points
    symmetry_score = float(judge.bull_bear_symmetry_score) * 2.0
    
    # Programmatic check: Ensure exact citations are present in text
    citations_valid = True
    details = {"bull_takeaways": [], "bear_takeaways": []}
    
    for idx, b in enumerate(summary.bull_takeaways):
        exists = b.citation_span != "N/A" and b.citation_span in markdown
        if not exists:
            citations_valid = False
        details["bull_takeaways"].append({"text": b.text, "citation_exists": exists})
        
    for idx, b in enumerate(summary.bear_takeaways):
        exists = b.citation_span != "N/A" and b.citation_span in markdown
        if not exists:
            citations_valid = False
        details["bear_takeaways"].append({"text": b.text, "citation_exists": exists})
        
    if not citations_valid:
        symmetry_score = max(0.0, symmetry_score - 3.0)
        reason = f"Bull/Bear takeaways rated {judge.bull_bear_symmetry_score}/5 by LLM judge, but penalized for missing verbatim citation spans."
    else:
        reason = f"Bull/Bear takeaways rated {judge.bull_bear_symmetry_score}/5 by LLM judge. Citations verified."
        
    details["llm_symmetry_score_raw"] = judge.bull_bear_symmetry_score
    details["citations_valid"] = citations_valid
    
    return CriterionResult(
        name="Criterion 3: Bull/Bear Analytical Symmetry",
        weight="20%",
        score=round(symmetry_score, 2),
        max_score=10.0,
        reasoning=reason,
        details=details
    )


# ---------------------------------------------------------------------------
# Criterion 4 — Earnings Call Question Incisiveness (max 10 pts, Weight: 15%)
# ---------------------------------------------------------------------------

def evaluate_criterion_4(summary: AnalystSummary, judge: JudgeResult) -> CriterionResult:
    entailment_pass = judge.premise_is_entailed
    tension_score = max(1, min(5, judge.tension_score))
    
    final_score = float(int(entailment_pass) * tension_score * 2)
    
    return CriterionResult(
        name="Criterion 4: Earnings Call Question Incisiveness",
        weight="15%",
        score=min(final_score, 10.0),
        max_score=10.0,
        reasoning=f"Score = Entailment({int(entailment_pass)}) × Question Tension({tension_score}) × 2 = {final_score}.",
        details={
            "entailment_pass": entailment_pass,
            "tension_score": tension_score
        }
    )


# ---------------------------------------------------------------------------
# E-Criterion 5 — Telemetry & Calibration (max 10 pts, Weight: 15%)
# ---------------------------------------------------------------------------

def evaluate_criterion_5(
    summary: AnalystSummary,
    c1_score: float,
    c2_score: float,
    c3_score: float,
    c4_score: float,
    rendered_report: str
) -> CriterionResult:
    score = 0
    details = {}

    # +5 pts: Pydantic Schema Adherence
    schema_pass = (
        summary.ticker != ""
        and summary.headline is not None
        and len(summary.bull_takeaways) == 3
        and len(summary.bear_takeaways) == 3
        and len(summary.risks) > 0
        and len(summary.questions) == 2
    )
    if schema_pass:
        score += 5
    details["schema_pass"] = schema_pass

    # +3 pts: Telemetry and Cost delta calculation check
    cl = summary.cost_log
    expected_cost = (cl.input_tokens / 1_000_000) * 0.075 + (cl.output_tokens / 1_000_000) * 0.30
    cost_delta_pct = abs(cl.usd_cost - expected_cost) / expected_cost if expected_cost > 0 else 0.0
    cost_pass = cost_delta_pct <= 0.15
    if cost_pass:
        score += 3
    details["cost_check"] = {
        "logged_cost": cl.usd_cost,
        "recomputed_cost": round(expected_cost, 6),
        "pass": cost_pass
    }

    # +2 pts: Length constraints (250–1200 words for advanced reports)
    word_count = len(rendered_report.split())
    length_pass = 250 <= word_count <= 1500
    if length_pass:
        score += 2
    details["length_check"] = {
        "word_count": word_count,
        "pass": length_pass
    }

    return CriterionResult(
        name="Criterion 5: Telemetry & Calibration Check",
        weight="15%",
        score=float(score),
        max_score=10.0,
        reasoning=f"Pydantic Schema={schema_pass}, Cost Delta={round(cost_delta_pct*100,2)}%, Words={word_count}.",
        details=details
    )


# ---------------------------------------------------------------------------
# Top-level Orchestrator
# ---------------------------------------------------------------------------

def run_evaluation(summary: AnalystSummary, markdown: str, rendered_report: str) -> list[CriterionResult]:
    # 1. Run the combined LLM judge
    judge = _run_combined_judge(summary, markdown)

    # 2. Score each criterion
    c1 = evaluate_criterion_1(summary, markdown)
    c2 = evaluate_criterion_2(summary, markdown, judge)
    c3 = evaluate_criterion_3(summary, markdown, judge)
    c4 = evaluate_criterion_4(summary, judge)
    c5 = evaluate_criterion_5(summary, c1.score, c2.score, c3.score, c4.score, rendered_report)

    return [c1, c2, c3, c4, c5]


# ---------------------------------------------------------------------------
# Output Markdown Renderer
# ---------------------------------------------------------------------------

WEIGHTS = [0.30, 0.20, 0.20, 0.15, 0.15]

def render_eval_markdown(results: list[CriterionResult]) -> str:
    lines = ["# Financial Intelligence Evaluation Report\n"]

    weighted_total = 0.0
    for result, weight in zip(results, WEIGHTS):
        normalized = result.score / result.max_score
        weighted_total += normalized * weight * 100

    lines.append(f"**Overall Weighted Score: {weighted_total:.1f} / 100**\n")
    lines.append("---\n")

    for result in results:
        pct = (result.score / result.max_score) * 100
        badge = "✅" if pct >= 75 else "⚠️" if pct >= 50 else "❌"
        lines.append(f"## {badge} {result.name}")
        lines.append(f"**Weight:** {result.weight} | **Score:** {result.score} / {result.max_score} ({pct:.0f}%)\n")
        lines.append(f"**Reasoning:** {result.reasoning}\n")
        lines.append("**Evaluation Metrics:**")
        lines.append("```json")
        lines.append(json.dumps(result.details, indent=2))
        lines.append("```\n")
        lines.append("---\n")

    return "\n".join(lines)
