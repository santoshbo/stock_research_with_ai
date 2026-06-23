"""Groq LLM client for narrative generation."""

import logging
from typing import Optional
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import Config

logger = logging.getLogger(__name__)


class GroqClient:
    """Wrapper for Groq LLM inference."""
    
    def __init__(self, model: str = "mixtral-8x7b-32768", temperature: float = 0.7):
        """Initialize Groq client.
        
        Args:
            model: Model ID (default: Mixtral 8x7B)
            temperature: Temperature for response generation (0-1)
        """
        self.model = model
        self.temperature = temperature
        
        try:
            self.client = ChatGroq(
                model=model,
                temperature=temperature,
                groq_api_key=Config.GROQ_API_KEY,
            )
            logger.info(f"Initialized Groq client with model: {model}")
        except Exception as e:
            logger.error(f"Error initializing Groq client: {e}")
            self.client = None
    
    def generate_analysis_narrative(
        self,
        ticker: str,
        company_name: str,
        financial_summary: str,
        growth_analysis: str,
        current_price: float,
        key_metrics: str,
    ) -> Optional[str]:
        """Generate investment analysis narrative.
        
        Args:
            ticker: Stock ticker
            company_name: Company name
            financial_summary: Summary of financial metrics
            growth_analysis: Growth trend analysis
            current_price: Current stock price
            key_metrics: Key performance metrics
            
        Returns:
            Generated narrative or None if generation fails
        """
        if not self.client:
            logger.warning("Groq client not initialized; skipping narrative generation")
            return None
        
        try:
            prompt = f"""
Analyze this stock and provide a brief investment narrative (2-3 sentences):

Ticker: {ticker}
Company: {company_name}
Current Price: {current_price}

Financial Summary: {financial_summary}

Growth Analysis: {growth_analysis}

Key Metrics: {key_metrics}

Provide a concise, educational narrative about the stock's investment characteristics. 
Focus on business fundamentals and growth potential. Avoid direct investment advice.
"""
            
            messages = [
                SystemMessage(content="You are an investment analyst providing educational stock research. Be concise, balanced, and educational. Never provide direct investment advice."),
                HumanMessage(content=prompt),
            ]
            
            response = self.client.invoke(messages)
            narrative = response.content.strip() if response else None
            
            if narrative:
                logger.debug(f"Generated narrative for {ticker}")
            
            return narrative
        except Exception as e:
            logger.error(f"Error generating narrative for {ticker}: {e}")
            return None
    
    def generate_risk_summary(
        self,
        ticker: str,
        financial_risks: str,
        market_risks: str,
        business_risks: str,
    ) -> Optional[str]:
        """Generate risk analysis summary.
        
        Args:
            ticker: Stock ticker
            financial_risks: Financial risk factors
            market_risks: Market/macro risk factors
            business_risks: Business/operational risk factors
            
        Returns:
            Generated risk summary or None if generation fails
        """
        if not self.client:
            return None
        
        try:
            prompt = f"""
Provide a concise risk summary (2-3 sentences) for this stock:

Ticker: {ticker}

Financial Risks: {financial_risks}
Market Risks: {market_risks}
Business Risks: {business_risks}

Be balanced and educational. Highlight the most material risks without fearmongering.
"""
            
            messages = [
                SystemMessage(content="You are a financial risk analyst. Provide balanced, educational risk assessments."),
                HumanMessage(content=prompt),
            ]
            
            response = self.client.invoke(messages)
            summary = response.content.strip() if response else None
            
            if summary:
                logger.debug(f"Generated risk summary for {ticker}")
            
            return summary
        except Exception as e:
            logger.error(f"Error generating risk summary for {ticker}: {e}")
            return None
    
    def generate_recommendation_rationale(
        self,
        ticker: str,
        signal: str,
        key_drivers: str,
        alternatives: str,
    ) -> Optional[str]:
        """Generate recommendation rationale.
        
        Args:
            ticker: Stock ticker
            signal: Buy/Hold/Sell signal
            key_drivers: Key factors driving recommendation
            alternatives: Alternative viewpoints or caveats
            
        Returns:
            Generated rationale or None if generation fails
        """
        if not self.client:
            return None
        
        try:
            prompt = f"""
Generate an educational rationale (2-3 sentences) for this investment signal:

Ticker: {ticker}
Signal: {signal}

Key Drivers: {key_drivers}
Caveats/Alternatives: {alternatives}

Frame as educational analysis, not investment advice. 
Emphasize that this is ONE analytical lens and past performance doesn't guarantee results.
"""
            
            messages = [
                SystemMessage(content="You are an investment educator. Provide educational, balanced perspectives on stocks. Always include appropriate disclaimers about investment advice."),
                HumanMessage(content=prompt),
            ]
            
            response = self.client.invoke(messages)
            rationale = response.content.strip() if response else None
            
            if rationale:
                logger.debug(f"Generated recommendation rationale for {ticker}")
            
            return rationale
        except Exception as e:
            logger.error(f"Error generating recommendation rationale for {ticker}: {e}")
            return None
