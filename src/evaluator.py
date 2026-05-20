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
    """All LLM verdicts gathered in a single API call shared by C3 and C4."""
    risk_is_forward_looking: bool = Field(
        description="True if the risk text describes a genuine future uncertainty or headwind — not past performance or generic legal boilerplate."
    )
    risk_has_management_attribution: bool = Field(
        description=(
            "True if the risk or its citation is plausibly attributed to management — either via explicit quotes, "
            "an executive name/title, an attribution verb (stated/noted/expects/commented), OR by being placed in "
            "a section clearly authored by management such as 'Outlook', 'Guidance', or 'Management Commentary'. "
            "Return True even if attribution is implicit but contextually clear."
        )
    )
    premise_is_entailed: bool = Field(
        description=(
            "True ONLY if every specific fact in the question premise (numbers, events, statements) can be directly "
            "verified in the source document above. Return False if ANY fact is hallucinated, approximated, or sourced "
            "from external knowledge not present in the document."
        )
    )
    tension_score: int = Field(
        description=(
            "Rate the analyst question 1–5 (integers only) based on the average of: "
            "Specificity (1–5: references distinct named metrics, products, or figures from the document), "
            "Criticality (1–5: probes a real vulnerability, contradiction, or risk), "
            "Non-Obviousness (1–5: goes beyond generic 'what is your outlook?' questions). "
            "Return the single integer average. A score of 5 means an exceptionally incisive question."
        )
    )


# ---------------------------------------------------------------------------
# Single Combined Judge Call
# ---------------------------------------------------------------------------

def _run_combined_judge(summary: AnalystSummary, markdown: str) -> JudgeResult:
    """
    Fires a single structured Gemini call to evaluate C3 and C4 simultaneously.
    Passes the full source markdown for maximum context.
    """
    risk = summary.risk
    question = summary.question

    prompt = f"""You are a strict financial analyst evaluator reviewing an AI-generated earnings press release summary.

You must evaluate four properties simultaneously and return a structured JSON response.

---
## FULL SOURCE DOCUMENT
{markdown}

---
## EXTRACTED RISK
Risk text: {risk.text}
Citation span (verbatim from source): {risk.citation_span}

---
## ANALYST QUESTION
Question: {question.text}
Premise: {question.premise}

---
## EVALUATION INSTRUCTIONS

**risk_is_forward_looking**
Return True if the risk describes a future-oriented uncertainty, headwind, or challenge. 
Return False if it describes past performance, a completed event, or is pure legal boilerplate.
Example True: "Management expects geopolitical tensions to delay deal closings in Q2."
Example False: "Revenue increased 22% in Q1."

**risk_has_management_attribution**
Return True if the risk is plausibly from management — this includes:
- Explicit executive quotes with attribution verbs (stated, noted, expects, commented, added)
- Content placed in Outlook, Guidance, or Management Commentary sections
- Statements with forward-looking language (expects, anticipates, projects) that originate from company guidance
Return False ONLY if the risk is clearly from a legal Safe Harbor disclaimer or third-party analyst commentary.
When in doubt, return True — management guidance sections frequently use impersonal language.

**premise_is_entailed**
Carefully check: does the source document above contain ALL the specific facts referenced in the question premise?
Return True if every number, event, or claim in the premise is verifiable in the document above.
Return False only if the premise introduces facts, numbers, or conclusions not found anywhere in the document.

**tension_score**
Score the analyst question 1–5 as the integer average of:
- Specificity: Does it name specific metrics, products, or figures from the document?
- Criticality: Does it probe a genuine risk, contradiction, or business vulnerability?
- Non-Obviousness: Is it a question management would find uncomfortable or unexpected?
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=JudgeResult,
            )
        )
        usage = response.usage_metadata
        if usage:
            update_cost(usage.prompt_token_count, usage.candidates_token_count, "gemini-3.1-flash-lite", "Evaluation")
        data = json.loads(response.text)
        return JudgeResult(**data)
    except Exception as e:
        is_quota, retry_secs = _is_quota_error(e)
        if is_quota:
            raise QuotaExhaustedError(
                f"Gemini API quota exhausted during evaluation. Please wait ~{retry_secs}s before retrying."
            ) from e
        # Fallback: conservative defaults so we don't crash the evaluation
        return JudgeResult(
            risk_is_forward_looking=False,
            risk_has_management_attribution=False,
            premise_is_entailed=False,
            tension_score=1
        )


# ---------------------------------------------------------------------------
# Criterion 1 — Numerical & Citation Accuracy (max 10 pts)
# ---------------------------------------------------------------------------

def evaluate_criterion_1(summary: AnalystSummary, markdown: str) -> CriterionResult:
    scores = []
    details = {}

    for i, h in enumerate(summary.highlights, 1):
        span_exists = h.citation_span != "N/A" and h.citation_span in markdown
        text_numbers = set(re.findall(r'\d+(?:\.\d+)?', h.text))
        span_numbers = set(re.findall(r'\d+(?:\.\d+)?', h.citation_span))

        if len(text_numbers) == 0:
            number_accuracy = 1.0
            verified = total = 0
        else:
            verified = len(text_numbers & span_numbers)
            total = len(text_numbers)
            number_accuracy = verified / total if total > 0 else 0.0

        # Tabular Label Fuzzy Matching
        is_tabular = False
        extracted_label = None
        label_fuzzy_score = None
        tabular_label_match = True
        
        if span_exists and '|' in h.citation_span:
            cells = [cell.strip() for cell in h.citation_span.split('|') if cell.strip()]
            if cells:
                is_tabular = True
                extracted_label = cells[0]
                label_fuzzy_score = fuzz.partial_ratio(extracted_label.lower(), h.text.lower())
                if label_fuzzy_score < 60.0:
                    tabular_label_match = False
                    number_accuracy = 0.0  # Penalize for citing the wrong row

        raw = (number_accuracy * 10) if span_exists else 0.0
        scores.append(raw)
        
        highlight_details = {
            "span_exists": span_exists,
            "text_numbers": list(text_numbers),
            "span_numbers": list(span_numbers),
            "verified": verified if text_numbers else "N/A",
            "total": total if text_numbers else "N/A"
        }
        
        if is_tabular:
            highlight_details["tabular"] = {
                "extracted_label": extracted_label,
                "fuzzy_score": round(label_fuzzy_score, 2),
                "match": tabular_label_match
            }
            
        highlight_details["raw_score"] = round(raw, 2)
        details[f"highlight_{i}"] = highlight_details

    avg = sum(scores) / len(scores) if scores else 0.0
    return CriterionResult(
        name="Criterion 1: Numerical & Citation Accuracy",
        weight="25%",
        score=round(avg, 2),
        max_score=10.0,
        reasoning=(
            f"Average of 3 highlight scores: {[round(s,2) for s in scores]}. "
            "Each highlight scored (verified_numbers / total_numbers) * 10 if citation span exists in source, else 0."
        ),
        details=details
    )


# ---------------------------------------------------------------------------
# Criterion 2 — Operational Constraints & Telemetry (max 10 pts)
# ---------------------------------------------------------------------------

def evaluate_criterion_2(summary: AnalystSummary, markdown: str, rendered_report: str) -> CriterionResult:
    score = 0
    details = {}

    # +5 pts: schema check
    schema_pass = (
        len(summary.highlights) == 3
        and summary.risk is not None
        and summary.question is not None
        and summary.cost_log is not None
    )
    if schema_pass:
        score += 5
    details["schema_pass"] = schema_pass

    # +3 pts: cost re-verification within 10% tolerance
    cl = summary.cost_log
    expected_cost = (cl.input_tokens / 1_000_000) * 0.25 + (cl.output_tokens / 1_000_000) * 1.50
    cost_delta_pct = abs(cl.usd_cost - expected_cost) / expected_cost if expected_cost > 0 else 1.0
    cost_pass = cost_delta_pct <= 0.10
    if cost_pass:
        score += 3
    details["cost_check"] = {
        "logged_cost": cl.usd_cost,
        "recomputed_cost": round(expected_cost, 6),
        "delta_pct": round(cost_delta_pct * 100, 2),
        "pass": cost_pass
    }

    # +2 pts: word count 250–500
    word_count = len(rendered_report.split())
    length_pass = 250 <= word_count <= 500
    if length_pass:
        score += 2
    details["length_check"] = {
        "word_count": word_count,
        "pass": length_pass
    }

    return CriterionResult(
        name="Criterion 2: Operational Constraints & Telemetry",
        weight="15%",
        score=float(score),
        max_score=10.0,
        reasoning=(
            f"Additive scoring: schema (+5), cost verification (+3), word count (+2). "
            f"Schema={schema_pass}, cost delta={details['cost_check']['delta_pct']}%, words={word_count}."
        ),
        details=details
    )


# ---------------------------------------------------------------------------
# Criterion 3 — Forward-Looking Risk (max 10 pts)
# ---------------------------------------------------------------------------

def evaluate_criterion_3(summary: AnalystSummary, judge: JudgeResult) -> CriterionResult:
    risk = summary.risk
    reasoning_data = {}
    try:
        reasoning_data = json.loads(risk.confidence_reasoning)
    except Exception:
        pass

    not_boilerplate = reasoning_data.get("not_boilerplate", True)

    # Regex-based attribution from confidence.py
    regex_attribution = reasoning_data.get("attribution_pass", False)

    # LLM attribution is a richer check (full context, implicit attribution)
    llm_attribution = judge.risk_has_management_attribution
    llm_forward_looking = judge.risk_is_forward_looking

    # Combined attribution: pass if EITHER regex OR LLM confirms it
    combined_attribution = regex_attribution or llm_attribution

    if combined_attribution and not_boilerplate and llm_forward_looking:
        score = 10.0
        verdict = "Full credit: programmatic + LLM checks pass."
    elif llm_forward_looking and not_boilerplate and not combined_attribution:
        score = 5.0
        verdict = "Partial credit: LLM confirms genuine forward-looking risk but attribution is implicit."
    else:
        score = 0.0
        verdict = "No credit: risk is not forward-looking or is boilerplate."

    return CriterionResult(
        name="Criterion 3: Forward-Looking Risk",
        weight="20%",
        score=score,
        max_score=10.0,
        reasoning=(
            f"{verdict} regex_attribution={regex_attribution}, llm_attribution={llm_attribution}, "
            f"not_boilerplate={not_boilerplate}, llm_forward_looking={llm_forward_looking}."
        ),
        details={
            "regex_attribution_pass": regex_attribution,
            "llm_attribution_pass": llm_attribution,
            "combined_attribution": combined_attribution,
            "not_boilerplate": not_boilerplate,
            "llm_forward_looking": llm_forward_looking,
            "verdict": verdict
        }
    )


# ---------------------------------------------------------------------------
# Criterion 4 — Analyst Question: Depth & Entailment (max 10 pts)
# ---------------------------------------------------------------------------

def evaluate_criterion_4(judge: JudgeResult) -> CriterionResult:
    entailment_pass = judge.premise_is_entailed
    tension_score = max(1, min(5, judge.tension_score))  # clamp to 1–5
    final_score = float(int(entailment_pass) * tension_score * 2)

    return CriterionResult(
        name="Criterion 4: Analyst Question Depth & Entailment",
        weight="20%",
        score=min(final_score, 10.0),
        max_score=10.0,
        reasoning=(
            f"Score = Entailment({int(entailment_pass)}) × Tension({tension_score}) × 2 = {final_score}. "
        ),
        details={
            "entailment_pass": entailment_pass,
            "tension_score": tension_score,
            "multiplicative_score": final_score
        }
    )


# ---------------------------------------------------------------------------
# Criterion 5 — Confidence Calibration (max 10 pts)
# ---------------------------------------------------------------------------

def evaluate_criterion_5(
    summary: AnalystSummary,
    c1_score: float,
    c3_score: float,
    c4_score: float
) -> CriterionResult:
    details = {}
    miscalibrations = 0

    def _is_deterministic(reasoning_str: str) -> bool:
        try:
            parsed = json.loads(reasoning_str)
            return isinstance(parsed, dict) and all(isinstance(v, bool) for v in parsed.values())
        except Exception:
            return False

    h_det = all(_is_deterministic(h.confidence_reasoning) for h in summary.highlights)
    r_det = _is_deterministic(summary.risk.confidence_reasoning)
    q_det = _is_deterministic(summary.question.confidence_reasoning)
    all_deterministic = h_det and r_det and q_det
    details["determinism"] = {"highlights": h_det, "risk": r_det, "question": q_det}

    if not all_deterministic:
        return CriterionResult(
            name="Criterion 5: Confidence Calibration",
            weight="20%",
            score=0.0,
            max_score=10.0,
            reasoning="0 pts: Reasoning is not deterministic (not a JSON dict of booleans).",
            details=details
        )

    avg_h_conf = sum(h.confidence for h in summary.highlights) / 3
    h_high_conf = avg_h_conf >= 0.80
    h_pass_score = c1_score >= 7.0
    if h_high_conf != h_pass_score:
        miscalibrations += 1
    details["highlight_calibration"] = {
        "avg_confidence": round(avg_h_conf, 2),
        "high_conf": h_high_conf,
        "c1_score": c1_score,
        "pass_score": h_pass_score,
        "calibrated": h_high_conf == h_pass_score
    }

    r_high_conf = summary.risk.confidence >= 0.80
    r_pass_score = c3_score >= 7.0
    if r_high_conf != r_pass_score:
        miscalibrations += 1
    details["risk_calibration"] = {
        "confidence": summary.risk.confidence,
        "high_conf": r_high_conf,
        "c3_score": c3_score,
        "pass_score": r_pass_score,
        "calibrated": r_high_conf == r_pass_score
    }

    q_high_conf = summary.question.confidence >= 0.80
    q_pass_score = c4_score >= 7.0
    if q_high_conf != q_pass_score:
        miscalibrations += 1
    details["question_calibration"] = {
        "confidence": summary.question.confidence,
        "high_conf": q_high_conf,
        "c4_score": c4_score,
        "pass_score": q_pass_score,
        "calibrated": q_high_conf == q_pass_score
    }

    if miscalibrations == 0:
        score = 10.0
        verdict = "Perfect calibration across all 3 sections."
    elif miscalibrations == 1:
        score = 5.0
        verdict = "Calibration fails in exactly 1 section."
    else:
        score = 0.0
        verdict = f"Systemic miscalibration: {miscalibrations} sections failed."

    return CriterionResult(
        name="Criterion 5: Confidence Calibration",
        weight="20%",
        score=score,
        max_score=10.0,
        reasoning=f"Determinism=True. {verdict} Miscalibrations={miscalibrations}/3.",
        details=details
    )


# ---------------------------------------------------------------------------
# Top-level runner
# ---------------------------------------------------------------------------

def run_evaluation(summary: AnalystSummary, markdown: str, rendered_report: str) -> list[CriterionResult]:
    print("  -> Eval C1: Scoring numerical & citation accuracy...")
    c1 = evaluate_criterion_1(summary, markdown)

    print("  -> Eval C2: Scoring operational constraints & telemetry...")
    c2 = evaluate_criterion_2(summary, markdown, rendered_report)

    print("  -> Eval C3 & C4: Running single combined LLM judge (full context)...")
    judge = _run_combined_judge(summary, markdown)

    print("  -> Eval C3: Scoring forward-looking risk...")
    c3 = evaluate_criterion_3(summary, judge)

    print("  -> Eval C4: Scoring analyst question depth & entailment...")
    c4 = evaluate_criterion_4(judge)

    print("  -> Eval C5: Scoring confidence calibration...")
    c5 = evaluate_criterion_5(summary, c1.score, c3.score, c4.score)

    return [c1, c2, c3, c4, c5]


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

WEIGHTS = [0.25, 0.15, 0.20, 0.20, 0.20]

def render_eval_markdown(results: list[CriterionResult]) -> str:
    lines = ["# Evaluation Report\n"]

    weighted_total = 0.0
    for result, weight in zip(results, WEIGHTS):
        normalized = result.score / result.max_score
        weighted_total += normalized * weight * 100

    lines.append(f"**Overall Weighted Score: {weighted_total:.1f} / 100**\n")
    lines.append("---\n")

    for result in results:
        pct = (result.score / result.max_score) * 100
        badge = "✅" if pct >= 70 else "⚠️" if pct >= 40 else "❌"
        lines.append(f"## {badge} {result.name}")
        lines.append(f"**Weight:** {result.weight} | **Score:** {result.score} / {result.max_score} ({pct:.0f}%)\n")
        lines.append(f"**Reasoning:** {result.reasoning}\n")
        lines.append("**Details:**")
        lines.append("```json")
        lines.append(json.dumps(result.details, indent=2))
        lines.append("```\n")
        lines.append("---\n")

    return "\n".join(lines)
