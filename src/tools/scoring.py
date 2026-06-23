"""Scoring and recommendation engine."""

import logging
import pandas as pd
from typing import Optional, Dict, List, Tuple
from datetime import datetime

from src.models.research import (
    Recommendation, RiskLevel, FinancialYear, GrowthTrend,
    SwingTradeOutlook, LongTermOutlook, RiskAnalysis, RiskScenario
)

logger = logging.getLogger(__name__)


class ScoringEngine:
    """Deterministic scoring for investment recommendation."""
    
    def __init__(self):
        """Initialize scoring engine with weighted thresholds."""
        # Component weights
        self.weight_profitability = 0.35
        self.weight_growth = 0.30
        self.weight_momentum = 0.20
        self.weight_valuation = 0.15
    
    def score_profitability(self, financial_history: List[FinancialYear]) -> Tuple[float, str]:
        """Score current and historical profitability.
        
        Returns:
            Tuple of (score 0-100, reasoning)
        """
        if not financial_history:
            return 50, "No profitability data available"
        
        try:
            # Get most recent 2 years
            recent = financial_history[:2]
            
            scores = []
            reasoning_parts = []
            
            for fy in recent:
                if fy.net_profit and fy.sales_revenue and fy.sales_revenue > 0:
                    profit_margin = (fy.net_profit / fy.sales_revenue) * 100
                    
                    # Score based on margin levels
                    if profit_margin > 15:
                        score = 90
                    elif profit_margin > 10:
                        score = 75
                    elif profit_margin > 5:
                        score = 60
                    elif profit_margin > 0:
                        score = 40
                    else:
                        score = 20
                    
                    scores.append(score)
                    reasoning_parts.append(f"{fy.year}: {profit_margin:.1f}% margin")
            
            if scores:
                avg_score = sum(scores) / len(scores)
                reasoning = ", ".join(reasoning_parts)
                return avg_score, reasoning
            else:
                return 50, "Insufficient profitability data"
        except Exception as e:
            logger.error(f"Error scoring profitability: {e}")
            return 50, f"Error calculating profitability score: {str(e)}"
    
    def score_growth(self, financial_history: List[FinancialYear], trend: GrowthTrend) -> Tuple[float, str]:
        """Score growth trajectory.
        
        Returns:
            Tuple of (score 0-100, reasoning)
        """
        try:
            # Analyze YoY growth rates
            growth_rates = [fy.yoy_revenue_growth for fy in financial_history if fy.yoy_revenue_growth]
            
            if not growth_rates:
                # Use trend analysis if YoY data not available
                if trend.revenue_trend == "accelerating":
                    return 80, "Revenue accelerating (from trend analysis)"
                elif trend.revenue_trend == "stable":
                    return 60, "Stable revenue growth"
                elif trend.revenue_trend == "decelerating":
                    return 40, "Revenue growth slowing"
                else:
                    return 30, "Revenue declining or unclear"
            
            avg_growth = sum(growth_rates) / len(growth_rates)
            
            if avg_growth > 20:
                score = 85
                reasoning = f"High growth: {avg_growth:.1f}% CAGR"
            elif avg_growth > 10:
                score = 70
                reasoning = f"Good growth: {avg_growth:.1f}% CAGR"
            elif avg_growth > 0:
                score = 55
                reasoning = f"Moderate growth: {avg_growth:.1f}% CAGR"
            elif avg_growth > -10:
                score = 40
                reasoning = f"Slow/flat growth: {avg_growth:.1f}% CAGR"
            else:
                score = 20
                reasoning = f"Declining revenue: {avg_growth:.1f}% CAGR"
            
            return score, reasoning
        except Exception as e:
            logger.error(f"Error scoring growth: {e}")
            return 50, f"Error calculating growth score: {str(e)}"
    
    def score_momentum(self, price_history: Optional[pd.DataFrame]) -> Tuple[float, str]:
        """Score price momentum and technical strength.
        
        Returns:
            Tuple of (score 0-100, reasoning)
        """
        if price_history is None or price_history.empty:
            return 50, "No price history available"
        
        try:
            close_prices = price_history['Close'].dropna()
            
            if len(close_prices) < 20:
                return 50, "Insufficient price history for momentum analysis"
            
            # Calculate simple momentum metrics
            # 20-day vs 50-day moving average (if available)
            ma_20 = close_prices.tail(20).mean()
            ma_50 = close_prices.tail(50).mean() if len(close_prices) >= 50 else close_prices.mean()
            current_price = close_prices.iloc[-1]
            
            # Score based on position relative to MAs
            momentum_ratio = (current_price - ma_50) / ma_50 * 100
            
            if current_price > ma_20 > ma_50:
                score = 75
                reasoning = f"Strong uptrend (+{momentum_ratio:.1f}% above 50-day MA)"
            elif current_price > ma_50:
                score = 60
                reasoning = f"Above long-term average (+{momentum_ratio:.1f}%)"
            elif current_price > ma_50 * 0.95:
                score = 50
                reasoning = f"Near average ({momentum_ratio:.1f}%)"
            else:
                score = 35
                reasoning = f"Below average ({momentum_ratio:.1f}%)"
            
            return score, reasoning
        except Exception as e:
            logger.error(f"Error scoring momentum: {e}")
            return 50, f"Error calculating momentum score: {str(e)}"
    
    def score_valuation(self, pe_ratio: Optional[float], sector_median_pe: float = 20.0) -> Tuple[float, str]:
        """Score valuation relative to sector.
        
        Args:
            pe_ratio: Current PE ratio
            sector_median_pe: Median PE for sector (default 20)
            
        Returns:
            Tuple of (score 0-100, reasoning)
        """
        if pe_ratio is None or pe_ratio <= 0:
            return 50, "PE ratio not available"
        
        try:
            # Score based on PE relative to sector
            pe_relative = pe_ratio / sector_median_pe
            
            if pe_relative < 0.8:
                score = 75
                reasoning = f"Undervalued (PE {pe_ratio:.1f} vs sector {sector_median_pe})"
            elif pe_relative < 1.0:
                score = 65
                reasoning = f"Fairly valued (PE {pe_ratio:.1f} vs sector {sector_median_pe})"
            elif pe_relative < 1.3:
                score = 50
                reasoning = f"Slightly premium (PE {pe_ratio:.1f} vs sector {sector_median_pe})"
            else:
                score = 35
                reasoning = f"Expensive (PE {pe_ratio:.1f} vs sector {sector_median_pe})"
            
            return score, reasoning
        except Exception as e:
            logger.error(f"Error scoring valuation: {e}")
            return 50, f"Error calculating valuation score: {str(e)}"
    
    def calculate_composite_score(
        self,
        profitability_score: float,
        growth_score: float,
        momentum_score: float,
        valuation_score: float,
    ) -> Tuple[float, List[str]]:
        """Calculate weighted composite score.
        
        Returns:
            Tuple of (score 0-100, list of key drivers)
        """
        composite = (
            profitability_score * self.weight_profitability +
            growth_score * self.weight_growth +
            momentum_score * self.weight_momentum +
            valuation_score * self.weight_valuation
        )
        
        # Identify key drivers (top 3)
        components = [
            ("Profitability", profitability_score, self.weight_profitability),
            ("Growth", growth_score, self.weight_growth),
            ("Momentum", momentum_score, self.weight_momentum),
            ("Valuation", valuation_score, self.weight_valuation),
        ]
        
        # Sort by weighted contribution
        drivers = sorted(
            components,
            key=lambda x: x[1] * x[2],
            reverse=True
        )
        
        driver_descriptions = [f"{name}: {score:.0f}" for name, score, _ in drivers[:3]]
        
        return min(composite, 100), driver_descriptions


class RiskAnalyzer:
    """Analyzes and scores risk factors."""
    
    def __init__(self):
        """Initialize risk analyzer."""
        pass
    
    def calculate_volatility_risk(self, price_history: Optional[pd.DataFrame]) -> RiskLevel:
        """Assess price volatility risk.
        
        Returns:
            Risk level: LOW, MEDIUM, or HIGH
        """
        if price_history is None or price_history.empty or len(price_history) < 30:
            return RiskLevel.MEDIUM
        
        try:
            returns = price_history['Close'].pct_change().dropna()
            volatility = returns.std() * 100  # Convert to percentage
            
            if volatility < 2.0:
                return RiskLevel.LOW
            elif volatility < 4.0:
                return RiskLevel.MEDIUM
            else:
                return RiskLevel.HIGH
        except Exception:
            return RiskLevel.MEDIUM
    
    def calculate_business_risk(self, financial_history: List[FinancialYear]) -> RiskLevel:
        """Assess business/operational risk based on earnings stability.
        
        Returns:
            Risk level: LOW, MEDIUM, or HIGH
        """
        if not financial_history or len(financial_history) < 2:
            return RiskLevel.MEDIUM
        
        try:
            net_profits = [fy.net_profit for fy in financial_history if fy.net_profit]
            
            if len(net_profits) < 2:
                return RiskLevel.MEDIUM
            
            # Calculate profit volatility
            changes = []
            for i in range(1, len(net_profits)):
                if net_profits[i-1] != 0:
                    pct_change = abs((net_profits[i] - net_profits[i-1]) / net_profits[i-1])
                    changes.append(pct_change)
            
            if not changes:
                return RiskLevel.MEDIUM
            
            avg_volatility = sum(changes) / len(changes)
            
            if avg_volatility < 0.15:
                return RiskLevel.LOW
            elif avg_volatility < 0.35:
                return RiskLevel.MEDIUM
            else:
                return RiskLevel.HIGH
        except Exception:
            return RiskLevel.MEDIUM
    
    def generate_scenarios(
        self,
        ticker: str,
        current_price: float,
        target_price: Optional[float] = None,
    ) -> List[RiskScenario]:
        """Generate bull, base, bear scenario projections.
        
        Returns:
            List of RiskScenario objects
        """
        scenarios = []
        
        if target_price is None:
            target_price = current_price * 1.15  # Assume 15% upside base case
        
        # Bull case: +25% upside
        bull_target = target_price * 1.25
        bull_return = ((bull_target - current_price) / current_price) * 100
        scenarios.append(RiskScenario(
            scenario_name="Bull",
            probability=0.25,
            description=f"Strong business execution, market tailwinds, above-market earnings growth",
            key_triggers=["Earnings beat expectations", "Market expansion", "Margin expansion"],
            expected_return=bull_return,
        ))
        
        # Base case: +15% upside
        base_return = ((target_price - current_price) / current_price) * 100
        scenarios.append(RiskScenario(
            scenario_name="Base",
            probability=0.50,
            description=f"As-expected business performance, aligned with market consensus",
            key_triggers=["In-line earnings", "Stable competitive position", "Normal valuations"],
            expected_return=base_return,
        ))
        
        # Bear case: -20% downside
        bear_target = target_price * 0.80
        bear_return = ((bear_target - current_price) / current_price) * 100
        scenarios.append(RiskScenario(
            scenario_name="Bear",
            probability=0.25,
            description=f"Business headwinds, competitive pressures, or macro downturn",
            key_triggers=["Earnings miss", "Market share loss", "Economic slowdown"],
            expected_return=bear_return,
        ))
        
        return scenarios


class RecommendationGenerator:
    """Generates final investment recommendation."""
    
    def generate_recommendation(
        self,
        composite_score: float,
        confidence: float,
        drivers: List[str],
    ) -> Recommendation:
        """Generate recommendation based on composite score.
        
        Args:
            composite_score: Score 0-100
            confidence: Confidence level 0-1
            drivers: Key drivers
            
        Returns:
            Recommendation (BUY, HOLD, SELL)
        """
        if composite_score >= 70:
            return Recommendation.BUY
        elif composite_score >= 50:
            return Recommendation.HOLD
        else:
            return Recommendation.SELL
