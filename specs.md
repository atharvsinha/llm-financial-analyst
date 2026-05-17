# Evaluation Specification: e-Analyst Summary System

**Objective**: Define deterministic, automatable checks to evaluate the factuality, structure, analytical depth, and calibration of the generated 1-page analyst summary. 

---

## Evaluation Criteria

### 1. Numerical & Citation Accuracy (Weight: 25%)
- **Measures**: Whether numerical data is correct, properly normalized, and strictly traceable to the cited span (including complex tables).
- **Mechanism**: 
    1. Verify the exact cited string (prose or Markdown table row) exists in the normalized Markdown source document.
    2. Extract all numbers/currencies from the generated highlight using Regex.
    3. Verify these exact numbers exist strictly *within* the verified citation string. 
    4. For tabular citations, ensure the highlight's metric label (e.g., "Revenue") fuzzy-matches the first cell of the cited row.
- **Scoring**: `(Verified Numbers / Total Extracted Numbers) * 10`. A highlight with no numbers or a missing citation scores 0. Final score is the average of all 3 highlights.

### 2. Operational Constraints & Telemetry (Weight: 15%)
- **Measures**: Programmatic adherence to the schema, API cost logging accuracy, and the 1-page length proxy.
- **Mechanism**: 
    1. **Schema Check**: Parse output against a Pydantic validation model (3 highlights, 1 risk, 1 question, confidences).
    2. **Cost Check**: Recalculate expected USD cost via logged input/output tokens and API pricing tier.
    3. **Length Check**: Check the final compiled document word count bounds (250–500 words).
- **Scoring (Additive)**: Start at 0, max 10 points.
    - **+5 pts**: Passes strict Pydantic validation.
    - **+3 pts**: Logged USD cost matches independently computed cost within a 10% tolerance.
    - **+2 pts**: Final document is strictly between 250 and 500 words.

### 3. Forward-Looking Risk (Weight: 20%)
- **Measures**: Ensures the risk is future-oriented, originates from management commentary, and avoids generic legal boilerplate.
- **Mechanism**: 
    1. **Attribution Check (Programmatic)**: Verify the cited span is attributed to management by checking if it meets at least one of these conditions:
        - It is enclosed in explicit quotation marks.
        - The cited sentence (or the paragraph immediately preceding it) contains executive title keywords (e.g., "CEO", "CFO", "management") or attribution verbs (e.g., "stated", "noted", "commented").
    2. **Negative Check (Programmatic)**: Assert the cited span does *not* exist under standard legal boilerplate headers (e.g., "Safe Harbor", "About Forward-Looking Statements").
    3. **Classification Check (LLM Judge)**: Pass the extracted risk to a lightweight judge (`gpt-4o-mini`) with a strict prompt: "Return True if describing a future uncertainty/risk. Return False if describing past performance or generic facts."
- **Scoring**: 
    - **10 pts**: Passes programmatic attribution/negative checks AND judge returns True.
    - **0 pts**: Fails attribution checks (e.g., pulled from legal boilerplate) OR judge returns False.

### 4. Analyst Question: Depth & Entailment (Weight: 20%)
- **Measures**: Whether the generated question synthesizes the text effectively, does not contradict known facts, and possesses high "tension" for an earnings call.
- **Mechanism**:
    1. **Entailment Check**: Use a Natural Language Inference (NLI) model or strictly prompted LLM judge to verify the premise of the question is supported entirely by the source text and does not hallucinate external context.
    2. **Tension Scoring**: An LLM-as-a-judge grades the question on a 1–5 scale based on three pillars: *Specificity* (references distinct metrics/products), *Criticality* (probes a vulnerability), and *Non-Obviousness* (goes beyond generic growth questions).
- **Scoring (Multiplicative)**: 
    - `Score = Entailment_Pass (0 or 1) * Tension_Score (1–5) * 2`
    - *Note: If the question's premise contradicts the text or hallucinates data, it fails entailment (0) and receives a final score of 0.*

### 5. Confidence Calibration (Weight: 20%) 
- **Measures**: Verifies the system assigns deterministic confidence scores that accurately reflect the probability of passing the other automated evaluation criteria.
- **Mechanism**: 
    1. **Determinism**: Verify the confidence reasoning relies on system telemetry (e.g., `citation_match = True`, `token_length_pass`, NLI entailment result) rather than an LLM self-evaluation.
    2. **Calibration**: Map the system's assigned confidence score for each section against the actual pass/fail outcomes of the corresponding automated criteria:
        - **Highlights**: Map confidence to Criterion 1 score.
        - **Risk**: Map confidence to Criterion 3 score.
        - **Question**: Map confidence to Criterion 4 score.
    3. **Thresholding**: A high confidence score (e.g., ≥80%) should strongly correlate with a passing score on the corresponding evaluation criterion.
- **Scoring**: 
    - **10 pts**: System generates 3 deterministic scores. Perfect calibration: High system confidence (≥80%) correctly predicts a passing evaluation score, and low confidence correctly predicts a failing score, across all 3 sections.
    - **5 pts**: Deterministic scores are present, but calibration fails in exactly 1 of the 3 sections (e.g., the system assigns 95% confidence to a Risk that scores a 0 in Criterion 3).
    - **0 pts**: Missing independent scores, reasoning relies on LLM self-rating, OR calibration fails in 2 or more sections (systemic miscalibration).

---

## Note: The Hardest Criterion to Score
Criterion 1 (Citation Accuracy) is by far the hardest to score. Mechanically verifying that a quote and a number exist in the source HTML is trivial. The challenge is "contextual drift."
An LLM might claim "Net Profit was $5B" and cite a sentence that says "Expected Market Size is $5B." The numbers match, but the facts don't. Catching these sneaky mismatches without spamming a heavy, expensive judge model on every line is the core challenge of evaluating financial AI.