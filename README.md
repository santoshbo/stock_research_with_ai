# stock_research_with_ai

Stock Research Made Easy With AI — Powered by Groq LLM, Yahoo Finance, and Screener.in

## ⚠️ **Important Disclaimer**

This application is for **educational purposes only** and provides analysis and signals based on publicly available financial data and AI-generated insights. 

**NOT financial or investment advice.** Do not use this tool as the sole basis for investment decisions. Always consult with a qualified financial advisor before making investment decisions. Past performance does not guarantee future results. Markets are volatile and involve significant risk of loss.

---

## Features

- **Multi-ticker Search**: Research US and Indian stocks
- **3-Year Financial Analysis**: Sales, expenses, operating profit, OPM, net profit, profit before tax
- **Growth Trend Detection**: Identifies improving or declining performance over time
- **Recent Announcements**: Aggregates recent corporate news and announcements
- **Educational Recommendations**: Buy/Hold/Sell signals with confidence scoring (not investment advice)
- **Risk Analysis**: Success/failure scenarios and downside triggers
- **Trading Outlook**: Swing trade opportunities (entry zones, stop-loss, targets) and long-term targets
- **Report Generation**: Auto-saves detailed PDF reports in `/reports` directory
- **Search History**: Maintains recent 20 searches for quick re-analysis

---

## Installation

### Prerequisites

- Python 3.13+
- `uv` package manager (or `pip`)

### Setup

1. **Clone/navigate to project**:
   ```bash
   cd stock_research_with_ai
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   # or if using pip:
   pip install -e .
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your API keys:
   - `GROQ_API_KEY`: Get from https://console.groq.com/keys
   - `GOOGLE_API_KEY`: (optional) Get from Google Cloud Console

4. **Verify installation**:
   ```bash
   uv run python -c "import streamlit; print('✓ Streamlit ready')"
   ```

---

## Running the Application

```bash
# Start the Streamlit UI
uv run streamlit run src/ui/streamlit_app.py

# Or directly:
uv run python main.py
```

The app will open in your browser at `http://localhost:8501`

---

## How It Works

1. **Enter a stock ticker** (e.g., `AAPL` for Apple, `RELIANCE.NS` for Reliance India)
2. **Click "Research"** to start analysis
3. The app will:
   - Fetch 3 years of financial data from Yahoo Finance
   - For Indian stocks, retrieve annual reports and concalls from Screener.in
   - Aggregate metrics and detect growth trends
   - Use Groq LLM to analyze and generate insights
   - Calculate risk scores and trading opportunities
   - Generate and save a detailed PDF report
4. **View results** in the dashboard with charts and metrics
5. **Browse history** in the sidebar to re-open previous research

---

## Data Sources

### Yahoo Finance (All Stocks)
- Historical stock prices (1–10 years)
- Key financial metrics: PE ratio, dividend yield, market cap, 52-week high/low
- Annual financial statements: revenue, expenses, net income (when available)
- Analyst ratings and earnings estimates

### Screener.in (Indian Stocks Only)
- Annual reports and financial statements
- Concall transcripts and notes
- Recent announcements and corporate actions
- Best-effort data (gracefully degrades if unavailable or blocked)

---

## Report Structure

Generated PDF reports include:

- **Company Overview**: Name, sector, market cap, current price
- **3-Year Financial Summary**: Table with sales, expenses, operating profit, OPM, net profit, PBT
- **Growth Analysis**: Trend commentary and year-over-year changes
- **Recent Announcements**: Recent corporate news and actions
- **Educational Recommendation**: Buy/Hold/Sell signal with confidence and disclaimer
- **Expected Returns**: Scenario-based return projections (not guaranteed)
- **Trading Outlook**:
  - **Swing Trading**: Entry zone, stop-loss %, target band, invalidation conditions
  - **Long-Term**: Multi-year target price and scenario targets
- **Risk Analysis**: Success/failure probabilities, downside triggers, and key uncertainties

---

## Configuration

Edit `.env` to customize behavior:

```ini
# LLM Model (Groq API)
GROQ_API_KEY=your_key

# Timeout for research (seconds)
RESEARCH_TIMEOUT_SECONDS=120

# Max historical searches to display
MAX_SEARCH_HISTORY=20

# Enable/disable Screener.in scraping for Indian stocks
ENABLE_SCREENER_IN=true

# Reports output directory
REPORTS_DIR=./reports
```

---

## Limitations

- **Data Availability**: Not all stocks have complete historical data; missing data is noted in reports
- **Screener.in Access**: May be rate-limited or occasionally unavailable; app gracefully falls back
- **Real-time Prices**: Uses delayed/EOD data (not real-time trading)
- **Sentiment Analysis**: Based on available news; may not capture all market sentiment
- **Recommendations**: Educational signals only; not substitutes for professional financial advice
- **Single-User**: Currently designed for personal use; no multi-user or portfolio tracking

---

## Development

### Running Tests

```bash
uv run pytest tests/ -v
```

### Adding New Features

The codebase is modular:
- `src/tools/` — Data adapters (Yahoo Finance, Screener.in)
- `src/llm/` — Groq client and prompt templates
- `src/ui/` — Streamlit app components
- `src/storage/` — Report and history persistence

---

## License

MIT

---

## Support

For issues or questions, check the `/reports` directory for generated research outputs and error logs in the application console.
