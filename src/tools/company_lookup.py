"""Company name to ticker lookup and fuzzy matching."""

import logging
from typing import Optional, List, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Company name to ticker mapping for quick lookups
COMPANY_TICKER_MAP = {
    # Indian companies (NSE)
    "reliance": "RELIANCE.NS",
    "reliance industries": "RELIANCE.NS",
    "tcs": "TCS.NS",
    "tata consultancy services": "TCS.NS",
    "infosys": "INFY.NS",
    "infy": "INFY.NS",
    "hdfc bank": "HDFCBANK.NS",
    "hdfc": "HDFCBANK.NS",
    "icici bank": "ICICIBANK.NS",
    "icici": "ICICIBANK.NS",
    "sbi": "SBIN.NS",
    "state bank of india": "SBIN.NS",
    "axis bank": "AXISBANK.NS",
    "axis": "AXISBANK.NS",
    "maruti": "MARUTI.NS",
    "maruti suzuki": "MARUTI.NS",
    "bharti airtel": "BHARTIARTL.NS",
    "airtel": "BHARTIARTL.NS",
    "ipl": "IPL.NS",
    "india post": "INDIAPOST.NS",
    "coal india": "COALINDIA.NS",
    "oil and natural gas": "ONGC.NS",
    "ongc": "ONGC.NS",
    "power grid": "POWERGRID.NS",
    "ntpc": "NTPC.NS",
    "indian oil": "IOCL.NS",
    "iocl": "IOCL.NS",
    "bajaj auto": "BAJAJAUT.NS",
    "bajaj": "BAJAJAUT.NS",
    "hero motocorp": "HEROMOTOCO.NS",
    "hero": "HEROMOTOCO.NS",
    "m&m": "MM.NS",
    "mahindra": "MM.NS",
    "mahindra & mahindra": "MM.NS",
    "lupin": "LUPIN.NS",
    "dr. reddy's": "DRREDDY.NS",
    "drreddy": "DRREDDY.NS",
    "sun pharma": "SUNPHARMA.NS",
    "cipla": "CIPLA.NS",
    "hcl technologies": "HCLTECH.NS",
    "hcl tech": "HCLTECH.NS",
    "wipro": "WIPRO.NS",
    "mindtree": "MINDTREE.NS",
    "tech mahindra": "TECHM.NS",
    
    # US companies (NASDAQ/NYSE)
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "meta": "META",
    "facebook": "META",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "elon musk": "TSLA",
    "berkshire": "BRK.B",
    "buffett": "BRK.B",
    "jp morgan": "JPM",
    "bank of america": "BAC",
    "wells fargo": "WFC",
    "goldman sachs": "GS",
    "morgan stanley": "MS",
    "coca cola": "KO",
    "pepsi": "PEP",
    "walmart": "WMT",
    "costco": "COST",
    "target": "TGT",
    "home depot": "HD",
    "lowes": "LOW",
    "mcdonalds": "MCD",
    "starbucks": "SBUX",
    "nike": "NKE",
    "adidas": "ADDYY",
    "facebook": "META",
    "intel": "INTC",
    "amd": "AMD",
    "qualcomm": "QCOM",
    "broadcom": "AVGO",
    "cisco": "CSCO",
    "ibm": "IBM",
    "oracle": "ORCL",
    "salesforce": "CRM",
    "adobe": "ADBE",
    "paypal": "PYPL",
    "square": "SQ",
    "uber": "UBER",
    "airbnb": "ABNB",
    "spotify": "SPOT",
    "netflix": "NFLX",
    "disney": "DIS",
    "comcast": "CMCSA",
    "verizon": "VZ",
    "at&t": "T",
    "t-mobile": "TMUS",
    "exxon": "XOM",
    "chevron": "CVX",
    "shell": "SHEL",
    "bp": "BP",
    "johnson & johnson": "JNJ",
    "pfizer": "PFE",
    "moderna": "MRNA",
    "merck": "MRK",
    "abbvie": "ABBV",
    "eli lilly": "LLY",
    "astrazeneca": "AZN",
}


class CompanyLookup:
    """Fuzzy match company names to ticker symbols."""
    
    @staticmethod
    def lookup(query: str) -> Optional[str]:
        """Look up company name or ticker and return normalized ticker.
        
        Args:
            query: Company name or ticker symbol
            
        Returns:
            Normalized ticker symbol or None
        """
        if not query:
            return None
        
        query = query.strip().upper()
        
        # Exact match on Indian ticker format
        if query.endswith('.NS') or query.endswith('.BO') or query.endswith('.BSE'):
            return query
        
        # Normalize and search in map
        normalized = query.lower().strip()
        
        # Exact match first
        if normalized in COMPANY_TICKER_MAP:
            return COMPANY_TICKER_MAP[normalized]
        
        # Fuzzy match (before returning query as-is)
        best_match = CompanyLookup._fuzzy_match(normalized)
        if best_match:
            return COMPANY_TICKER_MAP[best_match]
        
        # If it looks like a US ticker (short uppercase, no spaces), return as-is
        if len(query) <= 5 and not any(c.isspace() for c in query) and query.isalpha():
            return query
        
        # No match found, return original query (could be a new/unknown company)
        return query
    
    @staticmethod
    def _fuzzy_match(query: str, threshold: float = 0.6) -> Optional[str]:
        """Find best fuzzy match in company map.
        
        Args:
            query: Normalized company name query
            threshold: Similarity threshold (0-1)
            
        Returns:
            Best matching key or None
        """
        best_match = None
        best_score = threshold
        
        for company_name in COMPANY_TICKER_MAP.keys():
            # Check if query is substring
            if query in company_name or company_name in query:
                return company_name
            
            # Fuzzy match
            score = SequenceMatcher(None, query, company_name).ratio()
            if score > best_score:
                best_score = score
                best_match = company_name
        
        return best_match
    
    @staticmethod
    def get_suggestions(partial_query: str, limit: int = 5) -> List[Tuple[str, str]]:
        """Get auto-complete suggestions for partial query.
        
        Args:
            partial_query: Partial company name
            limit: Max number of suggestions
            
        Returns:
            List of (company_name, ticker) tuples
        """
        if not partial_query:
            return []
        
        partial = partial_query.lower().strip()
        matches = []
        
        for company_name, ticker in COMPANY_TICKER_MAP.items():
            if company_name.startswith(partial) or partial in company_name:
                matches.append((company_name, ticker))
        
        # Sort by relevance (starts with query first)
        matches.sort(key=lambda x: (not x[0].startswith(partial), x[0]))
        
        return matches[:limit]
