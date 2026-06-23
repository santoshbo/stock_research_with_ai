"""Report generation and PDF creation."""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from src.config import Config
from src.models.research import StockAnalysis, Recommendation

logger = logging.getLogger(__name__)


class ReportWriter:
    """Generates and saves research reports in multiple formats."""
    
    def __init__(self):
        """Initialize report writer."""
        self.reports_dir = Config.REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_report_filename(self, ticker: str, format_type: str = "pdf") -> Path:
        """Generate timestamped report filename.
        
        Args:
            ticker: Stock ticker
            format_type: File format (pdf, json, md)
            
        Returns:
            Path object for report file
        """
        # Create ticker directory
        ticker_dir = self.reports_dir / ticker.replace('.', '_')
        ticker_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_research_report.{format_type}"
        
        return ticker_dir / filename
    
    def save_json(self, analysis: StockAnalysis) -> Optional[Path]:
        """Save analysis as JSON.
        
        Args:
            analysis: StockAnalysis object
            
        Returns:
            Path to saved file or None if failed
        """
        try:
            filepath = self._get_report_filename(analysis.ticker, "json")
            
            # Convert to JSON-serializable format
            json_data = json.loads(analysis.model_dump_json(by_alias=True, exclude_none=False))
            
            with open(filepath, 'w') as f:
                json.dump(json_data, f, indent=2, default=str)
            
            logger.info(f"Saved JSON report: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving JSON report: {e}")
            return None
    
    def save_markdown(self, analysis: StockAnalysis) -> Optional[Path]:
        """Save analysis as Markdown.
        
        Args:
            analysis: StockAnalysis object
            
        Returns:
            Path to saved file or None if failed
        """
        try:
            filepath = self._get_report_filename(analysis.ticker, "md")
            
            with open(filepath, 'w') as f:
                f.write(self._generate_markdown_content(analysis))
            
            logger.info(f"Saved Markdown report: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving Markdown report: {e}")
            return None
    
    def save_pdf(self, analysis: StockAnalysis) -> Optional[Path]:
        """Generate and save PDF report.
        
        Args:
            analysis: StockAnalysis object
            
        Returns:
            Path to saved file or None if failed
        """
        try:
            filepath = self._get_report_filename(analysis.ticker, "pdf")
            
            doc = SimpleDocTemplate(str(filepath), pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=20,
                textColor=colors.HexColor('#1f77b4'),
                spaceAfter=12,
            )
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#2c3e50'),
                spaceAfter=8,
                spaceBefore=8,
            )
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=6,
            )
            disclaimer_style = ParagraphStyle(
                'Disclaimer',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.red,
                spaceAfter=6,
            )
            
            # Title and header
            story.append(Paragraph(f"Stock Research Report: {analysis.metrics.company_name}", title_style))
            story.append(Paragraph(f"Ticker: {analysis.ticker} | Generated: {analysis.timestamp.strftime('%Y-%m-%d %H:%M')}", normal_style))
            story.append(Spacer(1, 0.2*inch))
            
            # DISCLAIMER
            story.append(Paragraph("⚠️ DISCLAIMER", heading_style))
            story.append(Paragraph(
                "<b>EDUCATIONAL PURPOSES ONLY.</b> This report is for informational purposes and does NOT constitute investment advice. "
                "The analysis and recommendations are based on historical data and AI-generated insights. "
                "Past performance does not guarantee future results. Markets involve significant risk of loss. "
                "Always consult a qualified financial advisor before making investment decisions.",
                disclaimer_style
            ))
            story.append(Spacer(1, 0.2*inch))
            
            # Current metrics
            story.append(Paragraph("Current Market Data", heading_style))
            metrics_data = [
                ["Metric", "Value"],
                ["Current Price", f"{analysis.metrics.current_price:.2f} {analysis.metrics.currency}"],
                ["Market Cap", f"{analysis.metrics.market_cap:,.0f}" if analysis.metrics.market_cap else "N/A"],
                ["PE Ratio", f"{analysis.metrics.pe_ratio:.2f}" if analysis.metrics.pe_ratio else "N/A"],
                ["52-Week High", f"{analysis.metrics.week_52_high:.2f}" if analysis.metrics.week_52_high else "N/A"],
                ["52-Week Low", f"{analysis.metrics.week_52_low:.2f}" if analysis.metrics.week_52_low else "N/A"],
            ]
            metrics_table = Table(metrics_data, colWidths=[2.5*inch, 2*inch])
            metrics_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))
            story.append(metrics_table)
            story.append(Spacer(1, 0.2*inch))
            
            # Financial summary (3 years)
            story.append(Paragraph("3-Year Financial Summary", heading_style))
            if analysis.financial_history:
                fin_data = [
                    ["Year", "Revenue", "Operating Profit", "OPM %", "Net Profit", "PBT"],
                ]
                for fy in analysis.financial_history[:3]:
                    fin_data.append([
                        str(fy.year),
                        f"{fy.sales_revenue:,.0f}" if fy.sales_revenue else "N/A",
                        f"{fy.operating_profit:,.0f}" if fy.operating_profit else "N/A",
                        f"{fy.opm:.1f}%" if fy.opm else "N/A",
                        f"{fy.net_profit:,.0f}" if fy.net_profit else "N/A",
                        f"{fy.profit_before_tax:,.0f}" if fy.profit_before_tax else "N/A",
                    ])
                fin_table = Table(fin_data, colWidths=[0.9*inch, 1.2*inch, 1.2*inch, 0.8*inch, 1.2*inch, 1.2*inch])
                fin_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                    ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ]))
                story.append(fin_table)
            story.append(Spacer(1, 0.2*inch))
            
            # Growth Analysis
            story.append(Paragraph("Growth Analysis", heading_style))
            story.append(Paragraph(f"<b>Revenue Trend:</b> {analysis.growth_trend.revenue_trend}", normal_style))
            story.append(Paragraph(f"<b>Profitability Trend:</b> {analysis.growth_trend.profitability_trend}", normal_style))
            story.append(Paragraph(f"<b>OPM Trend:</b> {analysis.growth_trend.opm_trend}", normal_style))
            story.append(Paragraph(f"<b>Summary:</b> {analysis.growth_trend.summary}", normal_style))
            story.append(Spacer(1, 0.15*inch))
            
            # Recommendation
            story.append(Paragraph("Investment Recommendation", heading_style))
            rec_color = colors.green if analysis.recommendation.signal == Recommendation.BUY else (
                colors.orange if analysis.recommendation.signal == Recommendation.HOLD else colors.red
            )
            story.append(Paragraph(
                f"<font color='#{rec_color.hexValue()}'><b>{analysis.recommendation.signal.value}</b></font> "
                f"(Confidence: {analysis.recommendation.confidence:.0%})",
                normal_style
            ))
            story.append(Paragraph(f"<b>Reasoning:</b> {analysis.recommendation.reasoning}", normal_style))
            story.append(Paragraph(f"<b>Key Drivers:</b> {', '.join(analysis.recommendation.key_drivers)}", normal_style))
            story.append(Spacer(1, 0.15*inch))
            
            # Trading outlook
            story.append(Paragraph("Trading Outlook", heading_style))
            if analysis.swing_trade.opportunity_exists:
                story.append(Paragraph(f"<b>Swing Trade:</b> {analysis.swing_trade.commentary}", normal_style))
            story.append(Paragraph(f"<b>Long-Term:</b> {analysis.long_term.commentary}", normal_style))
            story.append(Spacer(1, 0.15*inch))
            
            # Risk Analysis
            story.append(Paragraph("Risk Analysis", heading_style))
            story.append(Paragraph(f"<b>Overall Risk Level:</b> {analysis.risk_analysis.overall_risk_level.value}", normal_style))
            story.append(Paragraph(f"<b>Downside Triggers:</b>", normal_style))
            for trigger in analysis.risk_analysis.downside_triggers[:3]:
                story.append(Paragraph(f"• {trigger}", normal_style))
            story.append(Paragraph(f"<b>Summary:</b> {analysis.risk_analysis.summary}", normal_style))
            
            # Build PDF
            doc.build(story)
            logger.info(f"Saved PDF report: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving PDF report: {e}")
            return None
    
    def _generate_markdown_content(self, analysis: StockAnalysis) -> str:
        """Generate Markdown content for report.
        
        Args:
            analysis: StockAnalysis object
            
        Returns:
            Markdown string
        """
        md = f"""# Stock Research Report: {analysis.metrics.company_name}

**Ticker:** {analysis.ticker}  
**Generated:** {analysis.timestamp.strftime('%Y-%m-%d %H:%M')}

---

## ⚠️ DISCLAIMER

**EDUCATIONAL PURPOSES ONLY.** This report is for informational purposes and does NOT constitute investment advice. The analysis is based on historical data and AI-generated insights. Past performance does not guarantee future results. Markets involve significant risk. **Always consult a qualified financial advisor before making investment decisions.**

---

## Current Market Data

| Metric | Value |
|--------|-------|
| Current Price | {analysis.metrics.current_price:.2f} {analysis.metrics.currency} |
| Market Cap | {f"{analysis.metrics.market_cap:,.0f}" if analysis.metrics.market_cap else "N/A"} |
| PE Ratio | {f"{analysis.metrics.pe_ratio:.2f}" if analysis.metrics.pe_ratio else "N/A"} |
| 52-Week High | {f"{analysis.metrics.week_52_high:.2f}" if analysis.metrics.week_52_high else "N/A"} |
| 52-Week Low | {f"{analysis.metrics.week_52_low:.2f}" if analysis.metrics.week_52_low else "N/A"} |

---

## 3-Year Financial Summary

| Year | Revenue | Operating Profit | OPM % | Net Profit | PBT |
|------|---------|------------------|-------|------------|-----|
"""
        
        for fy in analysis.financial_history[:3]:
            md += f"| {fy.year} | {f'{fy.sales_revenue:,.0f}' if fy.sales_revenue else 'N/A'} | {f'{fy.operating_profit:,.0f}' if fy.operating_profit else 'N/A'} | {f'{fy.opm:.1f}%' if fy.opm else 'N/A'} | {f'{fy.net_profit:,.0f}' if fy.net_profit else 'N/A'} | {f'{fy.profit_before_tax:,.0f}' if fy.profit_before_tax else 'N/A'} |\n"
        
        md += f"""
---

## Growth Analysis

- **Revenue Trend:** {analysis.growth_trend.revenue_trend}
- **Profitability Trend:** {analysis.growth_trend.profitability_trend}
- **OPM Trend:** {analysis.growth_trend.opm_trend}
- **Summary:** {analysis.growth_trend.summary}

---

## Investment Recommendation

**Signal:** **{analysis.recommendation.signal.value}** (Confidence: {analysis.recommendation.confidence:.0%})

**Reasoning:** {analysis.recommendation.reasoning}

**Key Drivers:**
{chr(10).join([f"- {driver}" for driver in analysis.recommendation.key_drivers])}

---

## Trading Outlook

**Swing Trade:** {analysis.swing_trade.commentary}

**Long-Term:** {analysis.long_term.commentary}

---

## Risk Analysis

- **Overall Risk Level:** {analysis.risk_analysis.overall_risk_level.value}
- **Volatility Risk:** {analysis.risk_analysis.volatility_risk.value}
- **Business Risk:** {analysis.risk_analysis.business_risk.value}

**Downside Triggers:**
{chr(10).join([f"- {trigger}" for trigger in analysis.risk_analysis.downside_triggers[:5]])}

**Summary:** {analysis.risk_analysis.summary}

---

*Report generated by Stock Research AI | Data sources: {', '.join(analysis.data_sources)}*
"""
        return md
