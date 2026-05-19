# e-Analyst Summary System

I built this automated financial analyst system to pull structured financial highlights, forward-looking risks, and tough analyst questions from corporate earnings press releases.

## Getting Started

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Create a `.env` file in the root directory and drop in your Gemini API key:
   ```env
   GEMINI_API_KEY="your-gemini-key-here"
   ```

3. **Run the Pipeline**:
   Just pass the URL of an earnings press release (HTML or PDF) to kick off the pipeline:
   ```bash
   python main.py --url <URL>
   ```

### Output Files
When you run the script, you'll get three output files:
- `final_summary.md`: A clean, 1-page markdown report with the extracted highlights, risk, question, and the telemetry table. Also has the confidence score and reasoning for each extraction.
- `eval.md`: The detailed evaluation report scoring the extraction against the 5 criteria.
- `cost_log.txt`: A persistent log that tracks token usage and USD cost across all your runs.

## Architectural Trade-offs & Decisions

- **Model Selection**: The original specs recommended `gpt-4o-mini` for the pipeline. I decided to use `gemini-2.5-flash` instead as a trade-off. Since OpenAI doesn't offer free API usage and I already had a Gemini subscription, it was a practical choice that let me take advantage of its native token counting and structured outputs while keeping costs down.
- **Programmatic Confidence Scoring**: I could have used a heavy NLI model for entailment checks, but I wanted to keep things snappy and deterministic. I went with heuristic-based scoring—using `rapidfuzz` for table labels, regex for numbers, and distance checks for boilerplate text. It might be less nuanced than a dedicated semantic model, but it's way more predictable.
- **Reducing LLM Overhead**: The original implementation relied on 6 separate LLM calls. I managed to consolidate the architecture down to just 2 calls (one for extraction, one for evaluation), while actually improving the confidence scores across the board!

## Differences from the Original Specs

- **Native PDF Parsing**: The specs only asked for HTML parsing. But as I started testing real-world data, I realized a ton of companies only publish their quarterly reports as PDFs. So, I added `PyMuPDF` to handle PDF ingestion natively alongside the `BeautifulSoup` HTML parser.

## What Was Hard to Evaluate?

- **C1 vs C4**: The original spec flagged **Criterion 1 (Numerical & Citation Accuracy)** as the toughest to grade because of "contextual drift." Honestly, building the engineering logic for C1 (stripping invisible characters, fixing spacing, fuzzy-matching table rows) was not as hard as I had initially thought. Adding checks for contextual drift, and managing table based numerical extraction was slightly time consuming but doable.
- But once that was hardened, **Criterion 4 (Analyst Question Depth)** actually became the hardest to score reliably. Judging the "tension" of a question—whether it actually probes a vulnerability or if it's just a softball—is super subjective and incredibly tricky to calibrate probabilistically with an LLM judge.

## Future Improvements (If I Had More Time)

- **Separate LLM Judge**: I'd love to spin up a fully isolated, highly-calibrated LLM pipeline just for grading entailment and relevance, keeping it completely decoupled from the core logic.
- **Request Caching**: Adding local caching for HTML fetches and LLM responses would save a lot of time and API calls during testing.
- **Advanced Table Parsing**: Earnings releases have gnarly, deep data tables. A dedicated semantic table parser would handle those edge cases much better.
- **Robust Error Recovery**: Adding exponential backoff for API rate limits and dynamic prompt fallbacks if the structured extraction fails on the first try.
- **LLM Model Switching**: Adding a simple CLI argument to switch between different LLM providers.
- **UI**: Adding a simple UI for the analyst to interact with the system.
- **More Criterias**: Adding more criterias for evaluation.

