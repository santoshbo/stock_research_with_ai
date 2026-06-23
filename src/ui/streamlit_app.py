"""Streamlit UI for stock research application."""

import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path

from src.app import StockResearchAgent
from src.models.research import Recommendation
from src.config import Config
from src.tools.company_lookup import CompanyLookup
from src.tools.charts import ChartGenerator

# Configure Streamlit page
st.set_page_config(
    page_title="Stock Research AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main {
        max-width: 1200px;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .buy {
        color: #09ab15;
        font-weight: bold;
    }
    .hold {
        color: #f7931e;
        font-weight: bold;
    }
    .sell {
        color: #d74e09;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "agent" not in st.session_state:
    st.session_state.agent = StockResearchAgent()

if "last_analysis" not in st.session_state:
    st.session_state.last_analysis = None

if "research_in_progress" not in st.session_state:
    st.session_state.research_in_progress = False


def format_recommendation(rec):
    """Format recommendation with color."""
    if rec == Recommendation.BUY:
        return '<span class="buy">🟢 BUY</span>'
    elif rec == Recommendation.HOLD:
        return '<span class="hold">🟡 HOLD</span>'
    else:
        return '<span class="sell">🔴 SELL</span>'


def display_financial_table(analysis):
    """Display 3-year financial summary."""
    if not analysis.financial_history:
        st.warning("No financial data available")
        return
    
    rows = []
    for fy in analysis.financial_history[:3]:
        rows.append({
            "Year": fy.year,
            "Revenue": f"₹{fy.sales_revenue/1e7:.0f}Cr" if fy.sales_revenue else "N/A",
            "Op. Profit": f"₹{fy.operating_profit/1e7:.0f}Cr" if fy.operating_profit else "N/A",
            "OPM %": f"{fy.opm:.1f}%" if fy.opm else "N/A",
            "Net Profit": f"₹{fy.net_profit/1e7:.0f}Cr" if fy.net_profit else "N/A",
            "PBT": f"₹{fy.profit_before_tax/1e7:.0f}Cr" if fy.profit_before_tax else "N/A",
        })
    
    df = pd.DataFrame(rows)
    st.table(df)


def display_recommendation(analysis):
    """Display investment recommendation."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        signal = analysis.recommendation.signal.value
        color = "green" if signal == "BUY" else ("orange" if signal == "HOLD" else "red")
        st.metric(
            "Recommendation",
            signal,
            f"Confidence: {analysis.recommendation.confidence:.0%}",
        )
    
    with col2:
        st.metric(
            "Expected Return (Base)",
            f"{analysis.expected_returns.get('base', 0):.1f}%",
        )
    
    with col3:
        st.metric(
            "Bull Case",
            f"{analysis.expected_returns.get('bull', 0):.1f}%",
        )
    
    with col4:
        st.metric(
            "Bear Case",
            f"{analysis.expected_returns.get('bear', 0):.1f}%",
        )
    
    st.subheader("Recommendation Rationale")
    st.write(analysis.recommendation.reasoning)
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Key Drivers:**")
        for driver in analysis.recommendation.key_drivers:
            st.write(f"• {driver}")
    
    with col2:
        st.write("**Risk Level:**")
        risk_color = "🟢" if analysis.risk_analysis.overall_risk_level.value == "LOW" else (
            "🟡" if analysis.risk_analysis.overall_risk_level.value == "MEDIUM" else "🔴"
        )
        st.write(f"{risk_color} {analysis.risk_analysis.overall_risk_level.value}")


def display_trading_outlook(analysis):
    """Display swing trade and long-term outlook."""
    st.subheader("Trading Outlook")
    
    # Highlight if swing trade qualifies
    if analysis.swing_trade.opportunity_exists:
        st.success("🟢 **SWING TRADE OPPORTUNITY IDENTIFIED!** This stock qualifies for swing trading (12%+ return, 1-2 months)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Swing Trade Opportunity**")
        if analysis.swing_trade.opportunity_exists:
            st.success("✓ QUALIFIED! Meets all criteria for swing trading")
            
            # Display confidence score prominently
            confidence = analysis.swing_trade.confidence_score or 0
            col_conf1, col_conf2 = st.columns(2)
            with col_conf1:
                st.metric("Confidence Score", f"{confidence:.0f}%", delta=f"+{max(0, confidence - 80):.0f}% above min")
            with col_conf2:
                st.metric("Target Return", f"{analysis.swing_trade.target_return_percent:.1f}%", 
                         delta=f"+{max(0, analysis.swing_trade.target_return_percent - 12):.1f}% above min")
            
            st.write(f"Entry Zone: {analysis.swing_trade.entry_zone_low:.2f} - {analysis.swing_trade.entry_zone_high:.2f}")
            st.write(f"Target: {analysis.swing_trade.target_low:.2f} - {analysis.swing_trade.target_high:.2f}")
            st.write(f"Stop Loss: {analysis.swing_trade.stop_loss_price:.2f}")
            st.write(f"Timeframe: {analysis.swing_trade.timeframe_days} days (~1-2 months)")
            st.caption(analysis.swing_trade.commentary)
            
            # Display swing trade chart
            chart = ChartGenerator.create_swing_trade_chart(
                analysis.ticker,
                analysis.metrics.current_price,
                analysis.swing_trade.entry_zone_low,
                analysis.swing_trade.entry_zone_high,
                analysis.swing_trade.target_low,
                analysis.swing_trade.target_high,
                analysis.swing_trade.stop_loss_price,
            )
            if chart:
                st.plotly_chart(chart, use_container_width=True)
        else:
            st.info("⚠️ No qualifying opportunity at this time")
            confidence = analysis.swing_trade.confidence_score or 0
            return_pct = analysis.swing_trade.target_return_percent or 0
            
            col_missing1, col_missing2 = st.columns(2)
            with col_missing1:
                if confidence < 80:
                    st.error(f"Confidence too low: {confidence:.0f}% (need ≥80%)")
            with col_missing2:
                if return_pct < 12:
                    st.error(f"Return too low: {return_pct:.1f}% (need ≥12%)")
            
            st.write(analysis.swing_trade.commentary)
    
    with col2:
        st.write("**Long-Term Outlook (3-Year)**")
        st.write(f"Target Range: {analysis.long_term.target_price_low:.2f} - {analysis.long_term.target_price_high:.2f}")
        st.write(f"Base Case Return: **{analysis.long_term.base_case_return:.1f}%**")
        st.write(f"Bull Case: {analysis.long_term.bull_case_return:.1f}%")
        st.write(f"Bear Case: {analysis.long_term.bear_case_return:.1f}%")
        st.caption(analysis.long_term.commentary)
    
    # Price projection chart (1-2 years)
    st.subheader("📈 Price Projection Chart (1-2 Years)")
    projection_chart = ChartGenerator.create_price_projection_chart(
        analysis.ticker,
        analysis.metrics.current_price,
        {
            "target_high": analysis.long_term.target_price_high or analysis.metrics.current_price * 1.25,
            "target_low": analysis.long_term.target_price_low or analysis.metrics.current_price * 0.85,
            "bull": analysis.long_term.bull_case_return or 0.30,
            "bear": analysis.long_term.bear_case_return or -0.20,
            "base": analysis.long_term.base_case_return or 0.15,
        },
        None,  # No historical prices needed here
    )
    if projection_chart:
        st.plotly_chart(projection_chart, use_container_width=True)


def display_risk_analysis(analysis):
    """Display comprehensive risk analysis."""
    st.subheader("Risk Analysis")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Overall Risk", analysis.risk_analysis.overall_risk_level.value)
    
    with col2:
        st.metric("Volatility Risk", analysis.risk_analysis.volatility_risk.value)
    
    with col3:
        st.metric("Business Risk", analysis.risk_analysis.business_risk.value)
    
    with col4:
        st.metric("Market Risk", analysis.risk_analysis.market_risk.value)
    
    st.write("**Downside Triggers:**")
    for trigger in analysis.risk_analysis.downside_triggers[:5]:
        st.write(f"• {trigger}")
    
    st.write("**Key Uncertainties:**")
    for note in analysis.risk_analysis.uncertainty_notes[:5]:
        st.write(f"• {note}")
    
    st.caption(analysis.risk_analysis.summary)


# Main UI
st.title("📈 Stock Research AI")
st.markdown("Powered by Groq LLM, Yahoo Finance, and Screener.in")

# Disclaimer
with st.expander("⚠️ IMPORTANT DISCLAIMER", expanded=False):
    st.warning(
        "**THIS IS EDUCATIONAL CONTENT ONLY.** This application is for informational purposes and does NOT constitute investment advice. "
        "Analysis is based on historical data and AI-generated insights. Past performance does not guarantee future results. "
        "Markets involve significant risk of loss. **Always consult a qualified financial advisor before making investment decisions.**"
    )

# Sidebar for search and history
with st.sidebar:
    st.header("Search & History")
    
    # Search input
    search_query = st.text_input(
        "Search stock by name or ticker",
        placeholder="e.g., Apple, Reliance, AAPL, RELIANCE.NS",
        help="Enter company name (Apple, Reliance) or ticker (AAPL, RELIANCE.NS)"
    ).strip()
    
    # Auto-complete suggestions
    if search_query and len(search_query) >= 2:
        suggestions = CompanyLookup.get_suggestions(search_query, limit=5)
        if suggestions:
            st.write("**Suggestions:**")
            for i, (company_name, ticker) in enumerate(suggestions):
                if st.button(f"{company_name} ({ticker})", key=f"suggest_{ticker}_{i}"):
                    search_query = ticker
                    search_button = True
    
    # Resolve company name to ticker
    ticker = CompanyLookup.lookup(search_query) if search_query else ""
    ticker = ticker.upper().strip() if ticker else ""
    
    search_button = st.button("🔍 Research", key="search_btn", type="primary")
    
    # Show history
    st.subheader("Recent Searches")
    history = st.session_state.agent.history_store.get_history()
    
    if history:
        for search in history[:Config.MAX_SEARCH_HISTORY]:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                if st.button(
                    f"{search.ticker} - {search.company_name or ''}",
                    key=f"hist_{search.id}",
                    use_container_width=True,
                ):
                    ticker = search.ticker
                    search_button = True
            
            with col2:
                if search.recommendation:
                    rec_emoji = "🟢" if search.recommendation == Recommendation.BUY else (
                        "🟡" if search.recommendation == Recommendation.HOLD else "🔴"
                    )
                    st.write(rec_emoji)
    else:
        st.info("No search history yet")
    
    # Clear history button
    if st.button("Clear History", use_container_width=True):
        st.session_state.agent.history_store.clear_history()
        st.rerun()

# Main content area
if search_button and ticker:
    st.session_state.research_in_progress = True
    
    # Progress placeholder
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    
    # Run research
    with progress_placeholder.container():
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    # Execute research
    analysis, progress = st.session_state.agent.research_stock(ticker)
    
    # Update progress
    progress_bar.progress(progress.percentage / 100)
    status_text.write(progress.message or progress.stage)
    
    if progress.is_complete:
        progress_placeholder.empty()
    
    if analysis:
        st.session_state.last_analysis = analysis
        
        st.success(f"✓ Research complete for {ticker}")
        
        # Main content tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Overview", "Financials", "Recommendation", "Trading", "Risk"]
        )
        
        with tab1:
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("Current Price", f"{analysis.metrics.current_price:.2f} {analysis.metrics.currency}")
            with col2:
                st.metric("Market Cap", f"${analysis.metrics.market_cap/1e9:.1f}B" if analysis.metrics.market_cap else "N/A")
            with col3:
                st.metric("PE Ratio", f"{analysis.metrics.pe_ratio:.1f}" if analysis.metrics.pe_ratio else "N/A")
            with col4:
                st.metric("52W High", f"{analysis.metrics.week_52_high:.2f}" if analysis.metrics.week_52_high else "N/A")
            with col5:
                st.metric("52W Low", f"{analysis.metrics.week_52_low:.2f}" if analysis.metrics.week_52_low else "N/A")
            
            st.subheader("Growth Analysis")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Revenue Trend:** {analysis.growth_trend.revenue_trend}")
            with col2:
                st.write(f"**Profitability:** {analysis.growth_trend.profitability_trend}")
            with col3:
                st.write(f"**OPM Trend:** {analysis.growth_trend.opm_trend}")
            
            st.info(analysis.growth_trend.summary)
        
        with tab2:
            st.subheader("3-Year Financial Summary")
            display_financial_table(analysis)
            
            if analysis.financial_history:
                # Financial trend chart
                fin_chart = ChartGenerator.create_financial_trend_chart(
                    analysis.ticker,
                    analysis.financial_history
                )
                if fin_chart:
                    st.plotly_chart(fin_chart, use_container_width=True)
            
            if analysis.recent_announcements:
                st.subheader("Recent Announcements")
                for ann in analysis.recent_announcements[:5]:
                    with st.expander(f"{ann.date.strftime('%Y-%m-%d')} - {ann.title}"):
                        st.write(ann.content or "No content available")
        
        with tab3:
            display_recommendation(analysis)
        
        with tab4:
            display_trading_outlook(analysis)
        
        with tab5:
            display_risk_analysis(analysis)
        
        # Download report
        st.divider()
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📥 View Report", use_container_width=True):
                st.info(f"Reports saved to: {Config.REPORTS_DIR / ticker.replace('.', '_')}")
        
        with col2:
            st.write("")  # Spacer
        
        with col3:
            st.write("")  # Spacer
    
    elif progress.error:
        st.error(f"Research failed: {progress.error}")
    
    st.session_state.research_in_progress = False

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: gray; font-size: 0.8em;'>
    Stock Research AI v0.1.0 | Data sources: Yahoo Finance, Screener.in | Powered by Groq LLM
</div>
""", unsafe_allow_html=True)
