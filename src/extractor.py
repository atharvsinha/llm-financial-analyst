import re
import json
import os
import logging
from google import genai
from google.genai import types
from src.models import FullExtractionResult, CostLog

logger = logging.getLogger(__name__)

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
    
    # Gemini 2.5 Flash pricing: $0.075 per 1M input, $0.30 per 1M output
    # Let's count costs using these standard optimized rates
    cost = (prompt_tokens / 1_000_000) * 0.075 + (completion_tokens / 1_000_000) * 0.30
        
    shared_cost_log.usd_cost += cost
    shared_cost_log.model = model
    
    shared_cost_log.calls.append({
        "phase": phase,
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "usd_cost": cost,
        "model": model
    })
    
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
    Extracts comprehensive financial data in a single structured cache-optimized call.
    """
    prompt = f"""
    You are a highly analytical, institutional-grade financial analyst reviewing an earnings press release. Your task is to extract and analyze the contents of the press release and construct a highly structured Financial Intelligence Report in JSON format matching the schema exactly.

    Ensure you strictly follow these extraction guidelines:
    1. HEADLINE FINANCIALS (Revenue, EPS, Operating Margin, Net Income):
       - Extract 'actual' reported value.
       - Extract market consensus 'estimate' (if mentioned in text, otherwise search or default to 'N/A').
       - YoY Growth (e.g. '12%' or '-4%').
       - Beat/Miss status: 'Beat', 'Miss', 'In-Line', or 'N/A' based on estimates vs actuals.
       - Every headline metric MUST have a verbatim 'citation_span' from the source release.

    2. SEGMENT PERFORMANCE:
       - Identify up to 5 major product lines, business units, or regional units (e.g. 'AWS', 'Google Cloud', 'YouTube Ads') with their reported revenue, YoY growth, and verbatim citation_span.

    3. GUIDANCE MATRIX:
       - Identify all future guidance targets provided by management for the next quarter or full fiscal year.
       - Extract the metric name, guided period, range_low, range_high, range_mid, and verbatim citation_span.

    4. BULL & BEAR DEBATE SYNTHESIS:
       - Extract exactly 3 key bullish takeaways (reasons the stock might go up, e.g. strong backlog, margin expansion, product adoption) and exactly 3 key bearish takeaways (reasons the stock might go down, e.g. decelerating growth, customer concentration). Each must have a verbatim citation_span.

    5. CATEGORIZED RISKS:
       - Extract up to 3 distinct future-oriented risks/headwinds.
       - Classify them as 'Macroeconomic', 'Operational', or 'Financial'.
       - Each risk must have a verbatim citation_span.

    6. EARNINGS CALL PLAYBOOK:
       - Generate exactly 2 sharp probing questions for management during the earnings call.
       - Each question must have a 'premise' (single factual sentence from the text) and explain the 'tension' (the core business contradiction or potential headwind being probed).

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
        return FullExtractionResult(**data)

    except Exception as e:
        is_quota, retry_secs = _is_quota_error(e)
        if is_quota:
            raise QuotaExhaustedError(
                f"Gemini API quota exhausted. Please wait ~{retry_secs}s before retrying."
            ) from e
        logger.warning(f"Error during extraction: {e}")
        # Return fallback empty state
        raise e
