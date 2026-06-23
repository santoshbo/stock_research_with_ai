"""Main application orchestrator for stock research."""

import logging
from datetime import datetime
from typing import Optional, Tuple

from src.config import Config
from src.models.research import StockAnalysis, RecommendationDetail, ResearchProgress, Recommendation, RiskAnalysis
from src.tools.aggregator import DataAggregator
from src.tools.scoring import ScoringEngine, RiskAnalyzer, RecommendationGenerator
from src.tools.trading import TradingOpportunityAnalyzer
from src.storage.report_writer import ReportWriter
from src.storage.history_store import SearchHistoryStore
from src.llm.groq_client import GroqClient

logger = logging.getLogger(__name__)


class StockResearchAgent:
    """Main orchestrator for complete stock research pipeline."""
    
    def __init__(self):
        """Initialize research agent with all components."""
        self.aggregator = DataAggregator(enable_screener_in=Config.ENABLE_SCREENER_IN)
        self.scoring_engine = ScoringEngine()
        self.risk_analyzer = RiskAnalyzer()
        self.trading_analyzer = TradingOpportunityAnalyzer()
        self.report_writer = ReportWriter()
        self.history_store = SearchHistoryStore(max_history=Config.MAX_SEARCH_HISTORY)
        self.llm = GroqClient()
    
    def research_stock(self, ticker: str) -> Tuple[Optional[StockAnalysis], ResearchProgress]:
        """Execute complete research pipeline for a stock.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Tuple of (StockAnalysis object, final progress object)
        """
        progress = ResearchProgress()
        
        try:
            # Step 1: Aggregate data
            progress.stage = "Aggregating data from Yahoo Finance and Screener.in..."
            progress.percentage = 10
            logger.info(f"Starting research for {ticker}")
            
            aggregated = self.aggregator.aggregate_stock_data(ticker)
            if not aggregated:
                progress.error = f"Failed to fetch data for {ticker}"
                progress.is_complete = True
                self.history_store.add_search(ticker, status="failed", error_message=progress.error)
                return None, progress
            
            # Step 2: Analyze growth trends
            progress.stage = "Analyzing growth trends..."
            progress.percentage = 20
            
            financial_history = aggregated.get("financial_history", [])
            growth_trend = self.aggregator.analyze_growth_trends(financial_history)
            
            # Step 3: Calculate scores
            progress.stage = "Scoring profitability, growth, and momentum..."
            progress.percentage = 40
            
            profitability_score, prof_reasoning = self.scoring_engine.score_profitability(financial_history)
            growth_score, growth_reasoning = self.scoring_engine.score_growth(financial_history, growth_trend)
            momentum_score, momentum_reasoning = self.scoring_engine.score_momentum(aggregated.get("price_history"))
            valuation_score, valuation_reasoning = self.scoring_engine.score_valuation(
                aggregated["metrics"].pe_ratio
            )
            
            # Composite score
            composite_score, key_drivers = self.scoring_engine.calculate_composite_score(
                profitability_score, growth_score, momentum_score, valuation_score
            )
            
            # Step 4: Risk analysis
            progress.stage = "Assessing risk factors..."
            progress.percentage = 60
            
            volatility_risk = self.risk_analyzer.calculate_volatility_risk(aggregated.get("price_history"))
            business_risk = self.risk_analyzer.calculate_business_risk(financial_history)
            
            # Overall risk
            overall_risk = self._calculate_overall_risk(volatility_risk, business_risk)
            
            # Risk scenarios
            risk_scenarios = self.risk_analyzer.generate_scenarios(
                ticker,
                aggregated["metrics"].current_price,
                target_price=self._estimate_target_price(composite_score, aggregated["metrics"].current_price)
            )
            
            # Step 5: Trading opportunities
            progress.stage = "Analyzing trading opportunities..."
            progress.percentage = 75
            
            swing_trade = self.trading_analyzer.analyze_swing_trade(
                aggregated["metrics"].current_price,
                aggregated.get("price_history"),
                volatility_risk,
                momentum_score,
                min_return_percent=12.0,  # Require 12% minimum return to qualify
            )
            
            long_term = self.trading_analyzer.analyze_long_term(
                aggregated["metrics"].current_price,
                profitability_score,
                growth_score,
                business_risk,
            )
            
            # Step 6: Generate recommendation
            progress.stage = "Generating recommendation..."
            progress.percentage = 80
            
            confidence = min(composite_score / 100, 1.0)
            rec_generator = RecommendationGenerator()
            signal = rec_generator.generate_recommendation(composite_score, confidence, key_drivers)
            
            recommendation = RecommendationDetail(
                signal=signal,
                confidence=confidence,
                reasoning=f"Based on profitability ({profitability_score:.0f}), growth ({growth_score:.0f}), "
                         f"momentum ({momentum_score:.0f}), and valuation ({valuation_score:.0f}) analysis.",
                key_drivers=key_drivers,
            )
            
            # Step 7: Build complete analysis
            progress.stage = "Compiling report..."
            progress.percentage = 85
            
            quality, missing_notes = self.aggregator.calculate_analysis_quality(aggregated)
            
            risk_analysis = RiskAnalysis(
                overall_risk_level=overall_risk,
                volatility_risk=volatility_risk,
                business_risk=business_risk,
                market_risk=self._estimate_market_risk(business_risk),
                scenarios=risk_scenarios,
                downside_triggers=self._generate_downside_triggers(financial_history, business_risk),
                uncertainty_notes=missing_notes,
                summary=f"Overall risk: {overall_risk.value}. Business fundamentals stable. Market conditions should be monitored.",
            )
            
            analysis = StockAnalysis(
                ticker=ticker,
                timestamp=datetime.now(),
                metrics=aggregated["metrics"],
                financial_history=financial_history,
                growth_trend=growth_trend,
                recent_announcements=aggregated.get("announcements", []),
                recommendation=recommendation,
                expected_returns={
                    "bull": long_term.bull_case_return or 0.0,
                    "base": long_term.base_case_return or 0.0,
                    "bear": long_term.bear_case_return or 0.0,
                },
                swing_trade=swing_trade,
                long_term=long_term,
                risk_analysis=risk_analysis,
                data_sources=aggregated.get("data_sources", ["yahoo_finance"]),
                analysis_quality=quality,
                missing_data_notes=missing_notes,
            )
            
            # Step 8: Save reports
            progress.stage = "Saving reports..."
            progress.percentage = 90
            
            json_path = self.report_writer.save_json(analysis)
            md_path = self.report_writer.save_markdown(analysis)
            pdf_path = self.report_writer.save_pdf(analysis)
            
            report_path = str(pdf_path) if pdf_path else (str(md_path) if md_path else None)
            
            # Step 9: Update history
            progress.stage = "Updating search history..."
            progress.percentage = 95
            
            self.history_store.add_search(
                ticker=ticker,
                company_name=aggregated["metrics"].company_name,
                recommendation=signal,
                report_path=report_path,
                status="success",
            )
            
            progress.stage = "Complete"
            progress.percentage = 100
            progress.is_complete = True
            
            logger.info(f"Successfully completed research for {ticker}: {signal.value}")
            return analysis, progress
        
        except Exception as e:
            logger.error(f"Error in research pipeline for {ticker}: {e}", exc_info=True)
            progress.error = f"Error during research: {str(e)}"
            progress.is_complete = True
            self.history_store.add_search(ticker, status="failed", error_message=progress.error)
            return None, progress
    
    def _estimate_target_price(self, composite_score: float, current_price: float) -> float:
        """Estimate fair value target price based on score.
        
        Args:
            composite_score: Composite score (0-100)
            current_price: Current stock price
            
        Returns:
            Estimated target price
        """
        # Simple heuristic: high scores suggest upside
        if composite_score >= 75:
            return current_price * 1.20  # 20% upside
        elif composite_score >= 60:
            return current_price * 1.10  # 10% upside
        elif composite_score >= 50:
            return current_price * 1.05  # 5% upside
        else:
            return current_price * 0.95  # 5% downside
    
    def _calculate_overall_risk(self, volatility_risk, business_risk) -> Recommendation:
        """Calculate overall risk from components.
        
        Args:
            volatility_risk: Volatility risk level
            business_risk: Business risk level
            
        Returns:
            Overall risk level
        """
        from src.models.research import RiskLevel
        
        risk_scores = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
        }
        
        avg_risk = (risk_scores[volatility_risk] + risk_scores[business_risk]) / 2
        
        if avg_risk < 1.5:
            return RiskLevel.LOW
        elif avg_risk < 2.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.HIGH
    
    def _estimate_market_risk(self, business_risk) -> Recommendation:
        """Estimate market/macro risk (correlated with business risk).
        
        Args:
            business_risk: Business risk level
            
        Returns:
            Market risk level
        """
        from src.models.research import RiskLevel
        
        # Market risk is typically lower than business risk but correlated
        if business_risk == RiskLevel.LOW:
            return RiskLevel.LOW
        elif business_risk == RiskLevel.MEDIUM:
            return RiskLevel.LOW  # Assume market risk is lower
        else:
            return RiskLevel.MEDIUM
    
    def _generate_downside_triggers(self, financial_history, business_risk) -> list:
        """Generate key downside risk triggers.
        
        Args:
            financial_history: Financial history data
            business_risk: Business risk level
            
        Returns:
            List of downside triggers
        """
        triggers = [
            "Earnings miss vs. expectations",
            "Market share loss to competitors",
        ]
        
        from src.models.research import RiskLevel
        
        if business_risk == RiskLevel.HIGH:
            triggers.extend([
                "Significant margin compression",
                "Debt covenant violations",
            ])
        
        if financial_history and any(fy.yoy_revenue_growth and fy.yoy_revenue_growth < 0 for fy in financial_history[:2]):
            triggers.append("Continued revenue decline")
        
        return triggers[:5]  # Return top 5
