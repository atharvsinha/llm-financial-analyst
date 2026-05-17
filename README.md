# e-Analyst Summary System

An automated financial analyst summary system that extracts structured financial highlights, forward-looking risks, and synthetic analyst questions from corporate earnings press releases.

## Getting Started

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Create a `.env` file in the root directory and add your Gemini API key:
   ```env
   GEMINI_API_KEY="your-gemini-key-here"
   ```

3. **Run the Pipeline**:
   Provide the URL of an earnings press release to run the full extraction and scoring pipeline:
   ```bash
   python main.py --url <URL>
   ```

### Output Files
- `final_summary.md`: A clean, 1-page markdown report containing the highlights, risk, question, and confidence metrics.
- `analyst_summary_log.txt`: The raw JSON output mapping to Pydantic objects.
- `cost_log.txt`: A persistent telemetry tracker appending token usage and USD cost across runs.

## Trade-offs Made
- **Programmatic Confidence Scoring**: Rather than using a more advanced NLI (Natural Language Inference) model for entailment/tension checks, I opted for heuristic-based scoring to strictly adhere to the requirement for deterministic confidence metrics. This includes using `rapidfuzz` for fuzzy string matching, regex for number verification, and distance-based heuristics for boilerplate detection. It is deterministic but naturally less nuanced than a dedicated semantic model.
- **HTML Parsing**: Used `BeautifulSoup` and `markdownify` for straightforward DOM extraction. While fast and effective for most standard press release layouts, it may occasionally struggle to perfectly format highly complex nested financial tables.
- **Model Selection**: Migrated the extraction pipeline to `gemini-2.5-flash` via the `google-genai` SDK to leverage its structured output capabilities, native token counting, and generous usage tier.

## Future Improvements (With More Time)
- **Secondary LLM Judge Pipeline**: Build a separate, highly-calibrated LLM evaluation pipeline strictly graded on checking entailment and relevance tension, functioning entirely separate from the core extraction logic.
- **Request Caching**: Implement local request caching for the HTML fetcher and LLM inference to save time and reduce API costs during iterative testing and development.
- **Advanced Table Parsing**: Integrate dedicated semantic table parsing tools to better handle the deep financial data arrays typical of earnings releases.
- **Robust Error Recovery**: Add retry mechanisms with exponential backoff for the LLM API calls and dynamic prompt degradation if structured extraction fails initially.

## AI Tools Used
- **Google Deepmind's Antigravity**: Used as the primary AI pair-programmer for iterative architectural design, code generation, refactoring the extraction pipeline for deterministic validation, and seamlessly transitioning the stack to the new Google GenAI SDK.
