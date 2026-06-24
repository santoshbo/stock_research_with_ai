"""Google Finance price scraper — used as fallback when Yahoo Finance fails."""

import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Map Yahoo Finance suffixes → Google Finance exchange codes
_SUFFIX_TO_EXCHANGE = {
    ".NS": "NSE",
    ".BO": "BOM",
    ".L": "LON",
    ".AX": "ASX",
    ".TO": "TSE",
    ".HK": "HKG",
    ".DE": "ETR",
    ".PA": "EPA",
}

# For bare US tickers we try these exchanges in order
_US_EXCHANGES = ["NASDAQ", "NYSE", "NYSEARCA", "NYSEAMERICAN"]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _parse_price(text: str) -> Optional[float]:
    """Extract a float from a price string like '₹1,436.80' or '294.30'."""
    # Remove everything that is not a digit, dot, or comma
    cleaned = re.sub(r"[^\d.,]", "", text.strip())
    if not cleaned:
        return None
    # Handle Indian number format (1,23,456.78) and Western (1,234.56)
    # Remove all commas then parse
    cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _scrape_google_finance(symbol: str, exchange: str, timeout: int = 10) -> Optional[float]:
    """Scrape the current price for `symbol:exchange` from Google Finance."""
    url = f"https://www.google.com/finance/quote/{symbol}:{exchange}"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            logger.debug(f"Google Finance {url} returned {resp.status_code}")
            return None

        html = resp.text

        # Google Finance embeds stock data in the page as a JSON array.
        # The pattern is: ..., <market_cap_in_sci_notation>, <current_price>, <open>, <high>, <low>, ...
        # e.g.  1.16E12,1433.1,1445.7,1448.7,1425.7
        m = re.search(r"[\d.]+E\d+,([\d.]+),([\d.]+),([\d.]+),([\d.]+)", html)
        if m:
            # First value after market cap is current / last price
            price = _parse_price(m.group(1))
            if price and price > 0:
                logger.info(f"Google Finance price for {symbol}:{exchange} = {price}")
                return price

        # Fallback: BeautifulSoup scan for the rdshMc class (related prices section —
        # first element is the quoted stock's price when there are no comparison stocks)
        soup = BeautifulSoup(html, "lxml")
        el = soup.find("div", class_="rdshMc")
        if el:
            price = _parse_price(el.get_text())
            if price and price > 0:
                logger.info(f"Google Finance (rdshMc) price for {symbol}:{exchange} = {price}")
                return price

    except requests.RequestException as exc:
        logger.debug(f"Google Finance request error for {symbol}:{exchange}: {exc}")
    except Exception as exc:
        logger.debug(f"Google Finance parse error for {symbol}:{exchange}: {exc}")

    return None


def get_price(yahoo_ticker: str, timeout: int = 10) -> Optional[float]:
    """Fetch the latest price from Google Finance for a Yahoo Finance ticker.

    Examples
    --------
    get_price("CIPLA.NS")   → tries NSE
    get_price("CIPLA")      → tries NASDAQ, NYSE, …
    get_price("AAPL")       → tries NASDAQ, NYSE, …
    """
    yahoo_ticker = yahoo_ticker.upper().strip()

    # Detect exchange from suffix
    for suffix, exchange in _SUFFIX_TO_EXCHANGE.items():
        if yahoo_ticker.endswith(suffix):
            symbol = yahoo_ticker[: -len(suffix)]
            price = _scrape_google_finance(symbol, exchange, timeout)
            if price:
                return price
            # If known Indian exchange failed, also try the other one
            if exchange == "NSE":
                price = _scrape_google_finance(symbol, "BOM", timeout)
                if price:
                    return price
            return None

    # No suffix → assume US stock, try common exchanges
    for exchange in _US_EXCHANGES:
        price = _scrape_google_finance(yahoo_ticker, exchange, timeout)
        if price:
            return price

    logger.warning(f"Google Finance: could not find price for {yahoo_ticker}")
    return None
