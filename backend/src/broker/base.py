"""
Base Broker Interface
Abstract base class for broker implementations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "SL"
    STOP_LOSS_MARKET = "SL-M"


class ProductType(str, Enum):
    INTRADAY = "INTRADAY"
    DELIVERY = "DELIVERY"
    MARGIN = "MARGIN"
    CARRYFORWARD = "CARRYFORWARD"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class OrderRequest:
    """Order request data structure"""
    symbol: str
    exchange: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    product_type: ProductType = ProductType.INTRADAY
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    symbol_token: Optional[str] = None
    tag: Optional[str] = None


@dataclass
class OrderResult:
    """Order execution result"""
    success: bool
    order_id: Optional[str] = None
    broker_order_id: Optional[str] = None
    message: str = ""
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    average_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class Position:
    """Open position data structure"""
    symbol: str
    exchange: str
    symbol_token: str
    quantity: int
    average_price: float
    ltp: float
    pnl: float
    pnl_pct: float
    product_type: ProductType
    side: OrderSide


@dataclass
class Holding:
    """Holdings data structure"""
    symbol: str
    exchange: str
    quantity: int
    average_price: float
    ltp: float
    pnl: float
    pnl_pct: float


@dataclass
class Quote:
    """Market quote data structure"""
    symbol: str
    exchange: str
    ltp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    bid: float
    ask: float
    timestamp: datetime


@dataclass
class Candle:
    """OHLCV candle data structure"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class BaseBroker(ABC):
    """
    Abstract base class for broker implementations.
    This interface allows the system to work with different brokers
    without changing the core trading logic.
    """
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection with the broker.
        Returns True if connection is successful.
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the broker."""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if broker connection is active."""
        pass
    
    @abstractmethod
    async def refresh_token(self) -> bool:
        """Refresh authentication token if needed."""
        pass
    
    # ============================================
    # Order Management
    # ============================================
    
    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResult:
        """
        Place a new order with the broker.
        
        Args:
            order: OrderRequest containing order details
            
        Returns:
            OrderResult with execution status
        """
        pass
    
    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None
    ) -> OrderResult:
        """Modify an existing order."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel an existing order."""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderResult:
        """Get current status of an order."""
        pass
    
    @abstractmethod
    async def get_order_book(self) -> List[Dict[str, Any]]:
        """Get all orders for the day."""
        pass
    
    # ============================================
    # Position & Holdings
    # ============================================
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
        pass
    
    @abstractmethod
    async def get_holdings(self) -> List[Holding]:
        """Get all holdings/portfolio."""
        pass
    
    # ============================================
    # Market Data
    # ============================================
    
    @abstractmethod
    async def get_ltp(self, symbol: str, exchange: str) -> float:
        """Get last traded price for a symbol."""
        pass
    
    @abstractmethod
    async def get_quote(self, symbol: str, exchange: str) -> Quote:
        """Get full market quote for a symbol."""
        pass
    
    @abstractmethod
    async def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Candle]:
        """
        Get historical OHLCV data.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code
            interval: Candle interval (1m, 5m, 15m, 1h, 1d)
            from_date: Start date
            to_date: End date
            
        Returns:
            List of Candle objects
        """
        pass
    
    # ============================================
    # Symbol Management
    # ============================================
    
    @abstractmethod
    async def get_symbol_token(self, symbol: str, exchange: str) -> str:
        """Get broker-specific token for a symbol."""
        pass
    
    @abstractmethod
    async def search_symbols(self, query: str) -> List[Dict[str, Any]]:
        """Search for symbols by name or code."""
        pass
    
    # ============================================
    # Account Information
    # ============================================
    
    @abstractmethod
    async def get_profile(self) -> Dict[str, Any]:
        """Get user profile information."""
        pass
    
    @abstractmethod
    async def get_funds(self) -> Dict[str, float]:
        """Get available funds/margins."""
        pass
