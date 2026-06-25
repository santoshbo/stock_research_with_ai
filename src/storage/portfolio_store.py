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
                    portfolio_type TEXT NOT NULL DEFAULT 'MIDTERM',
                    broker_account TEXT NOT NULL DEFAULT 'ZERODHA',
                    date_purchased TEXT NOT NULL,
                    target_1_price REAL,
                    target_2_price REAL,
                    target_1_achieved INTEGER NOT NULL DEFAULT 0,
                    target_2_achieved INTEGER NOT NULL DEFAULT 0,
                    target_1_achieved_at TEXT,
                    target_2_achieved_at TEXT,
                    partial_sold_quantity REAL NOT NULL DEFAULT 0,
                    partial_realized_pl REAL NOT NULL DEFAULT 0,
                    is_sold     INTEGER NOT NULL DEFAULT 0,
                    sell_price  REAL,
                    sell_date   TEXT
                )
            """)

            # Lightweight schema migration for existing DBs.
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(holdings)").fetchall()}
            required_columns = {
                "portfolio_type": "TEXT NOT NULL DEFAULT 'MIDTERM'",
                "broker_account": "TEXT NOT NULL DEFAULT 'ZERODHA'",
                "target_1_price": "REAL",
                "target_2_price": "REAL",
                "target_1_achieved": "INTEGER NOT NULL DEFAULT 0",
                "target_2_achieved": "INTEGER NOT NULL DEFAULT 0",
                "target_1_achieved_at": "TEXT",
                "target_2_achieved_at": "TEXT",
                "partial_sold_quantity": "REAL NOT NULL DEFAULT 0",
                "partial_realized_pl": "REAL NOT NULL DEFAULT 0",
            }
            for col_name, col_def in required_columns.items():
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE holdings ADD COLUMN {col_name} {col_def}")
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
        target_1_price: Optional[float] = None,
        target_2_price: Optional[float] = None,
        auto_resolve: bool = True,
        portfolio_type: str = "MIDTERM",
        broker_account: str = "ZERODHA",
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
                    (
                        ticker,
                        company_name,
                        quantity,
                        buying_price,
                        currency,
                        portfolio_type,
                        broker_account,
                        date_purchased,
                        target_1_price,
                        target_2_price
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_ticker,
                    company_name,
                    quantity,
                    buying_price,
                    currency,
                    portfolio_type,
                    broker_account,
                    date_purchased.isoformat(),
                    target_1_price,
                    target_2_price,
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
            portfolio_type=portfolio_type,
            broker_account=broker_account,
            date_purchased=date_purchased,
            target_1_price=target_1_price,
            target_2_price=target_2_price,
        )

    def find_matching_active_holding(
        self,
        ticker: str,
        portfolio_type: str,
        broker_account: str,
        currency: str,
        auto_resolve: bool = True,
    ) -> Optional[PortfolioHolding]:
        """Find existing active holding for same ticker+portfolio+broker+currency."""
        resolved_ticker = ticker.upper().strip()
        if auto_resolve:
            resolved_ticker, _ = self.resolve_ticker(resolved_ticker)

        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    ticker,
                    company_name,
                    quantity,
                    buying_price,
                    currency,
                    portfolio_type,
                    broker_account,
                    date_purchased,
                    target_1_price,
                    target_2_price,
                    target_1_achieved,
                    target_2_achieved,
                    target_1_achieved_at,
                    target_2_achieved_at,
                    partial_sold_quantity,
                    partial_realized_pl,
                    is_sold,
                    sell_price,
                    sell_date
                FROM holdings
                WHERE ticker = ?
                  AND portfolio_type = ?
                  AND broker_account = ?
                  AND currency = ?
                  AND is_sold = 0
                ORDER BY id DESC
                LIMIT 1
                """,
                (resolved_ticker, portfolio_type, broker_account, currency),
            ).fetchone()

        if not row:
            return None

        (
            hid,
            row_ticker,
            company_name,
            quantity,
            buying_price,
            row_currency,
            row_portfolio_type,
            row_broker_account,
            date_purchased,
            target_1_price,
            target_2_price,
            target_1_achieved,
            target_2_achieved,
            target_1_achieved_at,
            target_2_achieved_at,
            partial_sold_quantity,
            partial_realized_pl,
            is_sold,
            sell_price,
            sell_date,
        ) = row

        return PortfolioHolding(
            id=hid,
            ticker=row_ticker,
            company_name=company_name,
            quantity=quantity,
            buying_price=buying_price,
            currency=row_currency,
            portfolio_type=row_portfolio_type,
            broker_account=row_broker_account,
            date_purchased=datetime.fromisoformat(date_purchased),
            target_1_price=target_1_price,
            target_2_price=target_2_price,
            target_1_achieved=bool(target_1_achieved),
            target_2_achieved=bool(target_2_achieved),
            target_1_achieved_at=datetime.fromisoformat(target_1_achieved_at) if target_1_achieved_at else None,
            target_2_achieved_at=datetime.fromisoformat(target_2_achieved_at) if target_2_achieved_at else None,
            partial_sold_quantity=float(partial_sold_quantity or 0),
            partial_realized_pl=float(partial_realized_pl or 0),
            is_sold=bool(is_sold),
            sell_price=sell_price,
            sell_date=datetime.fromisoformat(sell_date) if sell_date else None,
        )

    def add_more_to_holding(
        self,
        holding_id: int,
        additional_quantity: float,
        additional_buying_price: float,
    ) -> tuple[bool, Optional[float], Optional[float]]:
        """Increase quantity and recalculate weighted-average buying price.

        Returns: (success, new_quantity, new_buying_price)
        """
        if additional_quantity <= 0 or additional_buying_price <= 0:
            return False, None, None

        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT quantity, buying_price
                FROM holdings
                WHERE id = ? AND is_sold = 0
                """,
                (holding_id,),
            ).fetchone()

            if not row:
                return False, None, None

            current_qty, current_buy_price = float(row[0]), float(row[1])
            current_invested = current_qty * current_buy_price
            new_invested = additional_quantity * additional_buying_price
            updated_qty = current_qty + additional_quantity
            if updated_qty <= 0:
                return False, None, None

            updated_avg_buy = (current_invested + new_invested) / updated_qty

            cursor = conn.execute(
                """
                UPDATE holdings
                SET quantity = ?, buying_price = ?
                WHERE id = ? AND is_sold = 0
                """,
                (updated_qty, updated_avg_buy, holding_id),
            )
            conn.commit()

        if cursor.rowcount <= 0:
            return False, None, None

        logger.info(
            f"Added more to holding id={holding_id}: +qty={additional_quantity:.4f} @ {additional_buying_price:.4f}; "
            f"new_qty={updated_qty:.4f}, new_avg_buy={updated_avg_buy:.4f}"
        )
        return True, updated_qty, updated_avg_buy

    def update_holding_targets(
        self,
        holding_id: int,
        target_1_price: Optional[float],
        target_2_price: Optional[float],
    ) -> bool:
        """Update target prices for a holding."""
        with self._conn() as conn:
            cursor = conn.execute(
                """
                UPDATE holdings
                SET target_1_price = ?, target_2_price = ?
                WHERE id = ? AND is_sold = 0
                """,
                (target_1_price, target_2_price, holding_id),
            )
            conn.commit()
        return cursor.rowcount > 0

    def partially_sell_holding(
        self,
        holding_id: int,
        sell_percent: float,
        sell_quantity: Optional[float] = None,
        sell_price: Optional[float] = None,
        sell_date: Optional[datetime] = None,
    ) -> tuple[bool, float, float]:
        """Partially sell a holding by percent of remaining quantity.

        Returns: (success, sold_quantity, realized_pl)
        """
        if sell_percent <= 0 and (sell_quantity is None or sell_quantity <= 0):
            return False, 0.0, 0.0

        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT ticker, quantity, buying_price, partial_sold_quantity
                FROM holdings
                WHERE id = ? AND is_sold = 0
                """,
                (holding_id,),
            ).fetchone()

            if not row:
                return False, 0.0, 0.0

            ticker, quantity, buying_price, partial_sold_quantity = row
            remaining_qty = max(float(quantity) - float(partial_sold_quantity or 0), 0.0)
            if remaining_qty <= 0:
                return False, 0.0, 0.0

            sold_qty = float(sell_quantity) if sell_quantity is not None else remaining_qty * (sell_percent / 100.0)
            sold_qty = min(sold_qty, remaining_qty)
            if sold_qty <= 0:
                return False, 0.0, 0.0

            effective_sell_price = sell_price
            if effective_sell_price is None:
                effective_sell_price = self._fetch_price_for_ticker(ticker)
            if effective_sell_price is None:
                return False, 0.0, 0.0

            realized = (float(effective_sell_price) - float(buying_price)) * sold_qty
            sell_date = sell_date or datetime.now()

            conn.execute(
                """
                UPDATE holdings
                SET
                    partial_sold_quantity = partial_sold_quantity + ?,
                    partial_realized_pl = partial_realized_pl + ?
                WHERE id = ? AND is_sold = 0
                """,
                (sold_qty, realized, holding_id),
            )
            conn.commit()

        logger.info(
            f"Partially sold holding id={holding_id}: {sell_percent:.1f}% -> qty={sold_qty:.4f}, realized={realized:.2f}"
        )
        return True, sold_qty, realized

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
        query = """
            SELECT
                id,
                ticker,
                company_name,
                quantity,
                buying_price,
                currency,
                portfolio_type,
                broker_account,
                date_purchased,
                target_1_price,
                target_2_price,
                target_1_achieved,
                target_2_achieved,
                target_1_achieved_at,
                target_2_achieved_at,
                partial_sold_quantity,
                partial_realized_pl,
                is_sold,
                sell_price,
                sell_date
            FROM holdings
        """
        params: tuple = ()
        if sold is not None:
            query += " WHERE is_sold = ?"
            params = (1 if sold else 0,)
        query += " ORDER BY date_purchased DESC"

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()

        holdings = []
        for row in rows:
            (
                hid,
                ticker,
                company_name,
                quantity,
                buying_price,
                currency,
                portfolio_type,
                broker_account,
                date_purchased,
                target_1_price,
                target_2_price,
                target_1_achieved,
                target_2_achieved,
                target_1_achieved_at,
                target_2_achieved_at,
                partial_sold_quantity,
                partial_realized_pl,
                is_sold,
                sell_price,
                sell_date,
            ) = row
            holdings.append(
                PortfolioHolding(
                    id=hid,
                    ticker=ticker,
                    company_name=company_name,
                    quantity=quantity,
                    buying_price=buying_price,
                    currency=currency,
                    portfolio_type=portfolio_type,
                    broker_account=broker_account,
                    date_purchased=datetime.fromisoformat(date_purchased),
                    target_1_price=target_1_price,
                    target_2_price=target_2_price,
                    target_1_achieved=bool(target_1_achieved),
                    target_2_achieved=bool(target_2_achieved),
                    target_1_achieved_at=datetime.fromisoformat(target_1_achieved_at) if target_1_achieved_at else None,
                    target_2_achieved_at=datetime.fromisoformat(target_2_achieved_at) if target_2_achieved_at else None,
                    partial_sold_quantity=float(partial_sold_quantity or 0),
                    partial_realized_pl=float(partial_realized_pl or 0),
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
                self._update_target_achievements(holding)

        return holdings

    def _update_target_achievements(self, holding: PortfolioHolding) -> None:
        """Persist target achievement flags when live price crosses targets."""
        if holding.current_price is None or holding.is_sold:
            return

        mark_t1 = (
            holding.target_1_price is not None
            and not holding.target_1_achieved
            and holding.current_price >= holding.target_1_price
        )
        mark_t2 = (
            holding.target_2_price is not None
            and not holding.target_2_achieved
            and holding.current_price >= holding.target_2_price
        )

        if not (mark_t1 or mark_t2):
            return

        now = datetime.now().isoformat()
        with self._conn() as conn:
            if mark_t1:
                conn.execute(
                    """
                    UPDATE holdings
                    SET target_1_achieved = 1, target_1_achieved_at = ?
                    WHERE id = ?
                    """,
                    (now, holding.id),
                )
                holding.target_1_achieved = True
                holding.target_1_achieved_at = datetime.fromisoformat(now)

            if mark_t2:
                conn.execute(
                    """
                    UPDATE holdings
                    SET target_2_achieved = 1, target_2_achieved_at = ?
                    WHERE id = ?
                    """,
                    (now, holding.id),
                )
                holding.target_2_achieved = True
                holding.target_2_achieved_at = datetime.fromisoformat(now)

            conn.commit()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def compute_summary(self, holdings: List[PortfolioHolding]) -> PortfolioSummary:
        """Compute aggregate P&L across all holdings."""
        summary = PortfolioSummary()
        for h in holdings:
            summary.total_invested += h.total_invested
            summary.realized_pl += h.realized_pl
            if h.is_sold:
                continue
            else:
                summary.current_value += h.current_value
                summary.unrealized_pl += h.unrealized_pl
        return summary
