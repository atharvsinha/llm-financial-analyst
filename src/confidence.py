import re
import json
from rapidfuzz import fuzz
from src.models import ExtractedHighlight, ExtractedRisk, ExtractedQuestion, Highlight, Risk, AnalystQuestion

def calculate_highlight_confidence(markdown: str, extracted: ExtractedHighlight) -> Highlight:
    # 1. Does citation_span exist as a substring?
    span_exists = False
    if extracted.citation_span and extracted.citation_span != "N/A":
        span_exists = extracted.citation_span in markdown
    
    # 2. Do all numbers in the highlight text appear within the citation_span?
    text_numbers = set(re.findall(r'\d+(?:\.\d+)?', extracted.text))
    span_numbers = set(re.findall(r'\d+(?:\.\d+)?', extracted.citation_span))
    
    if len(text_numbers) == 0:
        numbers_match = True
    else:
        numbers_match = text_numbers.issubset(span_numbers)
        
    # 3. Does metric_label fuzzy-match the start of the cited line?
    metric_match = False
    if extracted.metric_label and extracted.metric_label != "N/A" and extracted.citation_span:
        score = fuzz.partial_ratio(extracted.metric_label.lower(), extracted.citation_span.lower()[:50])
        metric_match = score > 80
        
    passes = sum([span_exists, numbers_match, metric_match])
    if passes == 3:
        confidence = 0.90
    elif passes == 2:
        confidence = 0.65
    else:
        confidence = 0.30
        
    reasoning = json.dumps({
        "span_exists": span_exists,
        "numbers_match": numbers_match,
        "metric_match": metric_match
    })
    
    return Highlight(
        text=extracted.text,
        citation_span=extracted.citation_span,
        metric_label=extracted.metric_label,
        confidence=confidence,
        confidence_reasoning=reasoning
    )

def calculate_risk_confidence(markdown: str, extracted: ExtractedRisk) -> Risk:
    # Attribution check — three layers
    span_lower = extracted.citation_span.lower()

    # Layer A: explicit quotes in the citation span
    has_quote = ('"' in extracted.citation_span or '\u201c' in extracted.citation_span
                 or '\u201d' in extracted.citation_span or "'" in extracted.citation_span)

    # Layer B: scan citation span AND nearby text (400 chars) for executive keywords
    idx = markdown.find(extracted.citation_span)
    nearby_text = ""
    if idx != -1:
        start = max(0, idx - 400)
        end = min(len(markdown), idx + len(extracted.citation_span) + 400)
        nearby_text = markdown[start:end].lower()

    executive_keywords = ["ceo", "cfo", "president", "management", "officer", "executive",
                          "chief executive", "chief financial"]

    # Layer C: forward-looking guidance verbs — covers both direct attribution AND guidance language
    attribution_verbs = [
        "stated", "said", "noted", "added", "commented", "explained", "mentioned",
        "expects", "expected", "anticipates", "anticipated", "projects", "projected",
        "intends", "believes", "estimates", "forecasts", "targets", "guides", "guided"
    ]

    # Guidance section headers are implicit management attribution
    guidance_headers = ["outlook", "guidance", "q2 2026", "full year 2026", "fy 2026",
                        "management commentary", "business outlook"]

    # Search both the span and surrounding context
    search_text = span_lower + " " + nearby_text
    has_executive = any(kw in search_text for kw in executive_keywords)
    has_verb = any(verb in search_text for verb in attribution_verbs)
    has_guidance_context = any(h in search_text for h in guidance_headers)

    has_attribution = has_executive or has_verb or has_guidance_context
    attribution_pass = has_quote or has_attribution

    # 2. Is the span not under a boilerplate header?
    not_boilerplate = True
    if idx != -1:
        before_text = markdown[max(0, idx - 500):idx].lower()
        if "safe harbor" in before_text or "forward-looking statements" in before_text:
            not_boilerplate = False

    passes = sum([attribution_pass, not_boilerplate])
    if passes == 2:
        confidence = 0.85
    elif passes == 1:
        confidence = 0.40
    else:
        confidence = 0.10

    reasoning = json.dumps({
        "attribution_pass": attribution_pass,
        "not_boilerplate": not_boilerplate
    })

    return Risk(
        text=extracted.text,
        citation_span=extracted.citation_span,
        confidence=confidence,
        confidence_reasoning=reasoning
    )

def calculate_question_confidence(markdown: str, extracted: ExtractedQuestion, highlights: list[ExtractedHighlight]) -> AnalystQuestion:
    # 1. Does the question's premise appear (as a paraphrase or substring) in the markdown?
    premise_pass = False
    if extracted.premise and extracted.premise != "N/A":
        score = fuzz.partial_ratio(extracted.premise.lower(), markdown.lower())
        premise_pass = score > 75
        
    # 2. Does the question reference at least one specific metric from the highlights?
    metric_pass = False
    question_lower = extracted.text.lower()
    for h in highlights:
        if h.metric_label and h.metric_label != "N/A" and h.metric_label.lower() in question_lower:
            metric_pass = True
            break
            
    passes = sum([premise_pass, metric_pass])
    if passes == 2:
        confidence = 0.88
    elif passes == 1:
        confidence = 0.50
    else:
        confidence = 0.15
        
    reasoning = json.dumps({
        "premise_pass": premise_pass,
        "metric_pass": metric_pass
    })
    
    return AnalystQuestion(
        text=extracted.text,
        premise=extracted.premise,
        confidence=confidence,
        confidence_reasoning=reasoning
    )
