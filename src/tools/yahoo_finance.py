"""Yahoo Finance data adapter for stock research."""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import yfinance as yf
import pandas as pd

from src.models.research import FinancialYear, StockMetrics, Announcement

logger = logging.getLogger(__name__)


class YahooFinanceClient:
    """Fetches stock data and financial metrics from Yahoo Finance."""
    
    def __init__(self, timeout: int = 30):
        """Initialize Yahoo Finance client.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
    
    def get_stock_metrics(self, ticker: str) -> Optional[StockMetrics]:
        """Fetch current stock metrics.
        
        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL', 'RELIANCE.NS')
            
        Returns:
            StockMetrics object or None if fetch fails
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            if not info:
                logger.warning(f"No info found for ticker {ticker}")
                return None
            
            metrics = StockMetrics(
                ticker=ticker,
                company_name=info.get("longName", ticker),
                current_price=info.get("currentPrice") or info.get("regularMarketPrice", 0.0),
                currency=info.get("currency", "USD"),
                market_cap=info.get("marketCap"),
                pe_ratio=info.get("trailingPE"),
                dividend_yield=info.get("dividendYield"),
                week_52_high=info.get("fiftyTwoWeekHigh"),
                week_52_low=info.get("fiftyTwoWeekLow"),
                sector=info.get("sector"),
            )
            return metrics
        except Exception as e:
            logger.error(f"Error fetching metrics for {ticker}: {e}")
            return None
    
    def get_financial_statements(self, ticker: str, years: int = 3) -> List[FinancialYear]:
        """Fetch annual financial statements for past N years.
        
        Args:
            ticker: Stock ticker symbol
            years: Number of years to fetch (default 3)
            
        Returns:
            List of FinancialYear objects (most recent first)
        """
        try:
            stock = yf.Ticker(ticker)
            
            # Fetch annual financials
            income_stmt = stock.income_stmt  # Annual income statement
            
            if income_stmt is None or income_stmt.empty:
                logger.warning(f"No income statement found for {ticker}")
                return []
            
            financial_years = []
            
            # Get the most recent N years
            for idx, date in enumerate(income_stmt.columns[:years]):
                try:
                    year = date.year
                    
                    # Extract financial metrics
                    revenue = income_stmt.loc["Total Revenue", date] if "Total Revenue" in income_stmt.index else None
                    operating_income = income_stmt.loc["Operating Income", date] if "Operating Income" in income_stmt.index else None
                    net_income = income_stmt.loc["Net Income", date] if "Net Income" in income_stmt.index else None
                    
                    # Calculate metrics
                    opm = None
                    if operating_income and revenue and revenue != 0:
                        opm = (operating_income / revenue) * 100
                    
                    # Try to get expenses (can be calculated or directly available)
                    total_expenses = None
                    if revenue and operating_income:
                        total_expenses = revenue - operating_income
                    
                    # Profit before tax (approximation using net income + tax)
                    pbt = None
                    if "Income Before Tax" in income_stmt.index:
                        pbt = income_stmt.loc["Income Before Tax", date]
                    elif net_income:
                        pbt = net_income  # Fallback approximation
                    
                    # Calculate YoY growth if we have previous year
                    yoy_growth = None
                    if idx > 0 and revenue:
                        prev_revenue = income_stmt.loc["Total Revenue", income_stmt.columns[idx - 1]]
                        if prev_revenue and prev_revenue != 0:
                            yoy_growth = ((revenue - prev_revenue) / prev_revenue) * 100
                    
                    fy = FinancialYear(
                        year=year,
                        sales_revenue=float(revenue) if revenue else None,
                        expenses=float(total_expenses) if total_expenses else None,
                        operating_profit=float(operating_income) if operating_income else None,
                        opm=opm,
                        net_profit=float(net_income) if net_income else None,
                        profit_before_tax=float(pbt) if pbt else None,
                        yoy_revenue_growth=yoy_growth,
                    )
                    financial_years.append(fy)
                except Exception as e:
                    logger.warning(f"Error parsing financials for {ticker} year {year}: {e}")
                    continue
            
            return financial_years
        except Exception as e:
            logger.error(f"Error fetching financial statements for {ticker}: {e}")
            return []
    
    def get_price_history(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """Fetch historical price data.
        
        Args:
            ticker: Stock ticker symbol
            period: Period to fetch ('1y', '5y', '10y', etc.)
            
        Returns:
            DataFrame with OHLCV data or None if fetch fails
        """
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            
            if hist is None or hist.empty:
                logger.warning(f"No price history found for {ticker} period {period}")
                return None
            
            return hist
        except Exception as e:
            logger.error(f"Error fetching price history for {ticker}: {e}")
            return None
    
    def get_earnings_dates(self, ticker: str, limit: int = 5) -> List[Dict]:
        """Get recent earnings announcement dates.
        
        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of earnings dates to return
            
        Returns:
            List of earnings date dictionaries with date and expected date
        """
        try:
            stock = yf.Ticker(ticker)
            earnings_dates = stock.earnings_dates
            
            if earnings_dates is None or earnings_dates.empty:
                return []
            
            results = []
            for idx, (date, row) in enumerate(earnings_dates.iterrows()):
                if idx >= limit:
                    break
                results.append({
                    "date": date,
                    "eps_estimate": row.get("Earnings Estimate"),
                    "eps_actual": row.get("Reported EPS"),
                    "surprise_pct": row.get("Surprise(%)"),
                })
            
            return results
        except Exception as e:
            logger.warning(f"Error fetching earnings dates for {ticker}: {e}")
            return []
    
    def get_analyst_recommendations(self, ticker: str) -> Optional[Dict]:
        """Get analyst recommendations summary.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with recommendation summary or None
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            if not info:
                return None
            
            return {
                "recommendation": info.get("recommendationKey"),
                "number_of_analysts": info.get("numberOfAnalysts"),
                "target_price": info.get("targetMeanPrice"),
                "strong_buy": info.get("recommendationKey") == "strong_buy",
                "buy": info.get("recommendationKey") == "buy",
                "hold": info.get("recommendationKey") == "hold",
                "sell": info.get("recommendationKey") == "sell",
            }
        except Exception as e:
            logger.warning(f"Error fetching analyst recommendations for {ticker}: {e}")
            return None
    
    def is_valid_ticker(self, ticker: str) -> bool:
        """Check if ticker is valid by attempting to fetch basic info.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            True if ticker is valid, False otherwise
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return bool(info and info.get("regularMarketPrice"))
        except Exception:
            return False
