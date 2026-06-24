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
from src.storage.portfolio_store import PortfolioStore

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
    .profit {
        color: #09ab15;
        font-weight: bold;
    }
    .loss {
        color: #d74e09;
        font-weight: bold;
    }
    .portfolio-holding {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 8px;
        margin-bottom: 6px;
        border-left: 3px solid #dee2e6;
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

if "portfolio_store" not in st.session_state:
    st.session_state.portfolio_store = PortfolioStore()

if "sell_form_open" not in st.session_state:
    st.session_state.sell_form_open = {}  # holding_id -> bool

if "portfolio_tab" not in st.session_state:
    st.session_state.portfolio_tab = "active"  # "active" or "sold"


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


def display_portfolio_panel():
    """Render the portfolio management panel."""
    store: PortfolioStore = st.session_state.portfolio_store

    st.markdown("## 💼 My Portfolio")
    st.divider()

    # ── Add Stock Form ──────────────────────────────────────────────
    with st.expander("➕ Add Stock to Portfolio", expanded=False):
        with st.form("add_stock_form", clear_on_submit=True):
            ticker_input = st.text_input("Ticker Symbol", placeholder="e.g. AAPL, RELIANCE.NS")
            company_input = st.text_input("Company Name", placeholder="e.g. Apple Inc.")
            qty_input = st.number_input("Quantity", min_value=0.001, step=1.0, format="%.3f")
            price_input = st.number_input("Buying Price", min_value=0.01, step=0.01, format="%.2f")
            currency_input = st.selectbox("Currency", ["INR", "USD", "EUR", "GBP", "JPY", "CAD", "AUD"])
            submitted = st.form_submit_button("Add to Portfolio", use_container_width=True)

            if submitted:
                t = ticker_input.strip().upper()
                c = company_input.strip()
                if not t:
                    st.error("Ticker is required.")
                elif qty_input <= 0:
                    st.error("Quantity must be greater than 0.")
                elif price_input <= 0:
                    st.error("Buying price must be greater than 0.")
                else:
                    if not c:
                        c = t
                    store.add_holding(t, c, qty_input, price_input, currency_input)
                    st.success(f"Added {t} × {qty_input} @ {price_input:.2f}")
                    st.rerun()

    # ── Load & enrich holdings ──────────────────────────────────────
    all_holdings = store.get_all_holdings()
    active_holdings = [h for h in all_holdings if not h.is_sold]
    sold_holdings = [h for h in all_holdings if h.is_sold]

    # Enrich active holdings with live prices
    if active_holdings:
        active_holdings = store.enrich_with_prices(active_holdings)

    # ── Portfolio Summary ───────────────────────────────────────────
    summary = store.compute_summary(active_holdings + sold_holdings)

    if all_holdings:
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Total Invested", f"{summary.total_invested:,.2f}")
        with col_b:
            pl_label = "▲ Profit" if summary.total_pl >= 0 else "▼ Loss"
            pl_pct = summary.total_pl_pct
            st.metric(
                "Overall P&L",
                f"{summary.total_pl:+,.2f}",
                delta=f"{pl_pct:+.2f}%",
                delta_color="normal",
            )

        col_c, col_d = st.columns(2)
        with col_c:
            st.metric(
                "Unrealized P&L",
                f"{summary.unrealized_pl:+,.2f}",
                delta=f"{summary.unrealized_pl_pct:+.2f}%",
                delta_color="normal",
            )
        with col_d:
            realized_color = "🟢" if summary.realized_pl >= 0 else "🔴"
            st.metric(
                "Realized P&L (Sold)",
                f"{realized_color} {summary.realized_pl:+,.2f}",
            )

        st.divider()

    # ── Tabs: Active / Sold ─────────────────────────────────────────
    tab_active, tab_sold = st.tabs([f"Active ({len(active_holdings)})", f"Sold ({len(sold_holdings)})"])

    with tab_active:
        if not active_holdings:
            st.info("No active holdings. Add a stock above.")
        else:
            for h in active_holdings:
                pl_pct = h.unrealized_pl_pct
                pl_val = h.unrealized_pl
                pl_emoji = "🟢" if pl_pct >= 0 else "🔴"
                border_color = "#09ab15" if pl_pct >= 0 else "#d74e09"

                st.markdown(
                    f"<div style='border-left:3px solid {border_color}; padding:6px 8px; "
                    f"background:#f8f9fa; border-radius:6px; margin-bottom:4px;'>"
                    f"<b>{h.ticker}</b> — {h.company_name}<br/>"
                    f"Qty: {h.quantity:g} | Buy: {h.buying_price:.2f} | "
                    f"Now: {f'{h.current_price:.2f}' if h.current_price else '—'}<br/>"
                    f"{pl_emoji} P&L: <b>{pl_val:+,.2f}</b> ({pl_pct:+.2f}%)"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                btn_col, form_col = st.columns([1, 2])
                with btn_col:
                    toggle_key = f"sell_toggle_{h.id}"
                    if st.button("Sell", key=f"sell_btn_{h.id}", use_container_width=True):
                        st.session_state.sell_form_open[h.id] = not st.session_state.sell_form_open.get(h.id, False)
                        st.rerun()

                    if st.button("Remove", key=f"del_btn_{h.id}", use_container_width=True):
                        store.delete_holding(h.id)
                        st.rerun()

                # Sell price form (shown inline when toggled)
                if st.session_state.sell_form_open.get(h.id, False):
                    with st.form(f"sell_form_{h.id}", clear_on_submit=True):
                        suggested = h.current_price or h.buying_price
                        sell_price = st.number_input(
                            "Sell Price",
                            value=float(f"{suggested:.2f}"),
                            min_value=0.01,
                            step=0.01,
                            format="%.2f",
                            key=f"sell_price_{h.id}",
                        )
                        confirm = st.form_submit_button("Confirm Sell", use_container_width=True)
                        if confirm:
                            store.sell_holding(h.id, sell_price)
                            st.session_state.sell_form_open[h.id] = False
                            realized = (sell_price - h.buying_price) * h.quantity
                            emoji = "🟢" if realized >= 0 else "🔴"
                            st.success(f"{emoji} Sold {h.ticker} — Realized P&L: {realized:+,.2f}")
                            st.rerun()

    with tab_sold:
        if not sold_holdings:
            st.info("No sold positions yet.")
        else:
            total_realized = sum(h.realized_pl for h in sold_holdings)
            emoji = "🟢" if total_realized >= 0 else "🔴"
            st.markdown(f"**Total Realized: {emoji} {total_realized:+,.2f}**")
            st.divider()

            for h in sold_holdings:
                pl_val = h.realized_pl
                pl_pct = h.realized_pl_pct
                pl_emoji = "🟢" if pl_val >= 0 else "🔴"
                border_color = "#09ab15" if pl_val >= 0 else "#d74e09"
                sell_dt = h.sell_date.strftime("%Y-%m-%d") if h.sell_date else "—"

                st.markdown(
                    f"<div style='border-left:3px solid {border_color}; padding:6px 8px; "
                    f"background:#f8f9fa; border-radius:6px; margin-bottom:4px;'>"
                    f"<b>{h.ticker}</b> — {h.company_name}<br/>"
                    f"Qty: {h.quantity:g} | Buy: {h.buying_price:.2f} → Sell: {h.sell_price:.2f}<br/>"
                    f"{pl_emoji} P&L: <b>{pl_val:+,.2f}</b> ({pl_pct:+.2f}%) | Sold: {sell_dt}"
                    f"</div>",
                    unsafe_allow_html=True,
                )


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

# Two-column layout: research area (left) + portfolio (right)
main_col, portfolio_col = st.columns([3, 1.3], gap="large")

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

# ── Main research content ────────────────────────────────────────────────
with main_col:
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

            # Quick-add to portfolio button
            with st.expander("➕ Add to Portfolio", expanded=False):
                with st.form("quick_add_form", clear_on_submit=True):
                    qa_qty = st.number_input("Quantity", min_value=0.001, step=1.0, format="%.3f", key="qa_qty")
                    qa_price = st.number_input(
                        "Buying Price",
                        value=float(f"{analysis.metrics.current_price:.2f}"),
                        min_value=0.01,
                        step=0.01,
                        format="%.2f",
                        key="qa_price",
                    )
                    if st.form_submit_button("Add to Portfolio", use_container_width=True):
                        st.session_state.portfolio_store.add_holding(
                            ticker=analysis.ticker,
                            company_name=analysis.metrics.company_name or analysis.ticker,
                            quantity=qa_qty,
                            buying_price=qa_price,
                            currency=analysis.metrics.currency or "INR",
                            auto_resolve=False,  # ticker from research is already resolved
                        )
                        st.success(f"Added {analysis.ticker} to portfolio!")
                        st.rerun()

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

            # Report link
            st.divider()
            if st.button("📥 View Report", use_container_width=False):
                st.info(f"Reports saved to: {Config.REPORTS_DIR / ticker.replace('.', '_')}")

        elif progress.error:
            st.error(f"Research failed: {progress.error}")

        st.session_state.research_in_progress = False

    # Footer inside main column
    st.divider()
    st.markdown("""
<div style='text-align: center; color: gray; font-size: 0.8em;'>
    Stock Research AI v0.1.0 | Data sources: Yahoo Finance, Screener.in | Powered by Groq LLM
</div>
""", unsafe_allow_html=True)

# ── Portfolio panel ──────────────────────────────────────────────────────
with portfolio_col:
    display_portfolio_panel()

