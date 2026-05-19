import sys
import logging
from src.fetcher import fetch_press_release, html_to_markdown
from src.extractor import extract_all, shared_cost_log, QuotaExhaustedError
from src.confidence import calculate_highlight_confidence, calculate_risk_confidence, calculate_question_confidence
from src.models import AnalystSummary, Highlight, Risk, AnalystQuestion
from src.evaluator import run_evaluation, render_eval_markdown
from src.fetcher import pdf_to_markdown

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
        # Fetch and normalize
        content, content_type = fetch_press_release(url)
        print("  -> Step 2: Normalizing source content to clean Markdown...")
        if 'pdf' in content_type:
            markdown = pdf_to_markdown(content)
        else:
            # Assume HTML
            html = content.decode('utf-8', errors='ignore')
            markdown = html_to_markdown(html)
    except Exception as e:
        logger.warning(f"Failed to fetch or parse URL: {e}")
        # Continue with empty markdown to return degraded result
        
    try:
        # Extraction
        print("  -> Step 3: Extracting highlights, risk, and question via a single LLM call...")
        extraction_result = extract_all(markdown)
        extracted_highlights = extraction_result.highlights
        extracted_risk = extraction_result.risk
        extracted_question = extraction_result.question

        # Confidence Scoring
        print("  -> Step 4: Programmatically calculating deterministic confidence metrics...")
        final_highlights = [calculate_highlight_confidence(markdown, h) for h in extracted_highlights]
        final_risk = calculate_risk_confidence(markdown, extracted_risk)
        final_question = calculate_question_confidence(markdown, extracted_question, extracted_highlights)

    except QuotaExhaustedError as e:
        print(f"\n[!] API Quota Exhausted: {e}")
        print("[!] No output files were written. Please wait and try again.\n")
        sys.exit(1)
    except Exception as e:
        logger.warning(f"Error during extraction or scoring: {e}")
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
    

    # Render 1-pager Markdown
    markdown_report = ""
    try:
        from src.renderer import render_markdown
        markdown_report = render_markdown(summary)
        with open("final_summary.md", "w", encoding="utf-8") as f:
            f.write(markdown_report)
    except Exception as e:
        logger.warning(f"Failed to render or write markdown report: {e}")

    # Run evaluation across all 5 criteria and save eval.md
    print("  -> Step 5: Running full evaluation across all 5 criteria...")
    try:
        eval_results = run_evaluation(summary, markdown, markdown_report)
        eval_md = render_eval_markdown(eval_results)
        with open("eval.md", "w", encoding="utf-8") as f:
            f.write(eval_md)
            
        from src.renderer import render_markdown
        markdown_report_final = render_markdown(summary)
        with open("final_summary.md", "w", encoding="utf-8") as f:
            f.write(markdown_report_final)
            
    except Exception as e:
        logger.warning(f"Failed to run or write evaluation: {e}")

    return summary
