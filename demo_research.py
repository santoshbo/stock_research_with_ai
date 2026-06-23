#!/usr/bin/env python
"""Demo: Full end-to-end stock research workflow."""

import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def demo():
    """Run a complete stock research demo."""
    from src.app import StockResearchAgent
    from src.tools.company_lookup import CompanyLookup
    
    logger.info("=" * 70)
    logger.info("Stock Research AI - End-to-End Demo")
    logger.info("=" * 70)
    
    # Initialize agent
    logger.info("\nInitializing Stock Research Agent...")
    agent = StockResearchAgent()
    logger.info("✅ Agent initialized")
    
    # Test company name resolution
    logger.info("\n" + "-" * 70)
    logger.info("Company Name Resolution Test")
    logger.info("-" * 70)
    
    test_queries = ["Apple", "Microsoft", "Reliance", "TCS", "AAPL", "INFY.NS"]
    
    for query in test_queries:
        resolved = CompanyLookup.lookup(query)
        logger.info(f"  '{query}' → '{resolved}'")
    
    # Research a stock
    logger.info("\n" + "-" * 70)
    logger.info("Researching Stock: Apple Inc.")
    logger.info("-" * 70)
    
    analysis, progress = agent.research_stock("AAPL")
    
    if analysis:
        logger.info(f"\n✅ Research completed successfully!")
        logger.info(f"  Ticker: {analysis.ticker}")
        logger.info(f"  Company: {analysis.metrics.company_name}")
        logger.info(f"  Current Price: ${analysis.metrics.current_price:.2f}")
        logger.info(f"  Recommendation: {analysis.recommendation.signal.value} (Confidence: {analysis.recommendation.confidence:.0%})")
        logger.info(f"  Analysis Quality: {analysis.analysis_quality}")
        
        if analysis.financial_history:
            logger.info(f"\n  3-Year Financial Summary:")
            for fy in analysis.financial_history[:3]:
                logger.info(f"    {fy.year}: Revenue ${fy.sales_revenue/1e9:.1f}B, "
                           f"Net Profit ${fy.net_profit/1e9:.1f}B, OPM {fy.opm:.1f}%")
        
        logger.info(f"\n  Growth Trend: {analysis.growth_trend.summary}")
        
        if analysis.recent_announcements:
            logger.info(f"\n  Recent Announcements: {len(analysis.recent_announcements)} found")
            for ann in analysis.recent_announcements[:2]:
                logger.info(f"    - {ann.date.strftime('%Y-%m-%d')}: {ann.title[:60]}")
        
        logger.info(f"\n  Trading Outlook:")
        if analysis.swing_trade.opportunity_exists:
            logger.info(f"    Swing Trade: YES")
            logger.info(f"      Entry: ${analysis.swing_trade.entry_zone_low:.2f}-${analysis.swing_trade.entry_zone_high:.2f}")
            logger.info(f"      Target: {analysis.swing_trade.target_return_percent:.1f}% return")
        else:
            logger.info(f"    Swing Trade: Not favorable at this time")
        
        logger.info(f"    Long-Term (3Y): {analysis.long_term.base_case_return:.1f}% expected")
        
        logger.info(f"\n  Risk Analysis:")
        logger.info(f"    Overall Risk: {analysis.risk_analysis.overall_risk_level.value}")
        logger.info(f"    Key Downside Triggers:")
        for trigger in analysis.risk_analysis.downside_triggers[:3]:
            logger.info(f"      - {trigger}")
        
        logger.info(f"\n  Reports Generated:")
        logger.info(f"    Location: {analysis.metrics.company_name}/...")
        logger.info(f"    Files: research_report.pdf, research_report.md, research_report.json")
        
        logger.info(f"\n  Data Sources: {', '.join(analysis.data_sources)}")
        if analysis.missing_data_notes:
            logger.info(f"  Data Quality Notes:")
            for note in analysis.missing_data_notes[:2]:
                logger.info(f"    - {note}")
        
    else:
        logger.error(f"❌ Research failed: {progress.error}")
        return 1
    
    # Test search history
    logger.info("\n" + "-" * 70)
    logger.info("Search History Test")
    logger.info("-" * 70)
    
    history = agent.history_store.get_history()
    logger.info(f"Total searches in history: {len(history)}")
    logger.info(f"Recent searches (max {agent.history_store.max_history}):")
    for search in history[:5]:
        logger.info(f"  - {search.ticker}: {search.company_name} ({search.recommendation.value if search.recommendation else 'N/A'})")
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ Demo completed successfully!")
    logger.info("=" * 70)
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(demo())
    except Exception as e:
        logger.error(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
