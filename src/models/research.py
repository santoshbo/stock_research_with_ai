"""Data models for stock research application."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Literal
from enum import Enum
from pydantic import BaseModel, Field


class Recommendation(str, Enum):
    """Investment recommendation type."""
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


class RiskLevel(str, Enum):
    """Risk assessment level."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FinancialYear(BaseModel):
    """Single year financial metrics."""
    year: int = Field(description="Fiscal year")
    sales_revenue: Optional[float] = Field(None, description="Annual sales/revenue in local currency")
    expenses: Optional[float] = Field(None, description="Total expenses")
    operating_profit: Optional[float] = Field(None, description="Operating profit (EBIT)")
    opm: Optional[float] = Field(None, description="Operating profit margin %")
    net_profit: Optional[float] = Field(None, description="Net profit")
    profit_before_tax: Optional[float] = Field(None, description="Profit before tax")
    yoy_revenue_growth: Optional[float] = Field(None, description="Year-over-year revenue growth %")
    
    class Config:
        json_schema_extra = {
            "example": {
                "year": 2024,
                "sales_revenue": 394328000000,
                "expenses": 309000000000,
                "operating_profit": 85328000000,
                "opm": 21.6,
                "net_profit": 79712000000,
                "profit_before_tax": 79712000000,
                "yoy_revenue_growth": 12.5
            }
        }


class StockMetrics(BaseModel):
    """Current stock market metrics."""
    ticker: str = Field(description="Stock ticker symbol")
    company_name: str = Field(description="Company name")
    current_price: float = Field(description="Current stock price")
    currency: str = Field(default="USD", description="Currency code (USD, INR, etc)")
    market_cap: Optional[float] = Field(None, description="Market capitalization")
    pe_ratio: Optional[float] = Field(None, description="Price-to-earnings ratio")
    dividend_yield: Optional[float] = Field(None, description="Dividend yield %")
    week_52_high: Optional[float] = Field(None, description="52-week high price")
    week_52_low: Optional[float] = Field(None, description="52-week low price")
    sector: Optional[str] = Field(None, description="Company sector")


class GrowthTrend(BaseModel):
    """Financial growth trend analysis."""
    revenue_trend: Literal["accelerating", "stable", "decelerating", "volatile", "insufficient_data"] = Field(description="Revenue growth trajectory")
    profitability_trend: Literal["improving", "stable", "declining", "volatile", "insufficient_data"] = Field(description="Profitability trajectory")
    opm_trend: Literal["expanding", "stable", "contracting", "volatile", "insufficient_data"] = Field(description="Operating margin trend")
    summary: str = Field(description="Plain English summary of growth trends")


class Announcement(BaseModel):
    """Corporate announcement or news."""
    date: datetime = Field(description="Announcement date")
    title: str = Field(description="Announcement title")
    content: Optional[str] = Field(None, description="Announcement content/summary")
    source: str = Field(description="Source: earnings, corporate_action, news, etc")
    url: Optional[str] = Field(None, description="URL to source")


class RecommendationDetail(BaseModel):
    """Detailed recommendation with context."""
    signal: Recommendation = Field(description="BUY, HOLD, or SELL")
    confidence: float = Field(description="Confidence score 0-1")
    reasoning: str = Field(description="Plain English reasoning for the recommendation")
    key_drivers: List[str] = Field(description="Top 3-5 factors influencing this recommendation")
    

class SwingTradeOutlook(BaseModel):
    """Short-term swing trading opportunity analysis."""
    opportunity_exists: bool = Field(description="Whether a swing trade opportunity is identified")
    confidence_score: Optional[float] = Field(None, description="Confidence score (0-100) that setup will hit target")
    entry_zone_low: Optional[float] = Field(None, description="Suggested entry zone low price")
    entry_zone_high: Optional[float] = Field(None, description="Suggested entry zone high price")
    stop_loss_price: Optional[float] = Field(None, description="Recommended stop-loss price")
    stop_loss_percent: Optional[float] = Field(None, description="Stop-loss as % below entry")
    target_low: Optional[float] = Field(None, description="Target price low estimate")
    target_high: Optional[float] = Field(None, description="Target price high estimate")
    target_return_percent: Optional[float] = Field(None, description="Expected return % at target")
    invalidation_price: Optional[float] = Field(None, description="Price at which setup is invalidated")
    timeframe_days: Optional[int] = Field(None, description="Expected holding period in days")
    commentary: str = Field(description="Plain English context and caveats")


class LongTermOutlook(BaseModel):
    """Long-term investment outlook."""
    target_price_low: Optional[float] = Field(None, description="Multi-year target price low")
    target_price_high: Optional[float] = Field(None, description="Multi-year target price high")
    target_return_percent: Optional[float] = Field(None, description="Expected return % over 3-5 years")
    bull_case_return: Optional[float] = Field(None, description="Bull case return %")
    bear_case_return: Optional[float] = Field(None, description="Bear case return %")
    base_case_return: Optional[float] = Field(None, description="Base case return %")
    holding_period_years: Optional[int] = Field(default=3, description="Target holding period")
    commentary: str = Field(description="Long-term narrative and context")


class RiskScenario(BaseModel):
    """Success or failure scenario."""
    scenario_name: str = Field(description="Scenario name: bull, base, bear, etc")
    probability: float = Field(description="Estimated probability 0-1")
    description: str = Field(description="What happens in this scenario")
    key_triggers: List[str] = Field(description="Key events that would trigger this scenario")
    expected_return: Optional[float] = Field(None, description="Expected return % in this scenario")


class RiskAnalysis(BaseModel):
    """Comprehensive risk assessment."""
    overall_risk_level: RiskLevel = Field(description="Overall risk classification")
    volatility_risk: RiskLevel = Field(description="Stock price volatility risk")
    business_risk: RiskLevel = Field(description="Business/operational risk")
    market_risk: RiskLevel = Field(description="Market/macroeconomic risk")
    scenarios: List[RiskScenario] = Field(description="Success/failure scenarios")
    downside_triggers: List[str] = Field(description="Key downside risks and triggers")
    uncertainty_notes: List[str] = Field(description="Data gaps or areas of uncertainty")
    summary: str = Field(description="Overall risk summary and key considerations")


class StockAnalysis(BaseModel):
    """Complete stock analysis output."""
    ticker: str = Field(description="Stock ticker")
    timestamp: datetime = Field(default_factory=datetime.now, description="Analysis timestamp")
    
    # Market metrics
    metrics: StockMetrics = Field(description="Current market metrics")
    
    # Financial history
    financial_history: List[FinancialYear] = Field(description="3-year financial history (most recent first)")
    
    # Trends and growth
    growth_trend: GrowthTrend = Field(description="Growth trend analysis")
    
    # News and announcements
    recent_announcements: List[Announcement] = Field(default_factory=list, description="Recent announcements")
    
    # Recommendation
    recommendation: RecommendationDetail = Field(description="Educational investment recommendation")
    expected_returns: Dict[str, float] = Field(description="Expected return scenarios: bull, base, bear")
    
    # Trading opportunities
    swing_trade: SwingTradeOutlook = Field(description="Short-term swing trade outlook")
    long_term: LongTermOutlook = Field(description="Long-term investment outlook")
    
    # Risk
    risk_analysis: RiskAnalysis = Field(description="Comprehensive risk assessment")
    
    # Metadata
    data_sources: List[str] = Field(description="Sources used: yahoo_finance, screener_in, etc")
    analysis_quality: Literal["complete", "partial", "degraded"] = Field(default="complete", description="Quality of analysis based on data availability")
    missing_data_notes: List[str] = Field(default_factory=list, description="Notes on missing or unavailable data")


class SearchHistory(BaseModel):
    """Recent search history entry."""
    id: str = Field(description="Unique search ID")
    ticker: str = Field(description="Stock ticker searched")
    company_name: Optional[str] = Field(None, description="Company name (cached from last search)")
    timestamp: datetime = Field(default_factory=datetime.now, description="Search timestamp")
    recommendation: Optional[Recommendation] = Field(None, description="Last recommendation for this ticker")
    report_path: Optional[str] = Field(None, description="Path to generated PDF report")
    status: Literal["success", "partial", "failed"] = Field(default="success", description="Search status")
    error_message: Optional[str] = Field(None, description="Error message if search failed")


@dataclass
class ResearchProgress:
    """Track research progress for UI display."""
    stage: str = "initializing"
    message: str = ""
    percentage: int = 0
    is_complete: bool = False
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
