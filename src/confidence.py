import re
import json
from rapidfuzz import fuzz
from src.models import HeadlineMetric, SentimentTakeaway, FinancialRisk, AnalystQuestion

def calculate_headline_confidence(markdown: str, metric: HeadlineMetric) -> HeadlineMetric:
    """
    Computes deterministic F-GVI checks for headline financial figures with strict None guards.
    """
    span_exists = False
    if metric.citation_span and metric.citation_span != "N/A":
        span_exists = metric.citation_span in markdown
    
    actual_numbers = set()
    if metric.actual and metric.actual != "N/A":
        actual_numbers = set(re.findall(r'\d+(?:\.\d+)?', metric.actual))
        
    span_numbers = set()
    if metric.citation_span and metric.citation_span != "N/A":
        span_numbers = set(re.findall(r'\d+(?:\.\d+)?', metric.citation_span))
    
    numbers_match = True
    if actual_numbers:
        numbers_match = actual_numbers.issubset(span_numbers)
        
    tabular_source = False
    if metric.citation_span and metric.citation_span != "N/A":
        tabular_source = "|" in metric.citation_span
    
    passes = sum([span_exists, numbers_match, tabular_source])
    if passes == 3:
        confidence = 0.95
    elif passes == 2:
        confidence = 0.70
    elif span_exists:
        confidence = 0.40
    else:
        confidence = 0.10
        
    reasoning = json.dumps({
        "verbatim_span_found": span_exists,
        "figures_fully_grounded": numbers_match,
        "tabular_format_match": tabular_source
    })
    
    metric.confidence = confidence
    metric.confidence_reasoning = reasoning
    return metric


def calculate_takeaway_confidence(markdown: str, takeaway: SentimentTakeaway) -> SentimentTakeaway:
    """
    Computes checks for Bull/Bear sentiment takeaways with strict None guards.
    """
    span_exists = False
    if takeaway.citation_span and takeaway.citation_span != "N/A":
        span_exists = takeaway.citation_span in markdown
        
    text_len = len(takeaway.text) if takeaway.text else 0
    length_valid = 10 <= text_len <= 250
    
    passes = sum([span_exists, length_valid])
    if passes == 2:
        confidence = 0.90
    elif span_exists:
        confidence = 0.50
    else:
        confidence = 0.10
        
    reasoning = json.dumps({
        "verbatim_span_found": span_exists,
        "metric_length_valid": length_valid
    })
    
    takeaway.confidence = confidence
    takeaway.confidence_reasoning = reasoning
    return takeaway


def calculate_risk_confidence(markdown: str, risk: FinancialRisk) -> FinancialRisk:
    """
    Computes checks for risks with strict None guards.
    """
    span_exists = False
    idx = -1
    if risk.citation_span and risk.citation_span != "N/A":
        idx = markdown.find(risk.citation_span)
        span_exists = idx != -1
        
    not_boilerplate = True
    if idx != -1:
        before_text = markdown[max(0, idx - 500):idx].lower()
        if "safe harbor" in before_text or "forward-looking statements" in before_text:
            not_boilerplate = False
            
    category_matches = False
    text_lower = risk.text.lower() if risk.text else ""
    cat_lower = risk.category.lower() if risk.category else ""
    risk_citation = risk.citation_span.lower() if risk.citation_span else ""
    
    if "macro" in cat_lower:
        category_matches = any(w in text_lower or w in risk_citation for w in ["inflation", "rate", "fx", "currency", "geopolitical", "market", "demand", "macro"])
    elif "operation" in cat_lower:
        category_matches = any(w in text_lower or w in risk_citation for w in ["supply", "chain", "labor", "cost", "operating", "facility", "headcount", "ops", "logistics"])
    elif "financ" in cat_lower:
        category_matches = any(w in text_lower or w in risk_citation for w in ["debt", "margin", "liquidity", "expense", "interest", "capital", "cash", "credit"])
    else:
        category_matches = True
        
    passes = sum([span_exists, not_boilerplate, category_matches])
    if passes == 3:
        confidence = 0.92
    elif passes == 2:
        confidence = 0.65
    elif span_exists:
        confidence = 0.35
    else:
        confidence = 0.10
        
    reasoning = json.dumps({
        "verbatim_span_found": span_exists,
        "legal_boilerplate_avoided": not_boilerplate,
        "category_context_validated": category_matches
    })
    
    risk.confidence = confidence
    risk.confidence_reasoning = reasoning
    return risk


def calculate_question_confidence(markdown: str, question: AnalystQuestion, headline: object) -> AnalystQuestion:
    """
    Computes checks for probing questions with strict None guards.
    """
    premise_grounded = False
    if question.premise and question.premise != "N/A":
        score = fuzz.partial_ratio(question.premise.lower(), markdown.lower())
        premise_grounded = score > 75
        
    metric_found = False
    q_lower = question.text.lower() if question.text else ""
    if "%" in q_lower or any(c.isdigit() for c in q_lower):
        metric_found = True
        
    passes = sum([premise_grounded, metric_found])
    if passes == 2:
        confidence = 0.90
    elif premise_grounded:
        confidence = 0.50
    else:
        confidence = 0.15
        
    reasoning = json.dumps({
        "premise_grounded_in_text": premise_grounded,
        "financial_metric_referenced": metric_found
    })
    
    question.confidence = confidence
    question.confidence_reasoning = reasoning
    return question
