"""Search history persistence and management."""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.config import Config
from src.models.research import SearchHistory, Recommendation

logger = logging.getLogger(__name__)


class SearchHistoryStore:
    """Manages and persists recent search history."""
    
    def __init__(self, max_history: int = 20):
        """Initialize search history store.
        
        Args:
            max_history: Maximum number of searches to retain
        """
        self.max_history = max_history
        self.history_file = Config.CACHE_DIR / "search_history.json"
        self.history: List[SearchHistory] = []
        self._load_history()
    
    def add_search(
        self,
        ticker: str,
        company_name: Optional[str] = None,
        recommendation: Optional[Recommendation] = None,
        report_path: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> SearchHistory:
        """Add a new search to history.
        
        Args:
            ticker: Stock ticker
            company_name: Company name
            recommendation: Investment recommendation
            report_path: Path to generated report
            status: Search status (success, partial, failed)
            error_message: Error message if failed
            
        Returns:
            SearchHistory object that was added
        """
        try:
            import uuid
            
            search = SearchHistory(
                id=str(uuid.uuid4())[:8],
                ticker=ticker,
                company_name=company_name,
                timestamp=datetime.now(),
                recommendation=recommendation,
                report_path=report_path,
                status=status,
                error_message=error_message,
            )
            
            # Add to front of list
            self.history.insert(0, search)
            
            # Enforce max history size
            if len(self.history) > self.max_history:
                self.history = self.history[:self.max_history]
            
            # Persist to disk
            self._save_history()
            
            logger.info(f"Added search to history: {ticker}")
            return search
        except Exception as e:
            logger.error(f"Error adding search to history: {e}")
            raise
    
    def get_history(self) -> List[SearchHistory]:
        """Get all search history entries (most recent first).
        
        Returns:
            List of SearchHistory objects
        """
        return self.history[:self.max_history]
    
    def get_by_ticker(self, ticker: str) -> List[SearchHistory]:
        """Get all searches for a specific ticker.
        
        Args:
            ticker: Stock ticker
            
        Returns:
            List of SearchHistory objects for that ticker
        """
        return [s for s in self.history if s.ticker == ticker]
    
    def get_latest_for_ticker(self, ticker: str) -> Optional[SearchHistory]:
        """Get most recent search for a ticker.
        
        Args:
            ticker: Stock ticker
            
        Returns:
            Most recent SearchHistory object or None
        """
        matches = self.get_by_ticker(ticker)
        return matches[0] if matches else None
    
    def clear_history(self) -> None:
        """Clear all search history."""
        try:
            self.history.clear()
            self._save_history()
            logger.info("Cleared search history")
        except Exception as e:
            logger.error(f"Error clearing history: {e}")
    
    def _load_history(self) -> None:
        """Load history from disk."""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                
                self.history = []
                for item in data:
                    try:
                        search = SearchHistory(
                            id=item.get('id'),
                            ticker=item.get('ticker'),
                            company_name=item.get('company_name'),
                            timestamp=datetime.fromisoformat(item.get('timestamp', datetime.now().isoformat())),
                            recommendation=Recommendation(item.get('recommendation')) if item.get('recommendation') else None,
                            report_path=item.get('report_path'),
                            status=item.get('status', 'success'),
                            error_message=item.get('error_message'),
                        )
                        self.history.append(search)
                    except Exception as e:
                        logger.warning(f"Error parsing history entry: {e}")
                        continue
                
                logger.info(f"Loaded {len(self.history)} search history entries")
            else:
                logger.info("No existing search history found")
                self.history = []
        except Exception as e:
            logger.error(f"Error loading search history: {e}")
            self.history = []
    
    def _save_history(self) -> None:
        """Save history to disk."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = []
            for search in self.history:
                data.append({
                    'id': search.id,
                    'ticker': search.ticker,
                    'company_name': search.company_name,
                    'timestamp': search.timestamp.isoformat(),
                    'recommendation': search.recommendation.value if search.recommendation else None,
                    'report_path': search.report_path,
                    'status': search.status,
                    'error_message': search.error_message,
                })
            
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Saved {len(self.history)} search history entries")
        except Exception as e:
            logger.error(f"Error saving search history: {e}")
