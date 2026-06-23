"""Data aggregation and normalization pipeline."""

import logging
from typing import Optional, List, Dict
from datetime import datetime

from src.models.research import (
    FinancialYear, StockMetrics, GrowthTrend, Announcement, 
    StockAnalysis, RiskLevel
)
from src.tools.yahoo_finance import YahooFinanceClient
from src.tools.screener_in import ScreenerInClient

logger = logging.getLogger(__name__)


class DataAggregator:
    """Aggregates and normalizes stock data from multiple sources."""
    
    def __init__(self, enable_screener_in: bool = True):
        """Initialize aggregator with data source clients.
        
        Args:
            enable_screener_in: Whether to fetch Screener.in data
        """
        self.yfinance = YahooFinanceClient()
        self.screener = ScreenerInClient(enabled=enable_screener_in)
    
    def aggregate_stock_data(self, ticker: str, years: int = 3) -> Optional[Dict]:
        """Aggregate all available data for a stock.
        
        Args:
            ticker: Stock ticker symbol
            years: Number of financial years to fetch
            
        Returns:
            Dictionary with aggregated data or None if major sources fail
        """
        try:
            # Validate ticker
            if not self.yfinance.is_valid_ticker(ticker):
                logger.error(f"Invalid ticker: {ticker}")
                return None
            
            # Fetch from Yahoo Finance (primary source)
            metrics = self.yfinance.get_stock_metrics(ticker)
            if not metrics:
                logger.error(f"Failed to fetch metrics for {ticker}")
                return None
            
            financial_history = self.yfinance.get_financial_statements(ticker, years)
            price_history = self.yfinance.get_price_history(ticker, period="5y")
            
            # Build base aggregated data
            aggregated = {
                "ticker": ticker,
                "metrics": metrics,
                "financial_history": financial_history,
                "price_history": price_history,
                "announcements": [],
                "data_sources": ["yahoo_finance"],
                "missing_data_notes": [],
            }
            
            # Try to fetch Indian stock data (if applicable)
            if self.screener.is_indian_stock(ticker):
                try:
                    announcements = self.screener.get_announcements(ticker, limit=10)
                    if announcements:
                        aggregated["announcements"].extend(announcements)
                        aggregated["data_sources"].append("screener_in")
                    
                    # Fetch annual reports and concalls
                    reports = self.screener.get_annual_reports(ticker)
                    concalls = self.screener.get_concall_transcripts(ticker, limit=5)
                    
                    aggregated["annual_reports"] = reports
                    aggregated["concall_transcripts"] = concalls
                except Exception as e:
                    logger.warning(f"Error fetching Screener.in data for {ticker}: {e}")
                    aggregated["missing_data_notes"].append(f"Screener.in data unavailable: {str(e)}")
            
            # Add analyst data
            analyst_info = self.yfinance.get_analyst_recommendations(ticker)
            if analyst_info:
                aggregated["analyst_recommendations"] = analyst_info
            
            # Add earnings dates
            earnings = self.yfinance.get_earnings_dates(ticker, limit=5)
            if earnings:
                aggregated["earnings_dates"] = earnings
            
            return aggregated
        except Exception as e:
            logger.error(f"Error aggregating data for {ticker}: {e}")
            return None
    
    def analyze_growth_trends(self, financial_history: List[FinancialYear]) -> GrowthTrend:
        """Analyze financial growth trends from historical data.
        
        Args:
            financial_history: List of FinancialYear objects
            
        Returns:
            GrowthTrend analysis
        """
        if not financial_history or len(financial_history) < 2:
            return GrowthTrend(
                revenue_trend="insufficient_data",
                profitability_trend="insufficient_data",
                opm_trend="insufficient_data",
                summary="Insufficient historical data for trend analysis (need at least 2 years).",
            )
        
        try:
            # Analyze revenue trend
            revenues = [fy.sales_revenue for fy in financial_history if fy.sales_revenue]
            if len(revenues) >= 2:
                revenue_changes = []
                for i in range(1, len(revenues)):
                    if revenues[i-1] != 0:
                        pct_change = ((revenues[i] - revenues[i-1]) / revenues[i-1]) * 100
                        revenue_changes.append(pct_change)
                
                if revenue_changes:
                    avg_change = sum(revenue_changes) / len(revenue_changes)
                    if avg_change > 10:
                        revenue_trend = "accelerating"
                    elif avg_change > 0:
                        revenue_trend = "stable"
                    elif avg_change > -10:
                        revenue_trend = "decelerating"
                    else:
                        revenue_trend = "declining"
                else:
                    revenue_trend = "insufficient_data"
            else:
                revenue_trend = "insufficient_data"
            
            # Analyze profitability trend
            net_profits = [fy.net_profit for fy in financial_history if fy.net_profit]
            if len(net_profits) >= 2:
                profit_changes = []
                for i in range(1, len(net_profits)):
                    if net_profits[i-1] != 0:
                        pct_change = ((net_profits[i] - net_profits[i-1]) / net_profits[i-1]) * 100
                        profit_changes.append(pct_change)
                
                if profit_changes:
                    avg_change = sum(profit_changes) / len(profit_changes)
                    if avg_change > 10:
                        profitability_trend = "improving"
                    elif avg_change > -5:
                        profitability_trend = "stable"
                    else:
                        profitability_trend = "declining"
                else:
                    profitability_trend = "insufficient_data"
            else:
                profitability_trend = "insufficient_data"
            
            # Analyze OPM trend
            opms = [fy.opm for fy in financial_history if fy.opm is not None]
            if len(opms) >= 2:
                if opms[0] > opms[-1]:
                    opm_trend = "contracting"
                elif opms[0] < opms[-1]:
                    opm_trend = "expanding"
                else:
                    opm_trend = "stable"
            else:
                opm_trend = "insufficient_data"
            
            # Generate summary
            summary = f"Revenue: {revenue_trend}. Profitability: {profitability_trend}. OPM: {opm_trend}."
            
            return GrowthTrend(
                revenue_trend=revenue_trend,
                profitability_trend=profitability_trend,
                opm_trend=opm_trend,
                summary=summary,
            )
        except Exception as e:
            logger.error(f"Error analyzing growth trends: {e}")
            return GrowthTrend(
                revenue_trend="volatile",
                profitability_trend="volatile",
                opm_trend="volatile",
                summary=f"Error analyzing trends: {str(e)}",
            )
    
    def calculate_analysis_quality(self, aggregated_data: Dict) -> tuple:
        """Determine data completeness and analysis quality.
        
        Args:
            aggregated_data: Aggregated data dictionary
            
        Returns:
            Tuple of (quality_level, missing_notes)
            where quality_level is 'complete', 'partial', or 'degraded'
        """
        missing_notes = []
        completeness_score = 0
        
        # Check financial data
        financial_history = aggregated_data.get("financial_history", [])
        if not financial_history:
            missing_notes.append("No financial statements found (API limits or private company)")
            completeness_score -= 30
        elif len(financial_history) < 3:
            missing_notes.append(f"Only {len(financial_history)} years of financial data available (3+ recommended)")
            completeness_score -= 10
        
        # Check price history
        if not aggregated_data.get("price_history") is not None:
            missing_notes.append("Limited price history (may affect trend analysis)")
            completeness_score -= 15
        
        # Check announcements
        if not aggregated_data.get("announcements"):
            missing_notes.append("No recent announcements found")
            completeness_score -= 5
        
        # Check analyst ratings
        if not aggregated_data.get("analyst_recommendations"):
            missing_notes.append("No analyst recommendations available")
            completeness_score -= 10
        
        # Determine quality level
        if completeness_score >= 0:
            quality = "complete"
        elif completeness_score >= -30:
            quality = "partial"
        else:
            quality = "degraded"
        
        return quality, missing_notes
