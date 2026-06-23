"""Trading opportunity analysis for swing and long-term outlooks."""

import logging
from typing import Optional, List, Tuple
import pandas as pd

from src.models.research import SwingTradeOutlook, LongTermOutlook, RiskLevel

logger = logging.getLogger(__name__)


class TradingOpportunityAnalyzer:
    """Analyzes swing trade and long-term opportunities with risk management."""
    
    def __init__(self):
        """Initialize trading opportunity analyzer."""
        pass
    
    def _calculate_confidence_score(
        self,
        momentum_score: float,
        volatility_risk: RiskLevel,
        price_history: pd.DataFrame,
        current_price: float,
        entry_low: float,
        target_high: float,
    ) -> float:
        """Calculate confidence score (0-100) for swing trade success.
        
        Based on:
        - Momentum strength (stronger = higher confidence)
        - Volatility level (moderate = higher confidence)
        - Support/resistance strength
        - Trend alignment
        - Risk/reward ratio
        """
        confidence = 50.0  # Base score
        
        # Momentum factor: strong positive momentum increases confidence
        if momentum_score >= 70:
            confidence += 15
        elif momentum_score >= 60:
            confidence += 10
        elif momentum_score >= 55:
            confidence += 5
        
        # Volatility factor: low-to-medium volatility increases confidence
        if volatility_risk == RiskLevel.LOW:
            confidence += 15
        elif volatility_risk == RiskLevel.MEDIUM:
            confidence += 10
        # HIGH volatility reduces confidence (already penalized by early exit)
        
        # Support/resistance strength: check if entry zone has strong support
        close_prices = price_history['Close'].dropna()
        if len(close_prices) >= 20:
            low_20 = close_prices.tail(20).min()
            high_20 = close_prices.tail(20).max()
            
            # Check if current price is closer to support (good entry)
            distance_to_support = abs(current_price - low_20) / low_20
            if distance_to_support < 0.03:  # Within 3% of support
                confidence += 10
            elif distance_to_support < 0.05:
                confidence += 5
            
            # Check risk/reward ratio
            stop_distance = (current_price - entry_low) / entry_low if entry_low > 0 else 0
            reward_distance = (target_high - current_price) / current_price if current_price > 0 else 0
            
            if reward_distance > 0 and stop_distance > 0:
                risk_reward_ratio = reward_distance / stop_distance
                if risk_reward_ratio >= 3.0:  # At least 3:1 reward/risk
                    confidence += 10
                elif risk_reward_ratio >= 2.0:
                    confidence += 5
        
        # Cap at 100
        return min(100.0, confidence)
    
    def analyze_swing_trade(
        self,
        current_price: float,
        price_history: Optional[pd.DataFrame],
        volatility_risk: RiskLevel,
        momentum_score: float,
        min_return_percent: float = 12.0,  # Minimum 12% return to qualify
        min_confidence_score: float = 80.0,  # Minimum 80% confidence to qualify
    ) -> SwingTradeOutlook:
        """Analyze short-term swing trade opportunity (1-2 months, 12%+ target, 80%+ confidence).
        
        Args:
            current_price: Current stock price
            price_history: Historical price data
            volatility_risk: Overall volatility assessment
            momentum_score: Momentum score (0-100)
            min_return_percent: Minimum return required to qualify (default 12%)
            min_confidence_score: Minimum confidence required to qualify (default 80%)
            
        Returns:
            SwingTradeOutlook object with opportunity_exists set based on ALL criteria
        """
        try:
            # Only generate swing trade setup if momentum is positive and volatility not extreme
            if momentum_score < 55 or volatility_risk == RiskLevel.HIGH:
                return SwingTradeOutlook(
                    opportunity_exists=False,
                    confidence_score=0.0,
                    commentary="Momentum or volatility conditions not favorable for swing trading at this time."
                )
            
            if price_history is None or price_history.empty or len(price_history) < 20:
                return SwingTradeOutlook(
                    opportunity_exists=False,
                    confidence_score=0.0,
                    commentary="Insufficient price history for swing trade analysis."
                )
            
            # Calculate technical levels
            close_prices = price_history['Close'].dropna()
            
            # 20-day high and low for entry/exit zones
            high_20 = close_prices.tail(20).max()
            low_20 = close_prices.tail(20).min()
            
            # Entry zone (support area with some buffer)
            entry_low = max(low_20, current_price * 0.97)
            entry_high = current_price * 1.02
            
            # Calculate target price to achieve 12%+ return
            target_high = current_price * (1.0 + (min_return_percent / 100))
            target_low = current_price * 1.08  # At least 8% as minimum target
            
            # Stop loss (below entry with margin)
            stop_loss = entry_low * 0.95
            
            # Calculate actual return percentage
            stop_pct = ((entry_low - stop_loss) / entry_low) * 100
            target_return = ((target_high - current_price) / current_price) * 100
            
            # Calculate confidence score for the setup
            confidence = self._calculate_confidence_score(
                momentum_score,
                volatility_risk,
                price_history,
                current_price,
                entry_low,
                target_high,
            )
            
            # Check ALL criteria: 12%+ return AND 1-2 month timeframe AND 80%+ confidence
            qualifies = (
                target_return >= min_return_percent and
                confidence >= min_confidence_score
            )
            
            return SwingTradeOutlook(
                opportunity_exists=qualifies,  # Only True if ALL criteria met
                confidence_score=round(confidence, 1),
                entry_zone_low=round(entry_low, 2),
                entry_zone_high=round(entry_high, 2),
                stop_loss_price=round(stop_loss, 2),
                stop_loss_percent=round(stop_pct, 2),
                target_low=round(target_low, 2),
                target_high=round(target_high, 2),
                target_return_percent=round(target_return, 2),
                invalidation_price=round(high_20 * 1.05, 2),
                timeframe_days=45,  # 1-2 months (45 days)
                commentary=(
                    f"✅ QUALIFIED FOR SWING TRADE! "
                    f"Confidence: {confidence:.0f}% | Return: {target_return:.1f}% | "
                    f"Entry {entry_low:.2f}-{entry_high:.2f}, Stop {stop_loss:.2f}, "
                    f"Target {target_high:.2f}. Timeframe: 1-2 months. Invalidation above {high_20*1.05:.2f}."
                    if qualifies else
                    f"Does not meet swing trade criteria. "
                    f"Return: {target_return:.1f}% (need ≥{min_return_percent}%) | "
                    f"Confidence: {confidence:.0f}% (need ≥{min_confidence_score}%). "
                    f"Consider waiting for better setup."
                ),
            )
        except Exception as e:
            logger.error(f"Error analyzing swing trade opportunity: {e}")
            return SwingTradeOutlook(
                opportunity_exists=False,
                confidence_score=0.0,
                commentary=f"Unable to analyze swing trade: {str(e)}"
            )
    
    def analyze_long_term(
        self,
        current_price: float,
        profitability_score: float,
        growth_score: float,
        business_risk: RiskLevel,
    ) -> LongTermOutlook:
        """Analyze long-term investment opportunity and targets.
        
        Args:
            current_price: Current stock price
            profitability_score: Profitability score (0-100)
            growth_score: Growth score (0-100)
            business_risk: Business risk assessment
            
        Returns:
            LongTermOutlook object
        """
        try:
            # Calculate base target using PEG-like approach
            combined_quality_score = (profitability_score * 0.6 + growth_score * 0.4)
            
            # Risk-adjusted projection
            if business_risk == RiskLevel.LOW:
                risk_multiplier = 1.15
            elif business_risk == RiskLevel.MEDIUM:
                risk_multiplier = 1.10
            else:
                risk_multiplier = 1.05
            
            # Multi-year CAGR assumption based on growth
            if growth_score >= 75:
                assumed_cagr = 0.18  # 18% CAGR
            elif growth_score >= 60:
                assumed_cagr = 0.12  # 12% CAGR
            elif growth_score >= 45:
                assumed_cagr = 0.08  # 8% CAGR
            else:
                assumed_cagr = 0.05  # 5% CAGR
            
            # 3-year target
            years = 3
            base_target = current_price * ((1 + assumed_cagr) ** years)
            
            # Scenario targets
            bull_target = base_target * 1.25 * risk_multiplier
            bear_target = base_target * 0.75 / risk_multiplier
            
            bull_return = ((bull_target - current_price) / current_price) * 100
            base_return = ((base_target - current_price) / current_price) * 100
            bear_return = ((bear_target - current_price) / current_price) * 100
            
            return LongTermOutlook(
                target_price_low=round(bear_target, 2),
                target_price_high=round(bull_target, 2),
                target_return_percent=round(base_return, 2),
                bull_case_return=round(bull_return, 2),
                bear_case_return=round(bear_return, 2),
                base_case_return=round(base_return, 2),
                holding_period_years=years,
                commentary=f"Base case: {base_return:.0f}% return over {years} years (target {base_target:.2f}). "
                          f"Bull: {bull_return:.0f}% ({bull_target:.2f}). "
                          f"Bear: {bear_return:.0f}% ({bear_target:.2f}). "
                          f"Assumes continued business execution and market conditions.",
            )
        except Exception as e:
            logger.error(f"Error analyzing long-term outlook: {e}")
            return LongTermOutlook(
                commentary=f"Unable to analyze long-term outlook: {str(e)}"
            )
    
    def _calculate_atr(self, price_data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range for volatility assessment.
        
        Args:
            price_data: DataFrame with High, Low, Close columns
            period: ATR period
            
        Returns:
            ATR value
        """
        try:
            if len(price_data) < period:
                return 0.0
            
            high = price_data['High'].values
            low = price_data['Low'].values
            close = price_data['Close'].values
            
            tr_values = []
            for i in range(len(price_data)):
                if i == 0:
                    tr = high[i] - low[i]
                else:
                    tr = max(
                        high[i] - low[i],
                        abs(high[i] - close[i-1]),
                        abs(low[i] - close[i-1])
                    )
                tr_values.append(tr)
            
            atr = sum(tr_values[-period:]) / period
            return atr
        except Exception:
            return 0.0
