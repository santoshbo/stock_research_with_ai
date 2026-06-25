"""Streamlit UI for stock research application."""

from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from src.app import StockResearchAgent
from src.models.research import Recommendation
from src.config import Config
from src.tools.company_lookup import CompanyLookup
from src.tools.charts import ChartGenerator
from src.storage.portfolio_store import PortfolioStore

# Configure Streamlit page
st.set_page_config(
    page_title="Stock Research With AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    :root {
        --app-font-size: 16px;
        --portfolio-font-size: 0.9rem;
    }

    .main {
        max-width: 1200px;
    }

    html, body, [data-testid="stAppViewContainer"] {
        font-size: var(--app-font-size);
    }

    [data-testid="stAppViewContainer"] .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.1rem;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
    }

    [data-testid="stMetricDelta"] {
        font-size: 0.8rem;
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
        font-size: var(--portfolio-font-size);
        line-height: 1.35;
    }

    @media (max-width: 1200px) {
        :root {
            --app-font-size: 15px;
            --portfolio-font-size: 0.85rem;
        }

        [data-testid="stAppViewContainer"] .block-container {
            padding-left: 0.75rem;
            padding-right: 0.75rem;
        }
    }

    @media (max-width: 900px) {
        :root {
            --app-font-size: 14px;
            --portfolio-font-size: 0.82rem;
        }

        [data-testid="stHorizontalBlock"] {
            gap: 0.5rem;
        }

        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }
    }

    @media (max-width: 640px) {
        [data-testid="stMetricValue"] {
            font-size: 1rem;
        }

        [data-testid="stTabs"] [data-baseweb="tab"] {
            font-size: 0.82rem;
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
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

if "portfolio_snapshot" not in st.session_state:
    st.session_state.portfolio_snapshot = None

if "auto_refresh_minutes" not in st.session_state:
    st.session_state.auto_refresh_minutes = 15

if "show_read_target_alerts" not in st.session_state:
    st.session_state.show_read_target_alerts = False


AUTO_REFRESH_DEFAULT_MINUTES = 15


PORTFOLIO_TYPE_LABELS = {
    "SWING_TRADE": "Swing Trade",
    "MIDTERM": "Midterm",
    "LONG_TERM": "Long Term",
}
PORTFOLIO_TYPE_BY_LABEL = {v: k for k, v in PORTFOLIO_TYPE_LABELS.items()}

BROKER_ACCOUNT_LABELS = {
    "ZERODHA": "Zerodha",
    "5PAISA": "5Paisa",
    "UPSTOX": "Upstox",
}
BROKER_ACCOUNT_BY_LABEL = {v: k for k, v in BROKER_ACCOUNT_LABELS.items()}


def enable_auto_refresh(interval_ms: int) -> None:
    """Trigger a full-page refresh at a fixed interval."""
    components.html(
        f"""
        <script>
            setTimeout(function() {{
                window.parent.location.reload();
            }}, {int(interval_ms)});
        </script>
        """,
        height=0,
        width=0,
    )


def build_portfolio_snapshot():
    """Load holdings, apply defaults, and enrich active positions with live prices."""
    store: PortfolioStore = st.session_state.portfolio_store

    all_holdings = store.get_all_holdings()
    for h in all_holdings:
        if not h.portfolio_type:
            h.portfolio_type = "MIDTERM"
        if not h.broker_account:
            h.broker_account = "ZERODHA"

    active_holdings = [h for h in all_holdings if not h.is_sold]
    sold_holdings = [h for h in all_holdings if h.is_sold]

    if active_holdings:
        active_holdings = store.enrich_with_prices(active_holdings)

    snapshot = {
        "all_holdings": active_holdings + sold_holdings,
        "active_holdings": active_holdings,
        "sold_holdings": sold_holdings,
        "refreshed_at": datetime.now(),
    }
    st.session_state.portfolio_snapshot = snapshot
    return snapshot


def _build_target_alert_message(holding, target_level: int) -> str:
    target_price = holding.target_1_price if target_level == 1 else holding.target_2_price
    label = "1st" if target_level == 1 else "2nd"
    msg = f"{holding.ticker}: {label} target hit"
    if target_price is not None:
        msg += f" ({target_price:.2f})"
    if holding.current_price is not None:
        msg += f" | Current: {holding.current_price:.2f}"
    return msg


def render_target_hit_notifications(active_holdings, show_read: bool = False):
    """Show unread target-hit notifications, with optional read history."""
    unread_events = []
    read_events = []

    for holding in active_holdings:
        if holding.target_1_achieved and holding.partial_sold_quantity <= 0:
            evt = (
                holding.target_1_achieved_at or datetime.min,
                _build_target_alert_message(holding, 1),
                bool(holding.target_1_notified),
            )
            if evt[2]:
                read_events.append(evt)
            else:
                unread_events.append(evt)

        if holding.target_2_achieved:
            evt = (
                holding.target_2_achieved_at or datetime.min,
                _build_target_alert_message(holding, 2),
                bool(holding.target_2_notified),
            )
            if evt[2]:
                read_events.append(evt)
            else:
                unread_events.append(evt)

    unread_events.sort(key=lambda x: x[0], reverse=True)
    read_events.sort(key=lambda x: x[0], reverse=True)

    if unread_events:
        alert_text = "\n".join([f"- {msg}" for _, msg, _ in unread_events])
        left, right = st.columns([4, 1])
        with left:
            st.success(f"🎯 New Target Alerts\n{alert_text}")
        with right:
            if st.button("Mark Read", key="mark_target_alerts_read", use_container_width=True):
                st.session_state.portfolio_store.mark_all_target_alerts_read()
                st.rerun()

    if show_read and read_events:
        read_text = "\n".join([f"- {msg}" for _, msg, _ in read_events[:10]])
        st.info(f"✅ Read Target Alerts\n{read_text}")

    return {"unread": len(unread_events), "read": len(read_events)}


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
            "Revenue": f"₹{fy.sales_revenue/1e7:.2f}Cr" if fy.sales_revenue else "N/A",
            "Op. Profit": f"₹{fy.operating_profit/1e7:.2f}Cr" if fy.operating_profit else "N/A",
            "OPM %": f"{fy.opm:.2f}%" if fy.opm else "N/A",
            "Net Profit": f"₹{fy.net_profit/1e7:.2f}Cr" if fy.net_profit else "N/A",
            "PBT": f"₹{fy.profit_before_tax/1e7:.2f}Cr" if fy.profit_before_tax else "N/A",
        })
    
    df = pd.DataFrame(rows)
    st.table(df)


def display_recommendation(analysis):
    """Display investment recommendation."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        signal = analysis.recommendation.signal.value
        st.metric(
            "Recommendation",
            signal,
            f"Confidence: {analysis.recommendation.confidence:.2%}",
        )
    
    with col2:
        st.metric(
            "Expected Return (Base)",
            f"{analysis.expected_returns.get('base', 0):.2f}%",
        )
    
    with col3:
        st.metric(
            "Bull Case",
            f"{analysis.expected_returns.get('bull', 0):.2f}%",
        )
    
    with col4:
        st.metric(
            "Bear Case",
            f"{analysis.expected_returns.get('bear', 0):.2f}%",
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
                st.metric("Confidence Score", f"{confidence:.2f}%", delta=f"+{max(0, confidence - 80):.2f}% above min")
            with col_conf2:
                st.metric("Target Return", f"{analysis.swing_trade.target_return_percent:.2f}%", 
                         delta=f"+{max(0, analysis.swing_trade.target_return_percent - 12):.2f}% above min")
            
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
                    st.error(f"Confidence too low: {confidence:.2f}% (need ≥80%)")
            with col_missing2:
                if return_pct < 12:
                    st.error(f"Return too low: {return_pct:.2f}% (need ≥12%)")
            
            st.write(analysis.swing_trade.commentary)
    
    with col2:
        st.write("**Long-Term Outlook (3-Year)**")
        st.write(f"Target Range: {analysis.long_term.target_price_low:.2f} - {analysis.long_term.target_price_high:.2f}")
        st.write(f"Base Case Return: **{analysis.long_term.base_case_return:.2f}%**")
        st.write(f"Bull Case: {analysis.long_term.bull_case_return:.2f}%")
        st.write(f"Bear Case: {analysis.long_term.bear_case_return:.2f}%")
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

    if "partial_sell_form_open" not in st.session_state:
        st.session_state.partial_sell_form_open = {}
    if "duplicate_add_context" not in st.session_state:
        st.session_state.duplicate_add_context = None

    def _parse_positive_float(raw: str, field_name: str) -> float:
        val = (raw or "").strip()
        if not val:
            raise ValueError(f"{field_name} is required.")
        try:
            num = float(val)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a valid number.") from exc
        if num <= 0:
            raise ValueError(f"{field_name} must be greater than 0.")
        return num

    def _parse_optional_positive_float(raw: str, field_name: str):
        val = (raw or "").strip()
        if not val:
            return None
        try:
            num = float(val)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a valid number.") from exc
        if num <= 0:
            raise ValueError(f"{field_name} must be greater than 0 when provided.")
        return num

    st.markdown("## 💼 My Portfolio")
    st.divider()

    # ── Add Stock Form ──────────────────────────────────────────────
    with st.expander("➕ Add Stock to Portfolio", expanded=False):
        st.caption("Investment date is auto-set to today's date when you add a stock.")
        with st.form("add_stock_form", clear_on_submit=True):
            ticker_input = st.text_input("Ticker Symbol", placeholder="e.g. AAPL, RELIANCE.NS")
            company_input = st.text_input("Company Name", placeholder="e.g. Apple Inc.")
            qty_input = st.text_input("Quantity", placeholder="e.g. 10")
            price_input = st.text_input("Buying Price", placeholder="e.g. 1250.50")
            portfolio_label_input = st.selectbox(
                "Portfolio",
                ["Swing Trade", "Midterm", "Long Term"],
            )
            broker_label_input = st.selectbox(
                "Broker Account",
                ["Zerodha", "5Paisa", "Upstox"],
            )
            target_1_input = st.text_input(
                "1st Target Price (Optional)",
                placeholder="e.g. 1400",
                help="Set 0 to skip",
            )
            target_2_input = st.text_input(
                "2nd Target Price (Optional)",
                placeholder="e.g. 1550",
                help="Set 0 to skip",
            )
            currency_input = st.selectbox("Currency", ["INR", "USD", "EUR", "GBP", "JPY", "CAD", "AUD"])
            submitted = st.form_submit_button("Add to Portfolio", use_container_width=True)

            if submitted:
                t = ticker_input.strip().upper()
                c = company_input.strip()
                if not t:
                    st.error("Ticker is required.")
                else:
                    try:
                        qty_val = _parse_positive_float(qty_input, "Quantity")
                        price_val = _parse_positive_float(price_input, "Buying price")
                        target_1_val = _parse_optional_positive_float(target_1_input, "1st target price")
                        target_2_val = _parse_optional_positive_float(target_2_input, "2nd target price")

                        if target_2_val is not None and target_1_val is None:
                            st.error("Please set 1st target before 2nd target.")
                        elif (
                            target_1_val is not None
                            and target_2_val is not None
                            and target_2_val <= target_1_val
                        ):
                            st.error("2nd target should be greater than 1st target.")
                        else:
                            if not c:
                                c = t
                            portfolio_code = PORTFOLIO_TYPE_BY_LABEL[portfolio_label_input]
                            broker_code = BROKER_ACCOUNT_BY_LABEL[broker_label_input]

                            existing = store.find_matching_active_holding(
                                ticker=t,
                                portfolio_type=portfolio_code,
                                broker_account=broker_code,
                                currency=currency_input,
                                auto_resolve=True,
                            )

                            if existing:
                                st.session_state.duplicate_add_context = {
                                    "holding_id": existing.id,
                                    "ticker": existing.ticker,
                                    "company_name": existing.company_name,
                                    "portfolio_label": portfolio_label_input,
                                    "broker_label": broker_label_input,
                                    "currency": currency_input,
                                    "default_qty": qty_val,
                                    "default_price": price_val,
                                }
                                st.warning(
                                    f"{existing.ticker} is already in portfolio "
                                    f"({portfolio_label_input} / {broker_label_input} / {currency_input}). "
                                    "Use the form below to add more quantity."
                                )
                            else:
                                store.add_holding(
                                    t,
                                    c,
                                    qty_val,
                                    price_val,
                                    currency_input,
                                    target_1_price=target_1_val,
                                    target_2_price=target_2_val,
                                    portfolio_type=portfolio_code,
                                    broker_account=broker_code,
                                )
                                st.success(f"Added {t} × {qty_val:.2f} @ {price_val:.2f}")
                                st.rerun()
                    except ValueError as err:
                        st.error(str(err))

    if st.session_state.duplicate_add_context:
        dup = st.session_state.duplicate_add_context
        st.info(
            f"Stock already added: {dup['ticker']} | Portfolio: {dup['portfolio_label']} | "
            f"Broker: {dup['broker_label']} | Currency: {dup['currency']}"
        )
        with st.form("duplicate_add_more_form", clear_on_submit=True):
            add_more_qty_raw = st.text_input(
                "Add More Quantity",
                value=f"{dup['default_qty']:.2f}",
                placeholder="e.g. 10",
            )
            add_more_price_raw = st.text_input(
                "Buying Price",
                value=f"{dup['default_price']:.2f}",
                placeholder="e.g. 1250.50",
            )
            c1, c2 = st.columns(2)
            with c1:
                confirm_add_more = st.form_submit_button("Yes, Add More", use_container_width=True)
            with c2:
                cancel_add_more = st.form_submit_button("Cancel", use_container_width=True)

            if cancel_add_more:
                st.session_state.duplicate_add_context = None
                st.rerun()

            if confirm_add_more:
                try:
                    add_qty = _parse_positive_float(add_more_qty_raw, "Quantity")
                    add_price = _parse_positive_float(add_more_price_raw, "Buying price")
                    ok, new_qty, new_avg = store.add_more_to_holding(
                        holding_id=int(dup["holding_id"]),
                        additional_quantity=add_qty,
                        additional_buying_price=add_price,
                    )
                    if ok and new_qty is not None and new_avg is not None:
                        st.success(
                            f"Updated {dup['ticker']}: Qty={new_qty:.2f}, Avg Buy={new_avg:.2f}"
                        )
                        st.session_state.duplicate_add_context = None
                        st.rerun()
                    else:
                        st.error("Could not update existing holding. Try again.")
                except ValueError as err:
                    st.error(str(err))

    # ── Load & enrich holdings ──────────────────────────────────────
    snapshot = st.session_state.get("portfolio_snapshot")
    if snapshot:
        all_holdings = snapshot["all_holdings"]
        active_holdings = snapshot["active_holdings"]
        sold_holdings = snapshot["sold_holdings"]
    else:
        all_holdings = store.get_all_holdings()
        for h in all_holdings:
            if not h.portfolio_type:
                h.portfolio_type = "MIDTERM"
            if not h.broker_account:
                h.broker_account = "ZERODHA"

        active_holdings = [h for h in all_holdings if not h.is_sold]
        sold_holdings = [h for h in all_holdings if h.is_sold]

        if active_holdings:
            active_holdings = store.enrich_with_prices(active_holdings)

    # ── Portfolio Summary ───────────────────────────────────────────
    summary = store.compute_summary(active_holdings + sold_holdings)

    if all_holdings:
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Total Invested", f"{summary.total_invested:,.2f}")
        with col_b:
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

        st.markdown("#### Portfolio Buckets")
        bucket_cols = st.columns(3)
        for idx, (ptype, plabel) in enumerate(PORTFOLIO_TYPE_LABELS.items()):
            bucket_holdings = [h for h in (active_holdings + sold_holdings) if (h.portfolio_type or "MIDTERM") == ptype]
            bucket_summary = store.compute_summary(bucket_holdings)
            with bucket_cols[idx]:
                st.markdown(f"**{plabel} ({len(bucket_holdings)})**")
                st.metric("Invested", f"{bucket_summary.total_invested:,.2f}")
                st.metric(
                    "Profit/Loss",
                    f"{bucket_summary.total_pl:+,.2f}",
                    delta=f"{bucket_summary.total_pl_pct:+.2f}%",
                    delta_color="normal",
                )

        st.divider()

    portfolio_filter_label = st.selectbox(
        "View Portfolio",
        ["All", "Swing Trade", "Midterm", "Long Term"],
        key="portfolio_type_filter",
    )
    if portfolio_filter_label != "All":
        selected_type = PORTFOLIO_TYPE_BY_LABEL[portfolio_filter_label]
        active_holdings = [h for h in active_holdings if (h.portfolio_type or "MIDTERM") == selected_type]
        sold_holdings = [h for h in sold_holdings if (h.portfolio_type or "MIDTERM") == selected_type]

    partial_sold_holdings = [h for h in active_holdings if h.partial_sold_quantity > 0]

    def _render_partial_sell_confirm_form(holding, sell_percent: float, default_qty: int, form_key_prefix: str):
        """Render confirmation form for partial sells with editable qty and price."""
        open_key = f"partial_sell_open_{form_key_prefix}_{holding.id}_{int(sell_percent)}"
        if not st.session_state.partial_sell_form_open.get(open_key, False):
            return

        max_qty = int(max(0, round(holding.remaining_quantity)))
        if max_qty <= 0:
            st.warning("No remaining whole shares available to sell.")
            st.session_state.partial_sell_form_open[open_key] = False
            return

        default_qty = min(max(1, int(default_qty)), max_qty)
        suggested_price = float(f"{(holding.current_price or holding.buying_price):.2f}")

        with st.form(f"partial_sell_form_{form_key_prefix}_{holding.id}_{int(sell_percent)}", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                sell_qty = st.number_input(
                    f"Confirm share quantity for {holding.ticker}",
                    min_value=1,
                    max_value=max_qty,
                    value=default_qty,
                    step=1,
                    key=f"partial_qty_{form_key_prefix}_{holding.id}_{int(sell_percent)}",
                )
            with c2:
                sell_price = st.number_input(
                    f"Confirm sell price for {holding.ticker}",
                    min_value=0.01,
                    value=suggested_price,
                    step=0.01,
                    format="%.2f",
                    key=f"partial_price_{form_key_prefix}_{holding.id}_{int(sell_percent)}",
                )

            a1, a2 = st.columns(2)
            with a1:
                confirm = st.form_submit_button(f"Confirm Sell {int(sell_percent)}%", use_container_width=True)
            with a2:
                cancel = st.form_submit_button("Cancel", use_container_width=True)

            if cancel:
                st.session_state.partial_sell_form_open[open_key] = False
                st.rerun()

            if confirm:
                ok, sold_qty, realized = store.partially_sell_holding(
                    holding.id,
                    sell_percent,
                    sell_quantity=float(sell_qty),
                    sell_price=float(sell_price),
                )
                st.session_state.partial_sell_form_open[open_key] = False
                if ok:
                    st.success(
                        f"Sold {int(round(sold_qty))} of {holding.ticker} @ {float(sell_price):.2f}. "
                        f"Realized P&L: {realized:+,.2f}"
                    )
                    st.rerun()
                else:
                    st.error("Could not execute partial sell. Try again.")

    def _render_compact_holdings_table(holdings, sold: bool = False):
        """Render a dense, paginated table view for easier scanning of many items."""
        if not holdings:
            st.info("No holdings to display.")
            return []

        key_suffix = "sold" if sold else "active"
        page_size = st.selectbox(
            "Rows per page",
            [10, 20, 50],
            index=1,
            key=f"rows_per_page_{key_suffix}",
        )
        total_pages = max(1, (len(holdings) + page_size - 1) // page_size)
        page_num = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
            key=f"page_num_{key_suffix}",
        )

        start = (int(page_num) - 1) * page_size
        page_holdings = holdings[start:start + page_size]

        rows = []
        for h in page_holdings:
            current_or_sell = h.sell_price if sold else (h.current_price if h.current_price is not None else None)
            invested_on = h.invested_on
            days_value = h.days_to_target if sold else h.days_from_investment
            days_label = "Days to Target" if sold else "Days from Investment"
            target_status = "-"
            if not sold:
                if h.target_2_achieved:
                    target_status = "2nd target achieved"
                elif h.target_1_achieved:
                    if h.target_2_price is not None and h.partial_sold_quantity > 0:
                        target_status = "Waiting for 2nd target"
                    elif h.target_2_price is not None:
                        target_status = "1st target achieved"
                    else:
                        target_status = "Final target achieved"

            pl_value = h.realized_pl if sold else h.unrealized_pl
            if pl_value > 0:
                pl_display = f"🟢 ▲ {pl_value:,.2f}"
            elif pl_value < 0:
                pl_display = f"🔴 ▼ {abs(pl_value):,.2f}"
            else:
                pl_display = "⚪ ▶ 0.00"

            rows.append(
                {
                    "Ticker": h.ticker,
                    "Company": h.company_name,
                    "Portfolio": PORTFOLIO_TYPE_LABELS.get(h.portfolio_type or "MIDTERM", "Midterm"),
                    "Broker": BROKER_ACCOUNT_LABELS.get(h.broker_account or "ZERODHA", "Zerodha"),
                    "Invested On": invested_on,
                    days_label: f"{days_value}",
                    "Qty": f"{(h.remaining_quantity if not sold else h.quantity):.2f}",
                    "Buy": f"{h.buying_price:.2f}",
                    "Current Price": f"{current_or_sell:.2f}" if current_or_sell is not None else "-",
                    "P&L": pl_display,
                    "P&L %": f"{(h.realized_pl_pct if sold else h.unrealized_pl_pct):.2f}",
                    "Target Status": target_status,
                }
            )

        df = pd.DataFrame(rows)

        def _highlight_target_row(row):
            status = str(row.get("Target Status", ""))
            if status == "2nd target achieved":
                return ["background-color: #f3e8ff"] * len(row)
            return [""] * len(row)

        styled_df = df.style.apply(_highlight_target_row, axis=1)
        table_height = min(520, 72 + (len(df) * 35))
        st.dataframe(styled_df, use_container_width=True, height=table_height)
        st.caption(f"Showing {start + 1}-{start + len(page_holdings)} of {len(holdings)} items")
        return page_holdings

    # ── Tabs: Active / Sold ─────────────────────────────────────────
    tab_active, tab_sold = st.tabs([f"Active ({len(active_holdings)})", f"Sold ({len(sold_holdings)})"])

    with tab_active:
        if not active_holdings:
            st.info("No active holdings. Add a stock above.")
        else:
            active_view_mode = st.radio(
                "Active View",
                ["Compact Table", "Detailed Cards"],
                horizontal=True,
                key="active_holdings_view_mode",
            )

            if active_view_mode == "Compact Table":
                compact_page_holdings = _render_compact_holdings_table(active_holdings, sold=False)

                quick_action_holdings = [
                    h for h in compact_page_holdings
                    if h.target_1_achieved and h.remaining_quantity > 0 and not h.is_sold
                ]
                st.markdown("#### Quick Target Actions")
                if not quick_action_holdings:
                    st.info("No holdings on this page are eligible for target-based partial sell.")
                else:
                    for h in quick_action_holdings:
                        sell_30_qty = int(round(h.remaining_quantity * 0.30))
                        sell_50_qty = int(round(h.remaining_quantity * 0.50))
                        sell_100_qty = int(round(h.remaining_quantity))
                        single_target = h.target_2_price is None

                        act_col1, act_col2, act_col3, act_col4 = st.columns([2.8, 1.2, 1.2, 2.8])
                        with act_col1:
                            st.write(
                                f"**{h.ticker}** ({h.company_name}) | Remaining: {h.remaining_quantity:.2f}"
                            )
                        with act_col2:
                            if single_target:
                                if st.button(
                                    f"Sell 100% ({sell_100_qty})",
                                    key=f"compact_ps100_{h.id}",
                                    use_container_width=True,
                                ):
                                    if sell_100_qty <= 0:
                                        st.error("100% results in 0 whole shares for this holding.")
                                    else:
                                        k = f"partial_sell_open_compact_{h.id}_100"
                                        st.session_state.partial_sell_form_open[k] = True
                                        st.rerun()
                            else:
                                if st.button(
                                    f"Sell 30% ({sell_30_qty})",
                                    key=f"compact_ps30_{h.id}",
                                    use_container_width=True,
                                ):
                                    if sell_30_qty <= 0:
                                        st.error("30% results in 0 whole shares for this holding.")
                                    else:
                                        k = f"partial_sell_open_compact_{h.id}_30"
                                        st.session_state.partial_sell_form_open[k] = True
                                        st.rerun()
                        with act_col3:
                            if single_target:
                                st.caption("Single target")
                            else:
                                if st.button(
                                    f"Sell 50% ({sell_50_qty})",
                                    key=f"compact_ps50_{h.id}",
                                    use_container_width=True,
                                ):
                                    if sell_50_qty <= 0:
                                        st.error("50% results in 0 whole shares for this holding.")
                                    else:
                                        k = f"partial_sell_open_compact_{h.id}_50"
                                        st.session_state.partial_sell_form_open[k] = True
                                        st.rerun()
                        with act_col4:
                            if single_target:
                                st.caption("Only one target set. Full exit (100%) required.")
                            else:
                                st.caption(
                                    f"Suggested whole shares: 30%={sell_30_qty}, 50%={sell_50_qty}"
                                )

                        if single_target:
                            _render_partial_sell_confirm_form(h, 100.0, sell_100_qty, "compact")
                        else:
                            _render_partial_sell_confirm_form(h, 30.0, sell_30_qty, "compact")
                            _render_partial_sell_confirm_form(h, 50.0, sell_50_qty, "compact")

            for h in active_holdings if active_view_mode == "Detailed Cards" else []:
                pl_pct = h.unrealized_pl_pct
                pl_val = h.unrealized_pl
                pl_emoji = "🟢" if pl_pct >= 0 else "🔴"
                border_color = "#09ab15" if pl_pct >= 0 else "#d74e09"
                bg_color = "#f8f9fa"
                target_badge = ""

                if h.target_2_achieved:
                    border_color = "#6f42c1"
                    bg_color = "#f3e8ff"
                    target_badge = " | 🎯🎯 2nd target achieved"
                elif h.target_1_achieved:
                    border_color = "#f7931e"
                    bg_color = "#fff4de"
                    target_badge = " | 🎯 1st target achieved"

                target_line_parts = []
                if h.target_1_price:
                    status = "✅" if h.target_1_achieved else "⏳"
                    target_line_parts.append(f"T1: {h.target_1_price:.2f} {status}")
                if h.target_2_price:
                    status = "✅" if h.target_2_achieved else "⏳"
                    target_line_parts.append(f"T2: {h.target_2_price:.2f} {status}")
                target_line = " | ".join(target_line_parts) if target_line_parts else "Targets: Not set"

                st.markdown(
                    f"<div style='border-left:3px solid {border_color}; padding:6px 8px; "
                    f"background:{bg_color}; border-radius:6px; margin-bottom:4px; font-size:0.86rem; line-height:1.35;'>"
                    f"<b>{h.ticker}</b> — {h.company_name}<br/>"
                    f"Portfolio: {PORTFOLIO_TYPE_LABELS.get(h.portfolio_type or 'MIDTERM', 'Midterm')}<br/>"
                    f"Broker: {BROKER_ACCOUNT_LABELS.get(h.broker_account or 'ZERODHA', 'Zerodha')}<br/>"
                    f"Invested On: {h.invested_on} | Days from Investment: {h.days_from_investment}<br/>"
                    f"Qty: {h.quantity:.2f} | Buy: {h.buying_price:.2f} | "
                    f"Now: {f'{h.current_price:.2f}' if h.current_price else '—'} | "
                    f"Remaining: {h.remaining_quantity:.2f}<br/>"
                    f"{pl_emoji} P&L: <b>{pl_val:+,.2f}</b> ({pl_pct:+.2f}%){target_badge}<br/>"
                    f"{target_line}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                if h.target_1_achieved and h.remaining_quantity > 0:
                    sell_30_qty = int(round(h.remaining_quantity * 0.30))
                    sell_50_qty = int(round(h.remaining_quantity * 0.50))
                    sell_100_qty = int(round(h.remaining_quantity))
                    single_target = h.target_2_price is None

                    if single_target:
                        st.caption(f"Single target stock: sell 100% ({sell_100_qty} shares)")
                    else:
                        st.caption(
                            f"Partial sell suggestion: 30% = {sell_30_qty} shares, "
                            f"50% = {sell_50_qty} shares"
                        )

                    ps_col1, ps_col2 = st.columns(2)
                    with ps_col1:
                        if single_target:
                            if st.button(f"Sell 100% ({sell_100_qty})", key=f"ps100_{h.id}", use_container_width=True):
                                if sell_100_qty <= 0:
                                    st.error("100% results in 0 whole shares for this holding.")
                                else:
                                    k = f"partial_sell_open_detail_{h.id}_100"
                                    st.session_state.partial_sell_form_open[k] = True
                                    st.rerun()
                        else:
                            if st.button(f"Sell 30% ({sell_30_qty})", key=f"ps30_{h.id}", use_container_width=True):
                                if sell_30_qty <= 0:
                                    st.error("30% results in 0 whole shares for this holding.")
                                else:
                                    k = f"partial_sell_open_detail_{h.id}_30"
                                    st.session_state.partial_sell_form_open[k] = True
                                    st.rerun()

                    with ps_col2:
                        if single_target:
                            st.caption("Single target")
                        else:
                            if st.button(f"Sell 50% ({sell_50_qty})", key=f"ps50_{h.id}", use_container_width=True):
                                if sell_50_qty <= 0:
                                    st.error("50% results in 0 whole shares for this holding.")
                                else:
                                    k = f"partial_sell_open_detail_{h.id}_50"
                                    st.session_state.partial_sell_form_open[k] = True
                                    st.rerun()

                    if single_target:
                        _render_partial_sell_confirm_form(h, 100.0, sell_100_qty, "detail")
                    else:
                        _render_partial_sell_confirm_form(h, 30.0, sell_30_qty, "detail")
                        _render_partial_sell_confirm_form(h, 50.0, sell_50_qty, "detail")

                btn_col1, btn_col2, form_col = st.columns([1, 1, 4])
                with btn_col1:
                    is_single_target_full_exit = (
                        h.target_1_achieved
                        and h.target_2_price is None
                        and h.remaining_quantity > 0
                        and not h.is_sold
                    )
                    sell_button_label = (
                        f"Sell 100% ({h.remaining_quantity:.2f})"
                        if is_single_target_full_exit
                        else "Sell"
                    )
                    if st.button(sell_button_label, key=f"sell_btn_{h.id}", use_container_width=True):
                        st.session_state.sell_form_open[h.id] = not st.session_state.sell_form_open.get(h.id, False)
                        st.rerun()

                with btn_col2:
                    if st.button("Remove", key=f"del_btn_{h.id}", use_container_width=True):
                        store.delete_holding(h.id)
                        st.rerun()

                # Sell price form (shown inline when toggled)
                if st.session_state.sell_form_open.get(h.id, False):
                    with form_col:
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
        if not sold_holdings and not partial_sold_holdings:
            st.info("No sold positions yet.")
        else:
            total_realized = sum(h.realized_pl for h in sold_holdings) + sum(h.partial_realized_pl for h in partial_sold_holdings)
            emoji = "🟢" if total_realized >= 0 else "🔴"
            st.markdown(f"**Total Realized: {emoji} {total_realized:+,.2f}**")
            st.divider()

            if partial_sold_holdings:
                st.markdown("#### Partially Sold (Still Active)")
                partial_rows = []
                for h in partial_sold_holdings:
                    partial_rows.append(
                        {
                            "Ticker": h.ticker,
                            "Company": h.company_name,
                            "Portfolio": PORTFOLIO_TYPE_LABELS.get(h.portfolio_type or "MIDTERM", "Midterm"),
                            "Broker": BROKER_ACCOUNT_LABELS.get(h.broker_account or "ZERODHA", "Zerodha"),
                            "Invested On": h.invested_on,
                            "Days from Investment": f"{h.days_from_investment}",
                            "Qty Sold": f"{h.partial_sold_quantity:.2f}",
                            "Remaining Qty": f"{h.remaining_quantity:.2f}",
                            "Realized P&L": f"{h.partial_realized_pl:.2f}",
                        }
                    )
                st.dataframe(pd.DataFrame(partial_rows), use_container_width=True, height=min(360, 72 + (35 * len(partial_rows))))
                st.divider()

            sold_view_mode = st.radio(
                "Sold View",
                ["Compact Table", "Detailed Cards"],
                horizontal=True,
                key="sold_holdings_view_mode",
            )

            if sold_view_mode == "Compact Table":
                _render_compact_holdings_table(sold_holdings, sold=True)

            for h in sold_holdings if sold_view_mode == "Detailed Cards" else []:
                pl_val = h.realized_pl
                pl_pct = h.realized_pl_pct
                pl_emoji = "🟢" if pl_val >= 0 else "🔴"
                border_color = "#09ab15" if pl_val >= 0 else "#d74e09"
                sell_dt = h.sell_date.strftime("%Y-%m-%d") if h.sell_date else "—"

                st.markdown(
                    f"<div style='border-left:3px solid {border_color}; padding:6px 8px; "
                    f"background:#f8f9fa; border-radius:6px; margin-bottom:4px; font-size:0.86rem; line-height:1.35;'>"
                    f"<b>{h.ticker}</b> — {h.company_name}<br/>"
                    f"Portfolio: {PORTFOLIO_TYPE_LABELS.get(h.portfolio_type or 'MIDTERM', 'Midterm')}<br/>"
                    f"Broker: {BROKER_ACCOUNT_LABELS.get(h.broker_account or 'ZERODHA', 'Zerodha')}<br/>"
                    f"Invested On: {h.invested_on} | Days to Target: {h.days_to_target}<br/>"
                    f"Qty: {h.quantity:.2f} | Buy: {h.buying_price:.2f} → Sell: {h.sell_price:.2f}<br/>"
                    f"{pl_emoji} P&L: <b>{pl_val:+,.2f}</b> ({pl_pct:+.2f}%) | Sold: {sell_dt}"
                    f"</div>",
                    unsafe_allow_html=True,
                )


# Main UI
st.title("📈 Stock Research AI")
st.markdown("Powered by Groq LLM, Yahoo Finance, and Screener.in")
refresh_minutes = int(st.session_state.get("auto_refresh_minutes", AUTO_REFRESH_DEFAULT_MINUTES))
enable_auto_refresh(refresh_minutes * 60 * 1000)

portfolio_snapshot = build_portfolio_snapshot()
alert_counts = render_target_hit_notifications(
    portfolio_snapshot["active_holdings"],
    show_read=bool(st.session_state.get("show_read_target_alerts", False)),
)
st.caption(
    f"Auto-refresh every {refresh_minutes} minutes. "
    f"New target alerts: {alert_counts['unread']} | Read alerts: {alert_counts['read']} | "
    f"Last refresh: {portfolio_snapshot['refreshed_at'].strftime('%Y-%m-%d %H:%M:%S')}"
)

# Disclaimer
with st.expander("⚠️ IMPORTANT DISCLAIMER", expanded=False):
    st.warning(
        "**THIS IS EDUCATIONAL CONTENT ONLY.** This application is for informational purposes and does NOT constitute investment advice. "
        "Analysis is based on historical data and AI-generated insights. Past performance does not guarantee future results. "
        "Markets involve significant risk of loss. **Always consult a qualified financial advisor before making investment decisions.**"
    )

# Top-level workspace tabs so Portfolio can use full page width.
workspace_tab_research, workspace_tab_portfolio = st.tabs(["Research", "Portfolio"])

# Sidebar for search and history
with st.sidebar:
    st.header("Search & History")

    st.subheader("Live Updates")
    refresh_options = [5, 10, 15, 30, 60]
    current_refresh = int(st.session_state.get("auto_refresh_minutes", AUTO_REFRESH_DEFAULT_MINUTES))
    if current_refresh not in refresh_options:
        current_refresh = AUTO_REFRESH_DEFAULT_MINUTES

    st.selectbox(
        "Auto-refresh interval (minutes)",
        refresh_options,
        index=refresh_options.index(current_refresh),
        key="auto_refresh_minutes",
    )
    st.checkbox("Show read target alerts", key="show_read_target_alerts")
    if st.button("Refresh Prices Now", use_container_width=True):
        st.rerun()
    st.divider()
    
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

    st.divider()
    st.markdown("""
<div style='text-align: center; color: gray; font-size: 0.8em;'>
    About Me: Santosh Botre<br>
    <a href='https://www.linkedin.com/in/santoshbotre/' target='_blank' rel='noopener noreferrer'>LinkedIn</a> |
    <a href='https://github.com/santoshbo' target='_blank' rel='noopener noreferrer'>GitHub</a>
</div>
""", unsafe_allow_html=True)

# ── Main research content ────────────────────────────────────────────────
with workspace_tab_research:
    analysis = st.session_state.last_analysis

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

        elif progress.error:
            st.error(f"Research failed: {progress.error}")

        st.session_state.research_in_progress = False

    if analysis:
        # Quick-add to portfolio button
        with st.expander("➕ Add to Portfolio", expanded=False):
            st.caption("Investment date is auto-set to today's date when you add this stock.")
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
                qa_portfolio_label = st.selectbox(
                    "Portfolio",
                    ["Swing Trade", "Midterm", "Long Term"],
                    key="qa_portfolio",
                )
                qa_broker_label = st.selectbox(
                    "Broker Account",
                    ["Zerodha", "5Paisa", "Upstox"],
                    key="qa_broker",
                )
                qa_target_1 = st.number_input(
                    "1st Target Price (Optional)",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="qa_target_1",
                    help="Set 0 to skip",
                )
                qa_target_2 = st.number_input(
                    "2nd Target Price (Optional)",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="qa_target_2",
                    help="Set 0 to skip",
                )
                if st.form_submit_button("Add to Portfolio", use_container_width=True):
                    if qa_target_2 > 0 and qa_target_1 <= 0:
                        st.error("Please set 1st target before 2nd target.")
                    elif qa_target_1 > 0 and qa_target_2 > 0 and qa_target_2 <= qa_target_1:
                        st.error("2nd target should be greater than 1st target.")
                    else:
                        st.session_state.portfolio_store.add_holding(
                            ticker=analysis.ticker,
                            company_name=analysis.metrics.company_name or analysis.ticker,
                            quantity=qa_qty,
                            buying_price=qa_price,
                            currency=analysis.metrics.currency or "INR",
                            target_1_price=qa_target_1 if qa_target_1 > 0 else None,
                            target_2_price=qa_target_2 if qa_target_2 > 0 else None,
                            portfolio_type=PORTFOLIO_TYPE_BY_LABEL[qa_portfolio_label],
                            broker_account=BROKER_ACCOUNT_BY_LABEL[qa_broker_label],
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
                st.metric("Market Cap", f"${analysis.metrics.market_cap/1e9:.2f}B" if analysis.metrics.market_cap else "N/A")
            with col3:
                st.metric("PE Ratio", f"{analysis.metrics.pe_ratio:.2f}" if analysis.metrics.pe_ratio else "N/A")
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
            st.info(f"Reports saved to: {Config.REPORTS_DIR / analysis.ticker.replace('.', '_')}")

    # Footer inside main column
    st.divider()
    st.markdown("""
<div style='text-align: center; color: gray; font-size: 0.8em;'>
    Stock Research AI v0.1.0 | Data sources: Yahoo Finance, Screener.in | Powered by Groq LLM
    <br>
    About Me: Santosh Botre |
    <a href='https://www.linkedin.com/in/santoshbotre/' target='_blank' rel='noopener noreferrer'>LinkedIn</a> |
    <a href='https://github.com/santoshbo' target='_blank' rel='noopener noreferrer'>GitHub</a>
</div>
""", unsafe_allow_html=True)

# ── Portfolio panel ──────────────────────────────────────────────────────
with workspace_tab_portfolio:
    display_portfolio_panel()

