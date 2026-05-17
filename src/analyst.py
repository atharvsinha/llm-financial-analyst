import logging
from src.fetcher import fetch_press_release, html_to_markdown
from src.extractor import extract_highlights, extract_risk, extract_question, shared_cost_log
from src.confidence import calculate_highlight_confidence, calculate_risk_confidence, calculate_question_confidence
from src.models import AnalystSummary, Highlight, Risk, AnalystQuestion

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_analysis(url: str) -> AnalystSummary:
    """
    Top-level pipeline function that fetches data, runs LLM extractions,
    computes deterministic confidence scores, and assembles the final AnalystSummary.
    All errors are logged as warnings and the system gracefully degrades.
    """
    markdown = ""
    print("  -> Step 1: Fetching earnings press release HTML content...")
    try:
        # Phase 1: Fetch and normalize
        html = fetch_press_release(url)
        print("  -> Step 2: Normalizing HTML to clean Markdown...")
        markdown = html_to_markdown(html)
    except Exception as e:
        logger.warning(f"Failed to fetch or parse URL: {e}")
        # Continue with empty markdown to return degraded result
        
    try:
        # Phase 3: Extraction
        print("  -> Step 3: Extracting quantitative financial highlights via LLM...")
        extracted_highlights = extract_highlights(markdown)
        
        print("  -> Step 4: Extracting attributed forward-looking risks via LLM...")
        extracted_risk = extract_risk(markdown)
        
        print("  -> Step 5: Generating synthetic analyst call question via LLM...")
        extracted_question = extract_question(markdown, extracted_highlights, extracted_risk)
        
        # Phase 4: Confidence Scoring
        print("  -> Step 6: Programmatically calculating deterministic confidence metrics...")
        final_highlights = [calculate_highlight_confidence(markdown, h) for h in extracted_highlights]
        final_risk = calculate_risk_confidence(markdown, extracted_risk)
        final_question = calculate_question_confidence(markdown, extracted_question, extracted_highlights)
        
    except Exception as e:
        logger.warning(f"Error during extraction or scoring: {e}")
        # Degraded results on catastrophic failure
        final_highlights = [
            Highlight(text="N/A", citation_span="N/A", metric_label="N/A", confidence=0.0, confidence_reasoning="Failed"),
            Highlight(text="N/A", citation_span="N/A", metric_label="N/A", confidence=0.0, confidence_reasoning="Failed"),
            Highlight(text="N/A", citation_span="N/A", metric_label="N/A", confidence=0.0, confidence_reasoning="Failed")
        ]
        final_risk = Risk(text="N/A", citation_span="N/A", confidence=0.0, confidence_reasoning="Failed")
        final_question = AnalystQuestion(text="N/A", premise="N/A", confidence=0.0, confidence_reasoning="Failed")
        
    # Assemble final summary
    summary = AnalystSummary(
        highlights=final_highlights,
        risk=final_risk,
        question=final_question,
        cost_log=shared_cost_log
    )
    
    # 1. Append cost log to persistent cost log file
    try:
        with open("cost_log.txt", "a", encoding="utf-8") as f:
            f.write(f"Model: {summary.cost_log.model} | Input: {summary.cost_log.input_tokens} | Output: {summary.cost_log.output_tokens} | Cost: ${summary.cost_log.usd_cost:.4f}\n")
    except Exception as e:
        logger.warning(f"Failed to append to cost log: {e}")
        
    # 2. Log full JSON summary (original requirement)
    try:
        with open("analyst_summary_log.txt", "w", encoding="utf-8") as f:
            f.write(summary.model_dump_json(indent=2))
    except Exception as e:
        logger.warning(f"Failed to write json summary log: {e}")

    # 3. Render 1-pager Markdown
    try:
        from src.renderer import render_markdown
        markdown_report = render_markdown(summary)
        
        # Word count sanity check (assert 250-500)
        word_count = len(markdown_report.split())
        if not (250 <= word_count <= 500):
            logger.warning(f"Word count sanity check failed: {word_count} words (expected 250-500).")
            
        with open("final_summary.md", "w", encoding="utf-8") as f:
            f.write(markdown_report)
    except Exception as e:
        logger.warning(f"Failed to render or write markdown report: {e}")
        
    return summary
