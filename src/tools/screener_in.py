"""Screener.in data adapter for Indian stock research."""

import logging
from datetime import datetime
from typing import Optional, List, Dict
import requests
from bs4 import BeautifulSoup

from src.models.research import Announcement

logger = logging.getLogger(__name__)


class ScreenerInClient:
    """Fetches Indian stock data from Screener.in (best-effort)."""
    
    BASE_URL = "https://www.screener.in"
    TIMEOUT = 10
    
    def __init__(self, timeout: int = 10, enabled: bool = True):
        """Initialize Screener.in client.
        
        Args:
            timeout: Request timeout in seconds
            enabled: Whether to attempt scraping (can be disabled in config)
        """
        self.timeout = timeout
        self.enabled = enabled
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
    
    def _normalize_ticker(self, ticker: str) -> str:
        """Convert ticker to Screener.in format.
        
        Examples:
            'RELIANCE.NS' -> 'RELIANCE'
            'INFY.NS' -> 'INFY'
            'SBIN' -> 'SBIN' (already normalized)
        
        Args:
            ticker: Yahoo Finance ticker format
            
        Returns:
            Screener.in company code format
        """
        if ticker.endswith('.NS'):
            return ticker[:-3]
        elif ticker.endswith('.BO'):
            return ticker[:-3]
        return ticker
    
    def get_company_url(self, ticker: str) -> Optional[str]:
        """Get Screener.in company page URL.
        
        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            
        Returns:
            Company URL or None if not found
        """
        try:
            normalized = self._normalize_ticker(ticker)
            url = f"{self.BASE_URL}/company/{normalized}"
            
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                return url
            else:
                logger.warning(f"Screener.in company page not found for {ticker}: status {response.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Error checking Screener.in URL for {ticker}: {e}")
            return None
    
    def get_announcements(self, ticker: str, limit: int = 10) -> List[Announcement]:
        """Fetch recent announcements from Screener.in.
        
        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            limit: Maximum number of announcements to fetch
            
        Returns:
            List of Announcement objects (empty if unavailable)
        """
        if not self.enabled:
            return []
        
        try:
            normalized = self._normalize_ticker(ticker)
            url = f"{self.BASE_URL}/company/{normalized}/announcements"
            
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch announcements for {ticker}: status {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, 'lxml')
            announcements = []
            
            # Look for announcement rows (typical Screener.in structure)
            announcement_rows = soup.find_all('tr', limit=limit + 5)
            
            for row in announcement_rows:
                try:
                    cells = row.find_all('td')
                    if len(cells) < 2:
                        continue
                    
                    # Extract date
                    date_text = cells[0].get_text(strip=True)
                    try:
                        date = datetime.strptime(date_text, "%d %b %Y")
                    except ValueError:
                        try:
                            date = datetime.strptime(date_text, "%d-%m-%Y")
                        except ValueError:
                            date = datetime.now()
                    
                    # Extract title
                    title_cell = cells[1]
                    title = title_cell.get_text(strip=True)
                    
                    if not title:
                        continue
                    
                    announcement = Announcement(
                        date=date,
                        title=title,
                        source="screener_in",
                        url=url,
                    )
                    announcements.append(announcement)
                    
                    if len(announcements) >= limit:
                        break
                except Exception as e:
                    logger.debug(f"Error parsing announcement row: {e}")
                    continue
            
            return announcements
        except Exception as e:
            logger.warning(f"Error fetching announcements from Screener.in for {ticker}: {e}")
            return []
    
    def get_annual_reports(self, ticker: str) -> List[Dict]:
        """Fetch links to annual reports.
        
        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            
        Returns:
            List of report dictionaries with year, URL, and type
        """
        if not self.enabled:
            return []
        
        try:
            normalized = self._normalize_ticker(ticker)
            url = f"{self.BASE_URL}/company/{normalized}"
            
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.content, 'lxml')
            reports = []
            
            # Look for annual reports section (varies by Screener.in layout)
            # This is a heuristic approach; exact selectors may need adjustment
            report_links = soup.find_all('a', string=lambda s: s and 'annual' in s.lower())
            
            for link in report_links[:10]:
                try:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    if href.startswith('/'):
                        href = self.BASE_URL + href
                    
                    reports.append({
                        "title": text,
                        "url": href,
                        "type": "annual_report",
                    })
                except Exception as e:
                    logger.debug(f"Error parsing annual report link: {e}")
                    continue
            
            return reports
        except Exception as e:
            logger.warning(f"Error fetching annual reports from Screener.in for {ticker}: {e}")
            return []
    
    def get_concall_transcripts(self, ticker: str, limit: int = 5) -> List[Dict]:
        """Fetch links to concall transcripts/notes.
        
        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            limit: Maximum number of transcripts to fetch
            
        Returns:
            List of concall dictionaries with date, title, and URL
        """
        if not self.enabled:
            return []
        
        try:
            # Screener.in typically embeds concall info on the company page
            normalized = self._normalize_ticker(ticker)
            url = f"{self.BASE_URL}/company/{normalized}"
            
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.content, 'lxml')
            concalls = []
            
            # Look for earnings/concall related links
            concall_links = soup.find_all('a', string=lambda s: s and any(
                x in s.lower() for x in ['concall', 'earnings', 'conference', 'q1', 'q2', 'q3', 'q4']
            ))
            
            for link in concall_links[:limit]:
                try:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    if href.startswith('/'):
                        href = self.BASE_URL + href
                    
                    concalls.append({
                        "title": text,
                        "url": href,
                        "type": "concall_transcript",
                    })
                except Exception as e:
                    logger.debug(f"Error parsing concall link: {e}")
                    continue
            
            return concalls
        except Exception as e:
            logger.warning(f"Error fetching concall transcripts from Screener.in for {ticker}: {e}")
            return []
    
    def is_indian_stock(self, ticker: str) -> bool:
        """Check if ticker represents an Indian stock (NSE/BSE).
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            True if ticker ends with .NS (NSE) or .BO (BSE)
        """
        return ticker.upper().endswith(('.NS', '.BO'))
    
    def get_financial_metrics_page(self, ticker: str) -> Optional[Dict]:
        """Get key financial metrics from Screener.in company page (light scrape).
        
        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            
        Returns:
            Dictionary with market cap, PE, dividend yield, etc. or None
        """
        if not self.enabled:
            return None
        
        try:
            normalized = self._normalize_ticker(ticker)
            url = f"{self.BASE_URL}/company/{normalized}"
            
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'lxml')
            metrics = {}
            
            # This is a heuristic scrape; Screener.in structure may vary
            # Look for key metric boxes on the page
            metric_boxes = soup.find_all('div', class_='metric')
            
            for box in metric_boxes[:10]:
                try:
                    label = box.find('span', class_='label')
                    value = box.find('span', class_='value')
                    
                    if label and value:
                        key = label.get_text(strip=True).lower().replace(' ', '_')
                        val = value.get_text(strip=True)
                        metrics[key] = val
                except Exception:
                    continue
            
            return metrics if metrics else None
        except Exception as e:
            logger.warning(f"Error fetching metrics from Screener.in for {ticker}: {e}")
            return None
