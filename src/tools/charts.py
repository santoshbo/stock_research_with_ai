"""Chart generation for price projections and analysis visualization."""

import logging
from typing import Optional, Tuple
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ChartGenerator:
    """Generates interactive charts for stock analysis."""
    
    @staticmethod
    def create_price_projection_chart(
        ticker: str,
        current_price: float,
        projections: dict,
        historical_prices: Optional[pd.DataFrame] = None,
    ) -> Optional[go.Figure]:
        """Create interactive price projection chart for 1-2 years.
        
        Args:
            ticker: Stock ticker
            current_price: Current price
            projections: Dict with 'target_low', 'target_high', 'bull', 'bear', 'base'
            historical_prices: Optional historical price data
            
        Returns:
            Plotly figure or None if generation fails
        """
        try:
            fig = go.Figure()
            
            # Current date
            today = datetime.now()
            dates_1y = pd.date_range(today, periods=252, freq='D')  # ~1 year of trading days
            dates_2y = pd.date_range(today, periods=504, freq='D')  # ~2 years
            
            # Historical prices (if available)
            if historical_prices is not None and not historical_prices.empty:
                close_prices = historical_prices['Close'].tail(60)  # Last 60 days
                fig.add_trace(go.Scatter(
                    x=close_prices.index,
                    y=close_prices.values,
                    mode='lines',
                    name='Historical Price (60D)',
                    line=dict(color='#636EFA', width=2),
                    opacity=0.7,
                ))
            
            # Current price line
            fig.add_hline(
                y=current_price,
                line_dash="dash",
                line_color="black",
                annotation_text="Current",
                annotation_position="right",
            )
            
            # Projection scenarios (1-year)
            target_high = projections.get('target_high', current_price * 1.25)
            target_low = projections.get('target_low', current_price * 0.85)
            bull_target = projections.get('bull', current_price * 1.30)
            bear_target = projections.get('bear', current_price * 0.80)
            base_target = projections.get('base', current_price * 1.15)
            
            # Bull case
            bull_prices = pd.Series(
                [current_price + (bull_target - current_price) * (i / len(dates_1y))
                 for i in range(len(dates_1y))],
                index=dates_1y
            )
            fig.add_trace(go.Scatter(
                x=dates_1y,
                y=bull_prices,
                mode='lines',
                name='Bull Case',
                line=dict(color='green', width=2, dash='solid'),
                fill=None,
            ))
            
            # Base case
            base_prices = pd.Series(
                [current_price + (base_target - current_price) * (i / len(dates_1y))
                 for i in range(len(dates_1y))],
                index=dates_1y
            )
            fig.add_trace(go.Scatter(
                x=dates_1y,
                y=base_prices,
                mode='lines',
                name='Base Case (1Y Target)',
                line=dict(color='blue', width=3, dash='solid'),
                fill=None,
            ))
            
            # Bear case
            bear_prices = pd.Series(
                [current_price + (bear_target - current_price) * (i / len(dates_1y))
                 for i in range(len(dates_1y))],
                index=dates_1y
            )
            fig.add_trace(go.Scatter(
                x=dates_1y,
                y=bear_prices,
                mode='lines',
                name='Bear Case',
                line=dict(color='red', width=2, dash='solid'),
                fill=None,
            ))
            
            # 2-year extended projection (base case)
            base_prices_2y = pd.Series(
                [current_price + (base_target * 1.1 - current_price) * (i / len(dates_2y))
                 for i in range(len(dates_2y))],
                index=dates_2y
            )
            fig.add_trace(go.Scatter(
                x=dates_2y,
                y=base_prices_2y,
                mode='lines',
                name='Base Case (2Y Extended)',
                line=dict(color='purple', width=2, dash='dash'),
                opacity=0.6,
            ))
            
            # Target zones (shaded)
            fig.add_hrect(
                y0=bear_target, y1=target_low,
                fillcolor="red", opacity=0.1,
                layer="below", line_width=0,
                annotation_text="Bear Zone", annotation_position="right",
            )
            
            fig.add_hrect(
                y0=target_low, y1=target_high,
                fillcolor="blue", opacity=0.1,
                layer="below", line_width=0,
                annotation_text="Target Zone", annotation_position="right",
            )
            
            fig.add_hrect(
                y0=target_high, y1=bull_target,
                fillcolor="green", opacity=0.1,
                layer="below", line_width=0,
                annotation_text="Bull Zone", annotation_position="right",
            )
            
            # Layout
            fig.update_layout(
                title=f"<b>{ticker} - Price Projection (1-2 Years)</b>",
                xaxis_title="Date",
                yaxis_title="Price ($)",
                hovermode='x unified',
                template='plotly_white',
                height=500,
                margin=dict(l=60, r=100, t=60, b=60),
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01,
                ),
            )
            
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
            
            return fig
        except Exception as e:
            logger.error(f"Error creating projection chart: {e}")
            return None
    
    @staticmethod
    def create_swing_trade_chart(
        ticker: str,
        current_price: float,
        entry_low: float,
        entry_high: float,
        target_low: float,
        target_high: float,
        stop_loss: float,
    ) -> Optional[go.Figure]:
        """Create swing trade setup visualization.
        
        Args:
            ticker: Stock ticker
            current_price: Current price
            entry_low: Entry zone low
            entry_high: Entry zone high
            target_low: Target zone low
            target_high: Target zone high
            stop_loss: Stop loss price
            
        Returns:
            Plotly figure or None if generation fails
        """
        try:
            fig = go.Figure()
            
            # Create timeline (1-2 months)
            days = list(range(1, 61))  # 60 days = ~2 months
            
            # Entry zone
            fig.add_hline(
                y=entry_low,
                line_dash="dash",
                line_color="orange",
                annotation_text="Entry Low",
                annotation_position="right",
            )
            fig.add_hline(
                y=entry_high,
                line_dash="dash",
                line_color="orange",
                annotation_text="Entry High",
                annotation_position="right",
            )
            
            # Current price
            fig.add_hline(
                y=current_price,
                line_dash="solid",
                line_color="black",
                line_width=2,
                annotation_text="Current",
                annotation_position="right",
            )
            
            # Target zone
            fig.add_hline(
                y=target_low,
                line_dash="dash",
                line_color="green",
                annotation_text="Target Low",
                annotation_position="right",
            )
            fig.add_hline(
                y=target_high,
                line_dash="dash",
                line_color="green",
                annotation_text="Target High",
                annotation_position="right",
            )
            
            # Stop loss
            fig.add_hline(
                y=stop_loss,
                line_dash="dot",
                line_color="red",
                line_width=2,
                annotation_text="Stop Loss",
                annotation_position="right",
            )
            
            # Zones (shaded)
            fig.add_hrect(
                y0=stop_loss, y1=entry_low,
                fillcolor="red", opacity=0.1,
                layer="below", line_width=0,
            )
            
            fig.add_hrect(
                y0=entry_low, y1=entry_high,
                fillcolor="orange", opacity=0.2,
                layer="below", line_width=0,
                annotation_text="ENTRY ZONE", annotation_position="left",
            )
            
            fig.add_hrect(
                y0=target_low, y1=target_high,
                fillcolor="green", opacity=0.2,
                layer="below", line_width=0,
                annotation_text="TARGET ZONE", annotation_position="left",
            )
            
            # Layout
            fig.update_layout(
                title=f"<b>{ticker} - Swing Trade Setup (1-2 Months)</b>",
                xaxis_title="Days from Now",
                yaxis_title="Price ($)",
                hovermode='y unified',
                template='plotly_white',
                height=400,
                margin=dict(l=60, r=150, t=60, b=60),
                showlegend=False,
            )
            
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
            
            return fig
        except Exception as e:
            logger.error(f"Error creating swing trade chart: {e}")
            return None
    
    @staticmethod
    def create_financial_trend_chart(
        ticker: str,
        financial_years: list,
    ) -> Optional[go.Figure]:
        """Create financial metrics trend chart.
        
        Args:
            ticker: Stock ticker
            financial_years: List of FinancialYear objects
            
        Returns:
            Plotly figure or None if generation fails
        """
        try:
            if not financial_years:
                return None
            
            years = [fy.year for fy in financial_years]
            revenues = [fy.sales_revenue / 1e9 if fy.sales_revenue else None for fy in financial_years]
            net_profits = [fy.net_profit / 1e9 if fy.net_profit else None for fy in financial_years]
            opms = [fy.opm if fy.opm else None for fy in financial_years]
            
            fig = go.Figure()
            
            # Revenue trend
            fig.add_trace(go.Scatter(
                x=years,
                y=revenues,
                mode='lines+markers',
                name='Revenue (B$)',
                line=dict(color='blue', width=2),
                marker=dict(size=8),
                yaxis='y1',
            ))
            
            # Net profit trend
            fig.add_trace(go.Scatter(
                x=years,
                y=net_profits,
                mode='lines+markers',
                name='Net Profit (B$)',
                line=dict(color='green', width=2),
                marker=dict(size=8),
                yaxis='y1',
            ))
            
            # OPM trend (secondary axis)
            fig.add_trace(go.Scatter(
                x=years,
                y=opms,
                mode='lines+markers',
                name='OPM %',
                line=dict(color='orange', width=2),
                marker=dict(size=8),
                yaxis='y2',
            ))
            
            # Layout with dual axes
            fig.update_layout(
                title=f"<b>{ticker} - 3-Year Financial Trends</b>",
                xaxis=dict(title="Fiscal Year"),
                yaxis=dict(title="Revenue & Net Profit (B$)", side="left"),
                yaxis2=dict(title="Operating Profit Margin %", overlaying="y", side="right"),
                hovermode='x unified',
                template='plotly_white',
                height=400,
                margin=dict(l=60, r=60, t=60, b=60),
                legend=dict(x=0.01, y=0.99),
            )
            
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
            
            return fig
        except Exception as e:
            logger.error(f"Error creating financial trend chart: {e}")
            return None
