"""Data models for Firestore persistence."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TradeRecord:
    """Represents a trade record in Firestore."""
    
    symbol: str
    action: str  # "BUY" or "SELL"
    quantity: float
    price: float  # per share
    total: float  # total cost/proceeds
    timestamp: datetime
    trade_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to Firestore-compatible dictionary."""
        return {
            "symbol": self.symbol.upper(),
            "action": self.action,
            "quantity": self.quantity,
            "price": self.price,
            "total": self.total,
            "timestamp": self.timestamp,
            "trade_id": self.trade_id,
        }


@dataclass
class OwnershipRecord:
    """Represents ownership record in Firestore."""
    
    symbol: str
    quantity: float
    total_cost: float  # cumulative cost basis
    first_purchase_date: datetime
    last_purchase_date: datetime
    last_updated: datetime
    
    def to_dict(self) -> dict:
        """Convert to Firestore-compatible dictionary."""
        return {
            "symbol": self.symbol.upper(),
            "quantity": self.quantity,
            "total_cost": self.total_cost,
            "first_purchase_date": self.first_purchase_date,
            "last_purchase_date": self.last_purchase_date,
            "last_updated": self.last_updated,
        }


@dataclass
class ExternalSaleRecord:
    """Represents an external sale detection."""
    
    symbol: str
    quantity: float
    estimated_proceeds: float
    detected_date: datetime
    used_for_reinvestment: bool = False
    reinvestment_date: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to Firestore-compatible dictionary."""
        return {
            "symbol": self.symbol.upper(),
            "quantity": self.quantity,
            "estimated_proceeds": self.estimated_proceeds,
            "detected_date": self.detected_date,
            "used_for_reinvestment": self.used_for_reinvestment,
            "reinvestment_date": self.reinvestment_date,
        }
