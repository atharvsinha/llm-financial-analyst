import json
import os
from google import genai
from google.genai import types
from pydantic import BaseModel
from src.models import ExtractedHighlight, ExtractedRisk, ExtractedQuestion, CostLog, HighlightsList

# Shared cost log accumulator
shared_cost_log = CostLog(
    input_tokens=0,
    output_tokens=0,
    usd_cost=0.0,
    model="gemini-2.5-flash"
)

# The new google-genai client automatically picks up GEMINI_API_KEY from environment
client = genai.Client()

def update_cost(prompt_tokens: int, completion_tokens: int, model: str):
    """Update the shared cost log accumulator with new token counts and cost."""
    global shared_cost_log
    shared_cost_log.input_tokens += prompt_tokens
    shared_cost_log.output_tokens += completion_tokens
    
    # Gemini 2.5 Flash pricing: $0.075 per 1M input, $0.30 per 1M output
    cost = (prompt_tokens / 1_000_000) * 0.075 + (completion_tokens / 1_000_000) * 0.30
        
    shared_cost_log.usd_cost += cost
    shared_cost_log.model = model



def extract_highlights(markdown: str) -> list[ExtractedHighlight]:
    """
    Extracts exactly 3 highlights from the provided markdown.
    """
    prompt = f"""
    You are a highly analytical financial analyst. Your task is to extract exactly 3 key highlights from the following press release.
    CRITICAL: Every single highlight MUST contain specific financial figures (e.g., $, %, basis points). Qualitative highlights will be rejected.
    
    For each highlight, you must provide:
    - 'text': The summary text of the highlight containing the numerical data.
    - 'citation_span': A verbatim substring directly from the source text that justifies this highlight and contains the exact numbers.
    - 'metric_label': The label for the primary metric discussed (e.g., 'Revenue', 'Operating Margin').
    
    Context:
    {markdown}
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=HighlightsList
            )
        )
        
        usage = response.usage_metadata
        if usage:
            update_cost(usage.prompt_token_count, usage.candidates_token_count, "gemini-2.5-flash")
            
        data = json.loads(response.text)
        highlights_data = data.get("highlights", [])
        
        highlights = []
        for h in highlights_data:
            highlights.append(ExtractedHighlight(**h))
            
        # Ensure exactly 3 items are returned
        while len(highlights) < 3:
            highlights.append(ExtractedHighlight(
                text="N/A", citation_span="N/A", metric_label="N/A"
            ))
            
        return highlights[:3]
    except Exception as e:
        # Degraded result on failure
        return [
            ExtractedHighlight(text=f"Extraction failed: {str(e)}", citation_span="N/A", metric_label="N/A"),
            ExtractedHighlight(text="N/A", citation_span="N/A", metric_label="N/A"),
            ExtractedHighlight(text="N/A", citation_span="N/A", metric_label="N/A")
        ]

def extract_risk(markdown: str) -> ExtractedRisk:
    """
    Extracts a forward-looking risk from management commentary.
    """
    prompt = f"""
    You are a highly analytical financial analyst. Identify a future-oriented risk from management commentary in the following text.
    Do not use generic legal boilerplate (like Safe Harbor sections).
    
    CRITICAL: You MUST select a citation span that explicitly includes an executive's title (e.g., 'CEO', 'CFO', 'management') or an attribution verb (e.g., 'stated', 'noted', 'expected'). 
    
    You must provide:
    - 'text': The description of the risk.
    - 'citation_span': A verbatim substring directly from the source text containing the attribution.
    
    Context:
    {markdown}
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractedRisk
            )
        )
        usage = response.usage_metadata
        if usage:
            update_cost(usage.prompt_token_count, usage.candidates_token_count, "gemini-2.5-flash")
            
        data = json.loads(response.text)
        return ExtractedRisk(**data)
    except Exception as e:
        return ExtractedRisk(
            text=f"Extraction failed: {str(e)}", 
            citation_span="N/A"
        )

def extract_question(markdown: str, highlights: list[ExtractedHighlight], risk: ExtractedRisk) -> ExtractedQuestion:
    """
    Generates a synthetic analyst question based on extracted highlights and risk.
    """
    highlights_json = json.dumps([h.model_dump() for h in highlights], indent=2)
    risk_json = json.dumps(risk.model_dump(), indent=2)
    
    prompt = f"""
    You are an expert financial analyst preparing for an earnings call. 
    Based on the following press release, highlights, and risk, generate an insightful, synthetic question that probes a vulnerability or specific tension.
    
    You must provide:
    - 'text': The actual question you would ask on the call.
    - 'premise': A single, highly concise sentence containing the exact fact from the source text that prompts this question. Do not write a paragraph.
    
    Extracted Highlights:
    {highlights_json}
    
    Extracted Risk:
    {risk_json}
    
    Source Text:
    {markdown}
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractedQuestion
            )
        )
        usage = response.usage_metadata
        if usage:
            update_cost(usage.prompt_token_count, usage.candidates_token_count, "gemini-2.5-flash")
            
        data = json.loads(response.text)
        return ExtractedQuestion(**data)
    except Exception as e:
        return ExtractedQuestion(
            text=f"Extraction failed: {str(e)}", 
            premise="N/A"
        )
