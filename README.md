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
- **HTML & PDF Parsing**: The original specification strictly mentioned HTML parsing. However, because a significant portion of quarterly financial reports and earnings releases are exclusively distributed as PDF documents, native PDF parsing support (via `PyMuPDF`) was successfully added to the pipeline. HTML relies on `BeautifulSoup` and `markdownify`.
- **Model Selection (Divergence from Spec)**: While the original specification mandated using `gpt-4o-mini` for the secondary judge pipeline and specific NLI models, this implementation transitioned the entire stack (both extraction and evaluation) to `gemini-2.5-flash`. This leverages its structured output capabilities, native token counting, generous usage tier, and keeps the architecture unified.

## Evaluation Difficulty
- **C1 vs C4**: The original evaluation specification identified **Criterion 1 (Numerical & Citation Accuracy)** as the hardest to grade due to "contextual drift." Indeed, ensuring robust text parsing (stripping invisible HTML characters, normalizing spacing, and handling deep tabular structures via fuzzy-matching) was the most difficult *engineering* challenge. However, after successfully hardening the programmatic logic for C1, **Criterion 4 (Analyst Question Depth & Entailment)** has definitively emerged as the most difficult criteria to grade reliably. Scoring the "tension" of an analyst's question (e.g., whether it probes a true vulnerability versus being a softball question) is highly subjective and incredibly difficult to calibrate probabilistically for an LLM judge.

## Future Improvements (With More Time)
- **Secondary LLM Judge Pipeline**: Build a separate, highly-calibrated LLM evaluation pipeline strictly graded on checking entailment and relevance tension, functioning entirely separate from the core extraction logic.
- **Request Caching**: Implement local request caching for the HTML fetcher and LLM inference to save time and reduce API costs during iterative testing and development.
- **Advanced Table Parsing**: Integrate dedicated semantic table parsing tools to better handle the deep financial data arrays typical of earnings releases.
- **Robust Error Recovery**: Add retry mechanisms with exponential backoff for the LLM API calls and dynamic prompt degradation if structured extraction fails initially.

## AI Tools Used
- **Google Deepmind's Antigravity**: Used as the primary AI pair-programmer for iterative architectural design, code generation, refactoring the extraction pipeline for deterministic validation, and seamlessly transitioning the stack to the new Google GenAI SDK.
