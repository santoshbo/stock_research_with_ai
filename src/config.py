"""Application configuration loader and settings management."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


class Config:
    """Central configuration for the stock research application."""
    
    # Project directories
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "./reports"))
    CACHE_DIR = PROJECT_ROOT / ".cache"
    
    # Ensure reports directory exists
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    # API Keys (required)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY", None)
    
    # Model Configuration
    GROQ_MODEL = "mixtral-8x7b-32768"  # Primary model
    GOOGLE_MODEL = "gemini-pro"  # Fallback model
    
    # Timeouts (seconds)
    RESEARCH_TIMEOUT = int(os.getenv("RESEARCH_TIMEOUT_SECONDS", "120"))
    CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    SCREENER_IN_TIMEOUT = int(os.getenv("SCREENER_IN_TIMEOUT", "30"))
    
    # Feature Flags
    ENABLE_SCREENER_IN = os.getenv("ENABLE_SCREENER_IN", "true").lower() == "true"
    PDF_INCLUDE_CHARTS = os.getenv("PDF_INCLUDE_CHARTS", "true").lower() == "true"
    
    # UI Configuration
    MAX_SEARCH_HISTORY = int(os.getenv("MAX_SEARCH_HISTORY", "20"))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY not set. Please set it in .env or environment variables. "
                "Get your key from https://console.groq.com/keys"
            )
    
    @classmethod
    def to_dict(cls) -> dict:
        """Return config as dictionary (for logging, excludes sensitive keys)."""
        return {
            "project_root": str(cls.PROJECT_ROOT),
            "reports_dir": str(cls.REPORTS_DIR),
            "groq_model": cls.GROQ_MODEL,
            "research_timeout": cls.RESEARCH_TIMEOUT,
            "cache_ttl": cls.CACHE_TTL,
            "enable_screener_in": cls.ENABLE_SCREENER_IN,
            "max_search_history": cls.MAX_SEARCH_HISTORY,
            "log_level": cls.LOG_LEVEL,
        }


# Validate on import
try:
    Config.validate()
except ValueError as e:
    print(f"⚠️  Configuration warning: {e}")
