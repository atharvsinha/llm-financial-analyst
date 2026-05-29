import asyncio
import logging
import json
from typing import AsyncGenerator
from src.fetcher import fetch_press_release, html_to_markdown, pdf_to_markdown
from src.extractor import extract_all, shared_cost_log, QuotaExhaustedError
from src.confidence import (
    calculate_headline_confidence,
    calculate_takeaway_confidence,
    calculate_risk_confidence,
    calculate_question_confidence
)
from src.models import AnalystSummary, CostLog
from src.evaluator import run_evaluation, render_eval_markdown

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def analyze_stream(url: str, side: str = "left") -> AsyncGenerator[str, None]:
    """
    Asynchronous generator that runs the complete corporate financial intelligence pipeline
    with top-level crash-resistance guardrails to prevent infinite token loops.
    """
    def send_event(event_type: str, data: dict):
        return f"data: {json.dumps({'event': event_type, 'side': side, **data})}\n\n"
        
    try:
        yield send_event("progress", {"message": "Fetching earnings release content..."})
        
        # 1. Fetch and Parse
        try:
            content, content_type = await asyncio.to_thread(fetch_press_release, url)
            yield send_event("progress", {"message": "Normalizing raw content to clean Markdown..."})
            
            if 'pdf' in content_type:
                markdown = await asyncio.to_thread(pdf_to_markdown, content)
            else:
                html = content.decode('utf-8', errors='ignore')
                markdown = await asyncio.to_thread(html_to_markdown, html)
        except Exception as e:
            logger.warning(f"Failed fetching or parsing: {e}")
            yield send_event("error", {"message": f"Failed fetching or parsing source URL: {str(e)}"})
            return
            
        if not markdown or not markdown.strip():
            yield send_event("error", {"message": "Extracted document content is empty."})
            return

        # 2. Extract Data via structured LLM
        yield send_event("progress", {"message": "Extracting corporate financials, segments, guidance, and risks..."})
        try:
            extraction = await asyncio.to_thread(extract_all, markdown)
        except QuotaExhaustedError as e:
            yield send_event("error", {"message": f"API Limit Reached: {str(e)}"})
            return
        except Exception as e:
            logger.warning(f"Extraction failed: {e}")
            yield send_event("error", {"message": f"Extraction failed: {str(e)}"})
            return

        # 3. Calibrate Confidence Scores (F-GVI Grounding index) with try-except safety
        yield send_event("progress", {"message": "Calibrating Financial Grounding & Veracity Index (F-GVI)..."})
        try:
            # Headline Metric scoring
            calculate_headline_confidence(markdown, extraction.headline.revenue)
            calculate_headline_confidence(markdown, extraction.headline.eps)
            calculate_headline_confidence(markdown, extraction.headline.operating_margin)
            calculate_headline_confidence(markdown, extraction.headline.net_income)
            
            # Bull/Bear Takeaways scoring
            for b in extraction.bull_takeaways:
                calculate_takeaway_confidence(markdown, b)
            for b in extraction.bear_takeaways:
                calculate_takeaway_confidence(markdown, b)
                
            # Risks scoring
            for r in extraction.risks:
                calculate_risk_confidence(markdown, r)
                
            # Questions scoring
            for q in extraction.questions:
                calculate_question_confidence(markdown, q, extraction.headline)
        except Exception as e:
            logger.error(f"F-GVI Scoring calibration failed: {e}", exc_info=True)
            # Gracefully allow default metrics to pass rather than crashing
            pass
            
        # Assemble preliminary summary
        summary = AnalystSummary(
            ticker=extraction.headline.ticker,
            company_name=extraction.headline.company_name,
            period=extraction.headline.period,
            headline=extraction.headline,
            segments=extraction.segments,
            guidance=extraction.guidance,
            bull_takeaways=extraction.bull_takeaways,
            bear_takeaways=extraction.bear_takeaways,
            risks=extraction.risks,
            questions=extraction.questions,
            cost_log=shared_cost_log
        )
        
        # Stream sections out immediately to showcase live rendering
        yield send_event("headline", {"data": summary.headline.model_dump()})
        yield send_event("segments", {"data": [s.model_dump() for s in summary.segments]})
        yield send_event("guidance", {"data": [g.model_dump() for g in summary.guidance]})
        yield send_event("takeaways", {
            "bull": [b.model_dump() for b in summary.bull_takeaways],
            "bear": [b.model_dump() for b in summary.bear_takeaways]
        })
        yield send_event("risks", {"data": [r.model_dump() for r in summary.risks]})
        yield send_event("questions", {"data": [q.model_dump() for q in summary.questions]})

        # 4. Evaluation Spec Grading
        yield send_event("progress", {"message": "Running 5-point institutional evaluation loop..."})
        try:
            from src.renderer import render_markdown
            report_md = render_markdown(summary)
            
            eval_results = await asyncio.to_thread(run_evaluation, summary, markdown, report_md)
            eval_md = render_eval_markdown(eval_results)
            
            from src.evaluator import WEIGHTS
            weighted_total = 0.0
            for res, weight in zip(eval_results, WEIGHTS):
                weighted_total += (res.score / res.max_score) * weight * 100
                
            yield send_event("evaluation", {
                "score": round(weighted_total, 1),
                "report_md": eval_md,
                "results": [r.model_dump() for r in eval_results]
            })
        except Exception as e:
            logger.warning(f"Evaluation failed: {e}")
            yield send_event("progress", {"message": f"Evaluation degraded: {str(e)}"})
            
        yield send_event("done", {"summary": summary.model_dump()})
        
    except Exception as e:
        logger.error(f"Global pipeline crash in analyze_stream: {e}", exc_info=True)
        yield send_event("error", {"message": f"Critical pipeline failure: {str(e)}"})
