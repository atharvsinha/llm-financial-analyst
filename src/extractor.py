import re
import json
import os
from google import genai
from google.genai import types
from pydantic import BaseModel
from src.models import ExtractedHighlight, ExtractedRisk, ExtractedQuestion, CostLog, FullExtractionResult


class QuotaExhaustedError(Exception):
    """Raised when the Gemini API returns a 429 RESOURCE_EXHAUSTED error."""
    pass


# Shared cost log accumulator
shared_cost_log = CostLog(
    input_tokens=0,
    output_tokens=0,
    usd_cost=0.0,
    model="gemini-2.5-flash"
)

client = genai.Client()

def update_cost(prompt_tokens: int, completion_tokens: int, model: str, phase: str = "Unknown"):
    """Update the shared cost log accumulator with new token counts and cost."""
    global shared_cost_log
    shared_cost_log.input_tokens += prompt_tokens
    shared_cost_log.output_tokens += completion_tokens
    
    # Gemini 2.5 Flash pricing: $0.30 per 1M input, $2.50 per 1M output
    cost = (prompt_tokens / 1_000_000) * 0.30 + (completion_tokens / 1_000_000) * 2.50
        
    shared_cost_log.usd_cost += cost
    shared_cost_log.model = model
    
    shared_cost_log.calls.append({
        "phase": phase,
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "usd_cost": cost,
        "model": model
    })
    
    # Write to cost log immediately per LLM call
    try:
        with open("cost_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{phase}] Model: {model} | Input: {prompt_tokens} | Output: {completion_tokens} | Cost: ${cost:.5f}\n")
    except Exception:
        pass


def _is_quota_error(e: Exception) -> tuple[bool, int]:
    """Returns (is_quota_error, retry_after_seconds)."""
    msg = str(e)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg or "UNAVAILABLE" in msg:
        retry_match = re.search(r'retry.{0,15}(\d+)s', msg, re.IGNORECASE)
        retry_secs = int(retry_match.group(1)) if retry_match else 60
        return True, retry_secs
    return False, 0


def extract_all(markdown: str) -> FullExtractionResult:
    """
    Extracts highlights, risk, and question in a single structured call.
    """
    prompt = f"""
    You are a highly analytical financial analyst reviewing an earnings press release. Your task is to extract three things: exactly 3 key highlights, ONE forward-looking risk clearly attributable to company management, and ONE sharp, probing question for an earnings call.

    1. HIGHLIGHTS RULES:
    - You must extract exactly 3 key financial highlights.
    - Every highlight MUST contain specific financial figures (e.g., $, %, basis points).
    - Provide a concise summary text, the verbatim citation_span from the source that justifies it, and the metric_label (e.g., 'Revenue').

    2. RISK RULES:
    - Find ONE future-oriented risk that is clearly attributable to company management.
    - The citation_span MUST be verbatim text from the source document.
    - PREFER spans from CEO/CFO quotes, Forward guidance/Outlook sections, or sentences containing words like: expects, anticipates, projects, intends, believes, remains cautious.
    - DO NOT select spans from Safe Harbor disclaimers or legal boilerplate.
    - Provide a 1-2 sentence description text and the verbatim citation_span.

    3. QUESTION RULES:
    - Generate one sharp, probing question that creates tension between the company's strong performance and the extracted risk.
    - The question must reference at least one specific metric from your extracted highlights.
    - The 'premise' field must be a SINGLE sentence that states one specific, verifiable fact directly from the source document (a direct quote or close paraphrase).

    Source document:
    {markdown}
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FullExtractionResult
            )
        )
        
        usage = response.usage_metadata
        if usage:
            update_cost(usage.prompt_token_count, usage.candidates_token_count, "gemini-2.5-flash", "Extraction")
            
        data = json.loads(response.text)
        
        # Ensure exactly 3 highlights
        highlights_data = data.get("highlights", [])
        highlights = [ExtractedHighlight(**h) for h in highlights_data]
        while len(highlights) < 3:
            highlights.append(ExtractedHighlight(
                text="N/A", citation_span="N/A", metric_label="N/A"
            ))
        highlights = highlights[:3]
        
        risk_data = data.get("risk", {})
        question_data = data.get("question", {})
        
        # Add N/A defaults if fields are missing due to partial outputs
        if not risk_data:
             risk_data = {"text": "N/A", "citation_span": "N/A"}
        if not question_data:
             question_data = {"text": "N/A", "premise": "N/A"}

        risk = ExtractedRisk(**risk_data)
        question = ExtractedQuestion(**question_data)
        
        return FullExtractionResult(highlights=highlights, risk=risk, question=question)

    except Exception as e:
        is_quota, retry_secs = _is_quota_error(e)
        if is_quota:
            raise QuotaExhaustedError(
                f"Gemini API quota exhausted. Please wait ~{retry_secs}s before retrying."
            ) from e
        # Degraded result
        return FullExtractionResult(
            highlights=[
                ExtractedHighlight(text="N/A", citation_span="N/A", metric_label="N/A"),
                ExtractedHighlight(text="N/A", citation_span="N/A", metric_label="N/A"),
                ExtractedHighlight(text="N/A", citation_span="N/A", metric_label="N/A")
            ],
            risk=ExtractedRisk(text="N/A", citation_span="N/A"),
            question=ExtractedQuestion(text="N/A", premise="N/A")
        )
