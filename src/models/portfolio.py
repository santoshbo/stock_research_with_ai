"""Portfolio data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PortfolioHolding:
    """Represents a single stock holding in the portfolio."""

    id: int
    ticker: str
    company_name: str
    quantity: float
    buying_price: float
    date_purchased: datetime
    current_price: Optional[float] = None
    currency: str = "USD"
    portfolio_type: str = "MIDTERM"
    broker_account: str = "ZERODHA"

    # Target tracking
    target_1_price: Optional[float] = None
    target_2_price: Optional[float] = None
    target_1_achieved: bool = False
    target_2_achieved: bool = False
    target_1_achieved_at: Optional[datetime] = None
    target_2_achieved_at: Optional[datetime] = None
    target_1_notified: bool = False
    target_2_notified: bool = False

    # Partial profit-booking tracking
    partial_sold_quantity: float = 0.0
    partial_realized_pl: float = 0.0

    # Sold position fields
    is_sold: bool = False
    sell_price: Optional[float] = None
    sell_date: Optional[datetime] = None

    @property
    def remaining_quantity(self) -> float:
        """Quantity still held after any partial sales."""
        return max(self.quantity - self.partial_sold_quantity, 0.0)

    @property
    def total_invested(self) -> float:
        return self.quantity * self.buying_price

    @property
    def current_value(self) -> float:
        if self.is_sold:
            return 0.0
        if self.current_price is not None:
            return self.remaining_quantity * self.current_price
        return self.total_invested

    @property
    def unrealized_pl(self) -> float:
        """Unrealized profit/loss (only for active holdings)."""
        if self.is_sold or self.current_price is None:
            return 0.0
        return (self.current_price - self.buying_price) * self.remaining_quantity

    @property
    def realized_pl(self) -> float:
        """Realized profit/loss (only for sold holdings)."""
        realized = self.partial_realized_pl
        if self.is_sold and self.sell_price is not None:
            realized += (self.sell_price - self.buying_price) * self.remaining_quantity
        return realized

    @property
    def unrealized_pl_pct(self) -> float:
        """Unrealized P&L as percentage."""
        if self.is_sold or self.current_price is None or self.buying_price == 0:
            return 0.0
        return ((self.current_price - self.buying_price) / self.buying_price) * 100

    @property
    def realized_pl_pct(self) -> float:
        """Realized P&L as percentage."""
        if self.buying_price == 0:
            return 0.0
        return (self.realized_pl / self.total_invested) * 100 if self.total_invested else 0.0

    @property
    def invested_on(self) -> str:
        """Purchase date in YYYY-MM-DD format."""
        return self.date_purchased.strftime("%Y-%m-%d")

    @property
    def days_from_investment(self) -> int:
        """Number of days from purchase date until today."""
        return max((datetime.now().date() - self.date_purchased.date()).days, 0)

    @property
    def days_to_target(self) -> int:
        """For sold holdings, days between purchase and sell date."""
        if not self.sell_date:
            return 0
        return max((self.sell_date.date() - self.date_purchased.date()).days, 0)


@dataclass
class PortfolioSummary:
    """Aggregate summary of the entire portfolio."""

    total_invested: float = 0.0
    current_value: float = 0.0
    unrealized_pl: float = 0.0
    realized_pl: float = 0.0

    @property
    def total_pl(self) -> float:
        return self.unrealized_pl + self.realized_pl

    @property
    def unrealized_pl_pct(self) -> float:
        if self.total_invested == 0:
            return 0.0
        return (self.unrealized_pl / self.total_invested) * 100

    @property
    def total_pl_pct(self) -> float:
        if self.total_invested == 0:
            return 0.0
        # Use total invested across all (active + sold) as denominator
        return (self.total_pl / self.total_invested) * 100 if self.total_invested else 0.0
