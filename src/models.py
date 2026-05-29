from typing import List, Optional
from pydantic import BaseModel, Field

class SegmentPerformance(BaseModel):
    name: str = Field(..., description="The name of the business segment or regional unit.")
    revenue: str = Field(..., description="The revenue reported for this segment (with currency/units).")
    growth: str = Field(..., description="The YoY growth rate of this segment (e.g., '12%' or '-5%').")
    citation_span: str = Field(..., description="The exact verbatim citation from the source text justifying this segment's numbers.")

class GuidanceMetric(BaseModel):
    metric: str = Field(..., description="The financial metric guided (e.g., 'Revenue', 'Operating Income', 'EPS').")
    period: str = Field(..., description="The future period guided (e.g., 'Q2 2026' or 'FY 2026').")
    range_low: str = Field(..., description="The lower bound of the guided range (or 'N/A').")
    range_high: str = Field(..., description="The upper bound of the guided range (or 'N/A').")
    range_mid: str = Field(..., description="The midpoint or single-point target guided (or 'N/A').")
    citation_span: str = Field(..., description="The verbatim citation from the source text justifying this guidance.")

class HeadlineMetric(BaseModel):
    actual: str = Field(..., description="The actual reported value.")
    estimate: str = Field("N/A", description="The market consensus estimate (or 'N/A').")
    yoy_growth: str = Field("N/A", description="The YoY growth rate (or 'N/A').")
    beat_miss: str = Field("N/A", description="The beat/miss status: 'Beat', 'Miss', 'In-Line', or 'N/A'.")
    citation_span: str = Field(..., description="The exact verbatim citation from the source text.")
    confidence: float = Field(0.0, description="Deterministic confidence score.")
    confidence_reasoning: str = Field("", description="Programmatic validation reasoning.")

class SentimentTakeaway(BaseModel):
    text: str = Field(..., description="The analysis text.")
    citation_span: str = Field(..., description="The verbatim citation from the source text.")
    confidence: float = Field(0.0, description="Deterministic confidence score.")
    confidence_reasoning: str = Field("", description="Programmatic validation reasoning.")

class FinancialRisk(BaseModel):
    category: str = Field(..., description="Category of risk: 'Macroeconomic', 'Operational', or 'Financial'.")
    text: str = Field(..., description="Description of the risk/headwind.")
    citation_span: str = Field(..., description="The verbatim citation from the source text.")
    confidence: float = Field(0.0, description="Deterministic confidence score.")
    confidence_reasoning: str = Field("", description="Programmatic validation reasoning.")

class AnalystQuestion(BaseModel):
    text: str = Field(..., description="The sharp probing question.")
    premise: str = Field(..., description="The single sentence factual premise from the text.")
    tension: str = Field(..., description="Brief explanation of the core analytical tension.")
    confidence: float = Field(0.0, description="Deterministic confidence score.")
    confidence_reasoning: str = Field("", description="Programmatic validation reasoning.")

class HeadlineFinancials(BaseModel):
    ticker: str = Field(..., description="The company ticker symbol.")
    company_name: str = Field(..., description="The full company name.")
    period: str = Field(..., description="The reporting period (e.g., 'Q1 2026').")
    release_date: str = Field("N/A", description="The press release date (or 'N/A').")
    revenue: HeadlineMetric = Field(..., description="Revenue performance metrics.")
    eps: HeadlineMetric = Field(..., description="Earnings Per Share metrics.")
    operating_margin: HeadlineMetric = Field(..., description="Operating Margin metrics.")
    net_income: HeadlineMetric = Field(..., description="Net Income metrics.")

class CostLog(BaseModel):
    input_tokens: int = Field(0, description="Total input tokens.")
    output_tokens: int = Field(0, description="Total output tokens.")
    usd_cost: float = Field(0.0, description="Total USD cost.")
    model: str = Field("", description="The model name.")
    calls: list[dict] = Field(default_factory=list, description="List of LLM calls.")

class ExtractedHeadlineFinancials(BaseModel):
    ticker: str = Field(..., description="The company ticker symbol.")
    company_name: str = Field(..., description="The full company name.")
    period: str = Field(..., description="The reporting period (e.g., 'Q1 2026').")
    release_date: str = Field("N/A", description="The press release date (or 'N/A').")
    revenue: HeadlineMetric = Field(..., description="Revenue metrics.")
    eps: HeadlineMetric = Field(..., description="EPS metrics.")
    operating_margin: HeadlineMetric = Field(..., description="Operating Margin metrics.")
    net_income: HeadlineMetric = Field(..., description="Net Income metrics.")

class FullExtractionResult(BaseModel):
    headline: ExtractedHeadlineFinancials = Field(..., description="Headline financials.")
    segments: List[SegmentPerformance] = Field(..., description="Segment breakdowns (up to 5 items).")
    guidance: List[GuidanceMetric] = Field(..., description="Guidance matrix.")
    bull_takeaways: List[SentimentTakeaway] = Field(..., description="Exactly 3 key bullish takeaways.")
    bear_takeaways: List[SentimentTakeaway] = Field(..., description="Exactly 3 key bearish takeaways.")
    risks: List[FinancialRisk] = Field(..., description="Up to 3 categorized risks.")
    questions: List[AnalystQuestion] = Field(..., description="Exactly 2 earnings call probing questions.")

class AnalystSummary(BaseModel):
    ticker: str = Field(..., description="Company ticker.")
    company_name: str = Field(..., description="Company name.")
    period: str = Field(..., description="Reporting period.")
    headline: ExtractedHeadlineFinancials = Field(..., description="Headline financials (with confidences).")
    segments: List[SegmentPerformance] = Field(..., description="Segment performance details (with confidences).")
    guidance: List[GuidanceMetric] = Field(..., description="Guidance matrix (with confidences).")
    bull_takeaways: List[SentimentTakeaway] = Field(..., description="Bull takeaways (with confidences).")
    bear_takeaways: List[SentimentTakeaway] = Field(..., description="Bear takeaways (with confidences).")
    risks: List[FinancialRisk] = Field(..., description="Categorized risks (with confidences).")
    questions: List[AnalystQuestion] = Field(..., description="Probing questions (with confidences).")
    cost_log: CostLog = Field(..., description="Execution telemetry & costs.")
