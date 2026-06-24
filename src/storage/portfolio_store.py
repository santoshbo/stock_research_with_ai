"""SQLite-based portfolio persistence store."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yfinance as yf

from src.config import Config
from src.tools import google_finance as gf
from src.models.portfolio import PortfolioHolding, PortfolioSummary

logger = logging.getLogger(__name__)

DB_PATH = Config.CACHE_DIR / "portfolio.db"


class PortfolioStore:
    """Manages portfolio holdings and sold positions using SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS holdings (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker      TEXT    NOT NULL,
                    company_name TEXT   NOT NULL DEFAULT '',
                    quantity    REAL    NOT NULL,
                    buying_price REAL   NOT NULL,
                    currency    TEXT    NOT NULL DEFAULT 'USD',
                    date_purchased TEXT NOT NULL,
                    is_sold     INTEGER NOT NULL DEFAULT 0,
                    sell_price  REAL,
                    sell_date   TEXT
                )
            """)
            conn.commit()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Ticker resolution helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_price_for_ticker(ticker: str) -> Optional[float]:
        """Try to get the latest price via Yahoo Finance, then Google Finance."""
        # --- Yahoo Finance ---
        try:
            stock = yf.Ticker(ticker)
            fi = stock.fast_info
            price = getattr(fi, "last_price", None) or getattr(fi, "regular_market_price", None)
            if price:
                return float(price)
        except Exception:
            pass

        try:
            hist = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
            if not hist.empty and "Close" in hist.columns:
                last = hist["Close"].dropna()
                if not last.empty:
                    return float(last.iloc[-1])
        except Exception:
            pass

        # --- For bare tickers try Indian suffixes before Google Finance ---
        if "." not in ticker:
            for suffix in (".NS", ".BO"):
                alt = ticker + suffix
                try:
                    fi = yf.Ticker(alt).fast_info
                    p = getattr(fi, "last_price", None) or getattr(fi, "regular_market_price", None)
                    if p:
                        return float(p)
                except Exception:
                    pass
                try:
                    hist = yf.Ticker(alt).history(period="5d", auto_adjust=True)
                    if not hist.empty and "Close" in hist.columns:
                        last = hist["Close"].dropna()
                        if not last.empty:
                            return float(last.iloc[-1])
                except Exception:
                    pass

        # --- Google Finance fallback ---
        try:
            price = gf.get_price(ticker)
            if price:
                logger.info(f"Google Finance supplied price for {ticker}: {price}")
                return price
        except Exception:
            pass

        return None

    @staticmethod
    def resolve_ticker(raw: str) -> tuple[str, Optional[float]]:
        """Resolve a raw ticker to a valid Yahoo Finance symbol.

        For plain symbols (no exchange suffix), tries:
          1. As-is
          2. <TICKER>.NS  (NSE India)
          3. <TICKER>.BO  (BSE India)

        Returns (resolved_ticker, price) where price may be None.
        """
        raw = raw.upper().strip()

        # Already has a suffix — use as-is
        if "." in raw:
            price = PortfolioStore._fetch_price_for_ticker(raw)
            return raw, price

        # Try plain first (US stocks)
        price = PortfolioStore._fetch_price_for_ticker(raw)
        if price:
            return raw, price

        # Try NSE
        ns = raw + ".NS"
        price = PortfolioStore._fetch_price_for_ticker(ns)
        if price:
            logger.info(f"Resolved {raw} → {ns}")
            return ns, price

        # Try BSE
        bo = raw + ".BO"
        price = PortfolioStore._fetch_price_for_ticker(bo)
        if price:
            logger.info(f"Resolved {raw} → {bo}")
            return bo, price

        # Nothing worked; return original
        return raw, None

    def add_holding(
        self,
        ticker: str,
        company_name: str,
        quantity: float,
        buying_price: float,
        currency: str = "INR",
        date_purchased: Optional[datetime] = None,
        auto_resolve: bool = True,
    ) -> PortfolioHolding:
        """Add a new stock to the portfolio.

        If auto_resolve is True (default), plain Indian tickers like 'CIPLA'
        are automatically resolved to 'CIPLA.NS' / 'CIPLA.BO'.
        """
        date_purchased = date_purchased or datetime.now()

        resolved_ticker = ticker.upper().strip()
        if auto_resolve:
            resolved_ticker, _ = self.resolve_ticker(resolved_ticker)

        with self._conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO holdings
                    (ticker, company_name, quantity, buying_price, currency, date_purchased)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_ticker,
                    company_name,
                    quantity,
                    buying_price,
                    currency,
                    date_purchased.isoformat(),
                ),
            )
            conn.commit()
            holding_id = cursor.lastrowid

        logger.info(f"Added holding: {resolved_ticker} x{quantity} @ {buying_price}")
        return PortfolioHolding(
            id=holding_id,
            ticker=resolved_ticker,
            company_name=company_name,
            quantity=quantity,
            buying_price=buying_price,
            currency=currency,
            date_purchased=date_purchased,
        )

    def sell_holding(self, holding_id: int, sell_price: float, sell_date: Optional[datetime] = None) -> bool:
        """Mark a holding as sold."""
        sell_date = sell_date or datetime.now()
        with self._conn() as conn:
            cursor = conn.execute(
                """
                UPDATE holdings
                SET is_sold = 1, sell_price = ?, sell_date = ?
                WHERE id = ? AND is_sold = 0
                """,
                (sell_price, sell_date.isoformat(), holding_id),
            )
            conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info(f"Sold holding id={holding_id} @ {sell_price}")
        return updated

    def delete_holding(self, holding_id: int) -> bool:
        """Permanently remove a holding (active only)."""
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM holdings WHERE id = ? AND is_sold = 0",
                (holding_id,),
            )
            conn.commit()
        return cursor.rowcount > 0

    def get_active_holdings(self) -> List[PortfolioHolding]:
        """Return all unsold holdings."""
        return self._fetch_holdings(sold=False)

    def get_sold_holdings(self) -> List[PortfolioHolding]:
        """Return all sold holdings."""
        return self._fetch_holdings(sold=True)

    def get_all_holdings(self) -> List[PortfolioHolding]:
        """Return every holding regardless of sold status."""
        return self._fetch_holdings(sold=None)

    def _fetch_holdings(self, sold: Optional[bool]) -> List[PortfolioHolding]:
        query = "SELECT id, ticker, company_name, quantity, buying_price, currency, date_purchased, is_sold, sell_price, sell_date FROM holdings"
        params: tuple = ()
        if sold is not None:
            query += " WHERE is_sold = ?"
            params = (1 if sold else 0,)
        query += " ORDER BY date_purchased DESC"

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()

        holdings = []
        for row in rows:
            (hid, ticker, company_name, quantity, buying_price, currency,
             date_purchased, is_sold, sell_price, sell_date) = row
            holdings.append(
                PortfolioHolding(
                    id=hid,
                    ticker=ticker,
                    company_name=company_name,
                    quantity=quantity,
                    buying_price=buying_price,
                    currency=currency,
                    date_purchased=datetime.fromisoformat(date_purchased),
                    is_sold=bool(is_sold),
                    sell_price=sell_price,
                    sell_date=datetime.fromisoformat(sell_date) if sell_date else None,
                )
            )
        return holdings

    # ------------------------------------------------------------------
    # Live prices
    # ------------------------------------------------------------------

    def enrich_with_prices(self, holdings: List[PortfolioHolding]) -> List[PortfolioHolding]:
        """Fetch current (or latest EOD) market prices for active holdings via yfinance."""
        active = [h for h in holdings if not h.is_sold]
        if not active:
            return holdings

        tickers_unique = list({h.ticker for h in active})
        prices: dict = {}
        currencies: dict = {}
        ticker_remap: dict = {}  # plain_ticker -> resolved (e.g. CIPLA -> CIPLA.NS)

        for ticker in tickers_unique:
            price = None
            curr = None

            # 1. fast_info — lightest call, works pre/post/after-hours
            try:
                fi = yf.Ticker(ticker).fast_info
                price = getattr(fi, "last_price", None) or getattr(fi, "regular_market_price", None)
                curr = getattr(fi, "currency", None)
            except Exception:
                pass

            # 2. full info dict (slower but more complete)
            if not price:
                try:
                    info = yf.Ticker(ticker).info
                    price = (
                        info.get("currentPrice")
                        or info.get("regularMarketPrice")
                        or info.get("previousClose")
                    )
                    if not curr:
                        curr = info.get("currency")
                except Exception:
                    pass

            # 3. Historical EOD fallback — last 5 trading days
            if not price:
                try:
                    hist = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
                    if not hist.empty and "Close" in hist.columns:
                        last = hist["Close"].dropna()
                        if not last.empty:
                            price = float(last.iloc[-1])
                except Exception:
                    pass

            # 4. Auto-resolve Indian suffix if still no price (must happen before Google Finance
            #    so we pass the correct exchange e.g. CIPLA.NS not bare CIPLA)
            if not price and "." not in ticker:
                for suffix in (".NS", ".BO"):
                    alt = ticker + suffix
                    alt_price = self._fetch_price_for_ticker(alt)
                    if alt_price:
                        price = alt_price
                        prices[alt] = alt_price
                        ticker_remap[ticker] = alt
                        logger.info(f"Price fallback: {ticker} → {alt}")
                        break

            # 5. Google Finance fallback — use resolved ticker so the exchange is correct
            if not price:
                resolved_for_gf = ticker_remap.get(ticker, ticker)
                try:
                    gf_price = gf.get_price(resolved_for_gf)
                    if gf_price:
                        price = gf_price
                        logger.info(f"Google Finance supplied price for {resolved_for_gf}: {price}")
                except Exception:
                    pass

            if curr:
                currencies[ticker] = curr

            if price:
                prices[ticker] = float(price)
                logger.debug(f"Price for {ticker}: {price}")
            else:
                logger.warning(f"Could not fetch price for {ticker}")

        for holding in holdings:
            if not holding.is_sold:
                effective = ticker_remap.get(holding.ticker, holding.ticker)
                if effective in prices:
                    holding.current_price = prices[effective]
                if effective in currencies:
                    holding.currency = currencies[effective]

        return holdings

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def compute_summary(self, holdings: List[PortfolioHolding]) -> PortfolioSummary:
        """Compute aggregate P&L across all holdings."""
        summary = PortfolioSummary()
        for h in holdings:
            summary.total_invested += h.total_invested
            if h.is_sold:
                summary.realized_pl += h.realized_pl
            else:
                summary.current_value += h.current_value
                summary.unrealized_pl += h.unrealized_pl
        return summary
