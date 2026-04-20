"""Shared data models for GoldTracker."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HistoricalPriceSeries:
    """Represents a historical time series of gold prices."""

    dates: list
    prices: list[float]
    unit_label: str = "USD/gram"
    source_label: str = "Yahoo Finance (GC=F)"
    title: str = "Gold"

    def __post_init__(self) -> None:
        """Validate that the history series contains aligned non-empty data."""
        if len(self.dates) != len(self.prices):
            raise ValueError("History dates and prices must have the same length")
        if not self.dates:
            raise ValueError("History series cannot be empty")

    @property
    def start_date(self):
        """Return the first date in the series."""
        return self.dates[0]

    @property
    def end_date(self):
        """Return the last date in the series."""
        return self.dates[-1]

    @property
    def point_count(self) -> int:
        """Return the number of data points in the series."""
        return len(self.prices)

    @property
    def start_price(self) -> float:
        """Return the first visible price in the series."""
        return self.prices[0]

    @property
    def latest_price(self) -> float:
        """Return the latest visible price in the series."""
        return self.prices[-1]

    @property
    def lowest_price(self) -> float:
        """Return the minimum price in the current series window."""
        return min(self.prices)

    @property
    def highest_price(self) -> float:
        """Return the maximum price in the current series window."""
        return max(self.prices)

    @property
    def average_price(self) -> float:
        """Return the arithmetic mean price for the current series window."""
        return sum(self.prices) / len(self.prices)

    @property
    def absolute_change(self) -> float:
        """Return the absolute price change across the visible series window."""
        return self.latest_price - self.start_price

    @property
    def percent_change(self) -> float:
        """Return the percentage price change across the visible series window."""
        if self.start_price == 0:
            return 0.0
        return (self.absolute_change / self.start_price) * 100

    @property
    def change_direction(self) -> str:
        """Return whether the visible series trend is up, down, or flat."""
        if self.absolute_change > 0:
            return "up"
        if self.absolute_change < 0:
            return "down"
        return "flat"

    @property
    def date_range_label(self) -> str:
        """Return a human-readable label for the visible date range."""
        return f"{self.start_date:%b %d, %Y} - {self.end_date:%b %d, %Y}"
