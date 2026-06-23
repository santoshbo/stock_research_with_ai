#!/usr/bin/env python
"""End-to-end test of the stock research application."""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def test_imports():
    """Test all module imports."""
    logger.info("Testing module imports...")
    try:
        from src.config import Config
        from src.models.research import StockAnalysis
        from src.tools.yahoo_finance import YahooFinanceClient
        from src.tools.screener_in import ScreenerInClient
        from src.tools.company_lookup import CompanyLookup
        from src.tools.aggregator import DataAggregator
        from src.tools.scoring import ScoringEngine
        from src.tools.trading import TradingOpportunityAnalyzer
        from src.storage.report_writer import ReportWriter
        from src.storage.history_store import SearchHistoryStore
        from src.llm.groq_client import GroqClient
        from src.app import StockResearchAgent
        logger.info("✅ All imports successful")
        return True
    except Exception as e:
        logger.error(f"❌ Import error: {e}")
        return False


def test_company_lookup():
    """Test company name to ticker resolution."""
    logger.info("\nTesting company name lookup...")
    from src.tools.company_lookup import CompanyLookup
    
    test_cases = [
        ("apple", "AAPL"),
        ("Apple", "AAPL"),
        ("AAPL", "AAPL"),
        ("reliance", "RELIANCE.NS"),
        ("Reliance Industries", "RELIANCE.NS"),
        ("infosys", "INFY.NS"),
        ("INFY.NS", "INFY.NS"),
        ("microsoft", "MSFT"),
        ("tcs", "TCS.NS"),
    ]
    
    all_pass = True
    for query, expected in test_cases:
        result = CompanyLookup.lookup(query)
        passed = result == expected
        status = "✅" if passed else "❌"
        logger.info(f"  {status} '{query}' → '{result}' (expected: '{expected}')")
        if not passed:
            all_pass = False
    
    return all_pass


def test_yahoo_finance():
    """Test Yahoo Finance data fetching."""
    logger.info("\nTesting Yahoo Finance adapter...")
    from src.tools.yahoo_finance import YahooFinanceClient
    
    client = YahooFinanceClient()
    
    # Test ticker validation
    test_tickers = ["AAPL", "RELIANCE.NS", "INVALID_TICKER_XYZ"]
    
    for ticker in test_tickers:
        is_valid = client.is_valid_ticker(ticker)
        status = "✅" if is_valid else "⚠️"
        logger.info(f"  {status} {ticker}: valid={is_valid}")
    
    # Try to fetch real data for a known ticker
    logger.info("\n  Fetching sample data for AAPL...")
    try:
        metrics = client.get_stock_metrics("AAPL")
        if metrics:
            logger.info(f"    ✅ Got metrics: {metrics.company_name} (${metrics.current_price})")
            return True
        else:
            logger.warning("    ⚠️ No metrics returned")
            return False
    except Exception as e:
        logger.error(f"    ❌ Error: {e}")
        return False


def test_data_aggregation():
    """Test data aggregation pipeline."""
    logger.info("\nTesting data aggregation...")
    from src.tools.aggregator import DataAggregator
    
    aggregator = DataAggregator(enable_screener_in=False)
    
    # Test with US stock (more reliable)
    logger.info("  Aggregating data for AAPL...")
    try:
        data = aggregator.aggregate_stock_data("AAPL", years=3)
        
        if not data:
            logger.error("    ❌ No data returned")
            return False
        
        logger.info(f"    ✅ Got ticker: {data['ticker']}")
        logger.info(f"    ✅ Got metrics: {data['metrics'].company_name}")
        
        fin_years = len(data.get('financial_history', []))
        logger.info(f"    ✅ Financial history: {fin_years} years")
        
        if fin_years > 0:
            logger.info(f"    ✅ Most recent year: {data['financial_history'][0].year}")
        
        return True
    except Exception as e:
        logger.error(f"    ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scoring():
    """Test recommendation scoring."""
    logger.info("\nTesting scoring engine...")
    from src.tools.scoring import ScoringEngine
    from src.models.research import FinancialYear, GrowthTrend
    
    scorer = ScoringEngine()
    
    # Create mock financial data
    financial_history = [
        FinancialYear(
            year=2024,
            sales_revenue=1000000000,
            operating_profit=200000000,
            opm=20.0,
            net_profit=150000000,
            profit_before_tax=160000000,
            yoy_revenue_growth=15.0,
        ),
        FinancialYear(
            year=2023,
            sales_revenue=900000000,
            operating_profit=180000000,
            opm=20.0,
            net_profit=135000000,
            profit_before_tax=144000000,
            yoy_revenue_growth=10.0,
        ),
    ]
    
    try:
        prof_score, _ = scorer.score_profitability(financial_history)
        logger.info(f"    ✅ Profitability score: {prof_score:.0f}")
        
        growth_trend = GrowthTrend(
            revenue_trend="accelerating",
            profitability_trend="stable",
            opm_trend="stable",
            summary="Growing revenue"
        )
        growth_score, _ = scorer.score_growth(financial_history, growth_trend)
        logger.info(f"    ✅ Growth score: {growth_score:.0f}")
        
        composite, drivers = scorer.calculate_composite_score(
            prof_score, growth_score, 60.0, 50.0
        )
        logger.info(f"    ✅ Composite score: {composite:.0f}")
        logger.info(f"    ✅ Key drivers: {drivers}")
        
        return True
    except Exception as e:
        logger.error(f"    ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_report_generation():
    """Test report file generation."""
    logger.info("\nTesting report generation...")
    from src.storage.report_writer import ReportWriter
    from src.models.research import (
        StockAnalysis, StockMetrics, FinancialYear, GrowthTrend,
        RecommendationDetail, Recommendation, RiskAnalysis, SwingTradeOutlook,
        LongTermOutlook, RiskLevel
    )
    from datetime import datetime
    
    try:
        # Create minimal analysis object
        analysis = StockAnalysis(
            ticker="TEST",
            timestamp=datetime.now(),
            metrics=StockMetrics(
                ticker="TEST",
                company_name="Test Company",
                current_price=100.0,
            ),
            financial_history=[],
            growth_trend=GrowthTrend(
                revenue_trend="stable",
                profitability_trend="stable",
                opm_trend="stable",
                summary="Test"
            ),
            recommendation=RecommendationDetail(
                signal=Recommendation.HOLD,
                confidence=0.5,
                reasoning="Test recommendation",
                key_drivers=["Test driver"]
            ),
            expected_returns={"bull": 10.0, "base": 5.0, "bear": -5.0},
            swing_trade=SwingTradeOutlook(
                opportunity_exists=False,
                commentary="No opportunity"
            ),
            long_term=LongTermOutlook(
                commentary="Long term outlook"
            ),
            risk_analysis=RiskAnalysis(
                overall_risk_level=RiskLevel.MEDIUM,
                volatility_risk=RiskLevel.MEDIUM,
                business_risk=RiskLevel.MEDIUM,
                market_risk=RiskLevel.MEDIUM,
                scenarios=[],
                downside_triggers=[],
                uncertainty_notes=[],
                summary="Test"
            ),
            data_sources=["test_source"]
        )
        
        writer = ReportWriter()
        
        # Test JSON
        json_path = writer.save_json(analysis)
        if json_path and json_path.exists():
            logger.info(f"    ✅ JSON report saved: {json_path}")
        else:
            logger.warning(f"    ⚠️ JSON report not created")
        
        # Test Markdown
        md_path = writer.save_markdown(analysis)
        if md_path and md_path.exists():
            logger.info(f"    ✅ Markdown report saved: {md_path}")
        else:
            logger.warning(f"    ⚠️ Markdown report not created")
        
        # Test PDF
        pdf_path = writer.save_pdf(analysis)
        if pdf_path and pdf_path.exists():
            logger.info(f"    ✅ PDF report saved: {pdf_path}")
        else:
            logger.warning(f"    ⚠️ PDF report not created")
        
        return True
    except Exception as e:
        logger.error(f"    ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_history_store():
    """Test search history persistence."""
    logger.info("\nTesting search history...")
    from src.storage.history_store import SearchHistoryStore
    from src.models.research import Recommendation
    
    try:
        store = SearchHistoryStore(max_history=5)
        
        # Add a test search
        search = store.add_search(
            ticker="TEST.NS",
            company_name="Test Company",
            recommendation=Recommendation.BUY,
            status="success"
        )
        
        logger.info(f"    ✅ Added search: {search.ticker}")
        
        # Retrieve history
        history = store.get_history()
        logger.info(f"    ✅ History size: {len(history)}")
        
        # Test retrieval by ticker
        matches = store.get_by_ticker("TEST.NS")
        logger.info(f"    ✅ Found {len(matches)} searches for TEST.NS")
        
        return True
    except Exception as e:
        logger.error(f"    ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Stock Research AI - End-to-End Test Suite")
    logger.info("=" * 60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Company Lookup", test_company_lookup),
        ("Yahoo Finance", test_yahoo_finance),
        ("Data Aggregation", test_data_aggregation),
        ("Scoring Engine", test_scoring),
        ("Report Generation", test_report_generation),
        ("History Store", test_history_store),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            logger.error(f"❌ Test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅" if passed else "❌"
        logger.info(f"{status} {test_name}")
    
    logger.info(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        logger.info("\n🎉 All tests passed!")
        return 0
    else:
        logger.warning(f"\n⚠️ {total_count - passed_count} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
