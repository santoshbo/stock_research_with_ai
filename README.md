# stock_research_with_ai

AI-assisted stock research and portfolio tracking application built with Streamlit.

Data and analysis pipeline uses:
- Groq LLM for narrative insights and recommendations
- Yahoo Finance as the primary data source
- Screener.in as an additional source for Indian stocks

## Important Disclaimer

This project is for educational and informational use only.
It is not financial advice, portfolio management advice, or a solicitation to trade.

Always do your own research and consult a qualified financial advisor before making investment decisions.

## What Is New

- Portfolio management panel with add, sell, partial-sell, and remove actions
- Persistent portfolio storage in SQLite
- Realized and unrealized P&L tracking with active/sold tabs
- Dual targets per holding (target 1 and target 2) with automatic achievement marking
- Target-based visual highlighting in portfolio cards
- Partial sell helpers for 30% and 50% after target 1, with whole-share rounding
- Portfolio buckets: Swing Trade, Midterm, and Long Term
- Broker account tagging per holding: Zerodha, 5Paisa, and Upstox
- Per-portfolio invested amount and P&L summaries
- Auto ticker resolution for Indian equities (for example, raw ticker to .NS/.BO when needed)
- Interactive charts for:
  - financial trends
  - swing-trade setup
  - 1-2 year price projection scenarios
- Multi-format report generation (JSON, Markdown, PDF)
- Search history persistence in local cache
- Quality/missing-data notes in generated analysis

## Core Features

- Single-click research workflow from company name or ticker
- Company lookup and suggestions (US + India mappings)
- 3-year financial summary and growth trend analysis
- Recommendation signal with confidence and key drivers
- Risk analysis with downside triggers and scenario framing
- Swing-trade and long-term outlook modules
- Report output saved per ticker under the reports directory

## Quick Start

Two ways to run the app: **Docker** (recommended, no Python setup needed) or **local Python**.

---

### Option 1 — Docker (Recommended)

#### Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

#### 1. Get a Groq API key

Create a free key at https://console.groq.com/keys

#### 2. Create your .env file

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```ini
GROQ_API_KEY=your_groq_key
```

#### 3. Build the Docker image

```bash
docker compose build
```

This downloads the base Python image and installs all dependencies.  
Takes 3–5 minutes on first run; subsequent builds use the layer cache.

#### 4. Start the app

```bash
docker compose up
```

Add `-d` to run in the background:

```bash
docker compose up -d
```

#### 5. Open in browser

```
http://localhost:8501
```

#### Stop the app

```bash
docker compose down
```

Reports and portfolio data survive — they are stored in Docker named volumes:

| Data | Volume |
|---|---|
| Reports (JSON / Markdown / PDF) | `stock_research_with_ai_reports-data` |
| SQLite history and portfolio | `stock_research_with_ai_cache-data` |

#### Rebuild after code changes

```bash
docker compose up --build
```

#### Inspect or back up data

```bash
# See where Docker stores the volume on disk
docker volume inspect stock_research_with_ai_reports-data

# Copy reports out of the container to your local machine
docker cp stock-research:/home/app/project/reports ./reports-backup
```

#### Remove all data (destructive)

```bash
docker compose down -v
```

---

### Option 2 — Local Python

#### Requirements

- Python 3.13+
- uv (recommended) or pip

#### Install

```bash
cd stock_research_with_ai
uv sync
```

Alternative with pip:

```bash
pip install -e .
```

#### Configure Environment

Create or edit `.env` in the project root and set at minimum:

```ini
GROQ_API_KEY=your_groq_key
```

Optional settings:

```ini
GOOGLE_API_KEY=your_google_key
RESEARCH_TIMEOUT_SECONDS=120
CACHE_TTL_SECONDS=3600
SCREENER_IN_TIMEOUT=30
ENABLE_SCREENER_IN=true
PDF_INCLUDE_CHARTS=true
MAX_SEARCH_HISTORY=20
REPORTS_DIR=./reports
LOG_LEVEL=INFO
```

#### Run

Start Streamlit directly:

```bash
uv run streamlit run src/ui/streamlit_app.py
```

Or via launcher:

```bash
uv run python main.py
```

App default URL: http://localhost:8501

## Research Workflow

1. Enter company name or ticker in the sidebar search box.
2. Pick a suggestion or click Research.
3. The app aggregates market, financial, and announcement data.
4. Scoring and risk engines produce recommendation and scenarios.
5. Trading module calculates swing and long-term outlook.
6. Reports are saved as JSON, Markdown, and PDF.
7. You can add the researched stock directly to your portfolio.

## Portfolio Workflow

- Add holdings with quantity, buy price, currency, portfolio bucket, broker account, and optional target 1 and target 2
- View active holdings with live price enrichment
- Automatic highlight when target 1 or target 2 is achieved
- Partially sell on target 1 (30% or 50%) with rounded whole-share quantities
- Sell holdings and track realized P&L
- Remove active holdings
- View summarized invested value, unrealized P&L, and realized P&L
- View separate invested and P&L summary for Swing Trade, Midterm, and Long Term portfolios

Portfolio data is stored locally in .cache/portfolio.db.

## Screenshots

### Research Dashboard

![Research dashboard view](screenshots/Screenshot%202026-06-25%20at%2011.45.55%E2%80%AFAM.png)

### Research Result And Insights

![Research results and insights](screenshots/Screenshot%202026-06-25%20at%2011.46.34%E2%80%AFAM.png)

### Portfolio Add/Edit Panel

![Portfolio add or edit panel](screenshots/Screenshot%202026-06-25%20at%2011.46.41%E2%80%AFAM.png)

### Active Holdings Overview

![Active holdings overview](screenshots/Screenshot%202026-06-25%20at%2011.46.53%E2%80%AFAM.png)

### P&L And Targets Tracking

![P&L and targets tracking](screenshots/Screenshot%202026-06-25%20at%2011.47.02%E2%80%AFAM.png)

### History And Report References

![History and report references](screenshots/Screenshot%202026-06-25%20at%2011.47.14%E2%80%AFAM.png)

### Swing Trade App View

![Additional app view](screenshots/Screenshot%202026-06-25%20at%2011.49.39%E2%80%AFAM.png)

## Reports And Storage

- Reports are stored under reports/TICKER/
- Each run creates timestamped files:
  - YYYYMMDD_HHMMSS_research_report.json
  - YYYYMMDD_HHMMSS_research_report.md
  - YYYYMMDD_HHMMSS_research_report.pdf
- Search history is stored in .cache/search_history.json

## Data Sources

### Yahoo Finance

- Price history
- Core metrics (price, market cap, PE, 52-week range)
- Financial statements (when available)
- Analyst recommendation data and earnings dates (when available)

### Screener.in (Indian stocks)

- Announcements
- Annual report links
- Concall transcript links

If Screener.in data is unavailable, analysis still proceeds with available sources.

## Project Structure

- `Dockerfile`: multi-stage container build definition
- `docker-compose.yml`: single-command build and run with persistent volumes
- `.env.example`: template for all environment variables
- `src/app.py`: end-to-end research orchestration
- `src/ui/streamlit_app.py`: Streamlit UI (research + portfolio panel)
- `src/tools/`: data adapters, scoring, trading, charts, company lookup
- `src/storage/`: report writer, history store, portfolio store
- `src/models/`: analysis and portfolio models

## Development

Run the e2e test script:

```bash
uv run python test_e2e.py
```

Run the demo flow:

```bash
uv run python demo_research.py
```

## Known Limitations

- Data completeness varies by ticker and exchange
- Price feeds are best-effort and may be delayed
- Recommendation outputs are model-assisted and non-deterministic
- Designed for local/single-user usage

## License

MIT
