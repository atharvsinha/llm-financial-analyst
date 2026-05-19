from typing import List
from pydantic import BaseModel, Field

class ExtractedHighlight(BaseModel):
    text: str = Field(..., description="The highlight text.")
    citation_span: str = Field(..., description="The exact span from the source text used for citation.")
    metric_label: str = Field(..., description="The label for the metric (e.g., 'Revenue').")

class ExtractedRisk(BaseModel):
    text: str = Field(..., description="The forward-looking risk text.")
    citation_span: str = Field(..., description="The exact span from the source text used for citation.")

class ExtractedQuestion(BaseModel):
    text: str = Field(..., description="The analyst question.")
    premise: str = Field(..., description="The premise of the question, supported by source text.")

class FullExtractionResult(BaseModel):
    highlights: List[ExtractedHighlight] = Field(..., description="Exactly 3 extracted highlights.")
    risk: ExtractedRisk = Field(..., description="A forward-looking risk extracted from the text.")
    question: ExtractedQuestion = Field(..., description="An analytical question for an earnings call.")

class Highlight(ExtractedHighlight):
    confidence: float = Field(..., description="Confidence score.")
    confidence_reasoning: str = Field(..., description="Reasoning for the given confidence score.")

class Risk(ExtractedRisk):
    confidence: float = Field(..., description="Confidence score.")
    confidence_reasoning: str = Field(..., description="Reasoning for the given confidence score.")

class AnalystQuestion(ExtractedQuestion):
    confidence: float = Field(..., description="Confidence score.")
    confidence_reasoning: str = Field(..., description="Reasoning for the given confidence score.")

class CostLog(BaseModel):
    input_tokens: int = Field(0, description="Total number of input tokens.")
    output_tokens: int = Field(0, description="Total number of output tokens.")
    usd_cost: float = Field(0.0, description="Total estimated cost in USD.")
    model: str = Field("", description="The model used (e.g., 'gpt-4o').")
    calls: list[dict] = Field(default_factory=list, description="List of individual LLM calls.")

class AnalystSummary(BaseModel):
    highlights: List[Highlight] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly 3 highlights extracted from the text."
    )
    risk: Risk = Field(..., description="A forward-looking risk extracted from the text.")
    question: AnalystQuestion = Field(..., description="An analytical question for an earnings call.")
    cost_log: CostLog = Field(..., description="Telemetry and cost tracking log.")
