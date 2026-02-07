"""
Paper Trading Broker Implementation
Simulates order execution using real market data without actual trades
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from loguru import logger

from .base import (
    BaseBroker, OrderRequest, OrderResult, Position, Holding,
    Quote, Candle, OrderSide, OrderType, ProductType, OrderStatus
)
from .angel_one import AngelOneBroker


class PaperBroker(BaseBroker):
    """
    Paper trading broker that simulates order execution.
    Uses real market data from Angel One but doesn't place actual orders.
    
    Features:
    - Simulated order execution with realistic fills
    - Position tracking
    - P&L calculation
    - Same interface as live broker
    """
    
    def __init__(
        self,
        data_broker: AngelOneBroker,
        initial_capital: float = 1000000.0
    ):
        """
        Initialize paper broker.
        
        Args:
            data_broker: Real broker for market data
            initial_capital: Starting simulated capital
        """
        self.data_broker = data_broker
        self.initial_capital = initial_capital
        self.available_capital = initial_capital
        
        # Simulated state
        self._orders: Dict[str, Dict] = {}
        self._positions: Dict[str, Position] = {}
        self._holdings: Dict[str, Holding] = {}
        self._order_book: List[Dict] = []
        self._trade_history: List[Dict] = []
        
        self._connected = False
    
    async def connect(self) -> bool:
        """Connect by initializing data broker."""
        try:
            self._connected = await self.data_broker.connect()
            if self._connected:
                logger.info(f"Paper broker connected with capital: ₹{self.initial_capital:,.2f}")
            return self._connected
        except Exception as e:
            logger.error(f"Paper broker connection error: {str(e)}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from data broker."""
        await self.data_broker.disconnect()
        self._connected = False
        logger.info("Paper broker disconnected")
    
    async def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected and await self.data_broker.is_connected()
    
    async def refresh_token(self) -> bool:
        """Refresh data broker token."""
        return await self.data_broker.refresh_token()
    
    # ============================================
    # Order Management (Simulated)
    # ============================================
    
    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Simulate order placement."""
        if not await self.is_connected():
            return OrderResult(success=False, message="Not connected")
        
        try:
            # Generate order ID
            order_id = f"PAPER_{uuid.uuid4().hex[:12].upper()}"
            
            # Get current market price
            quote = await self.data_broker.get_quote(order.symbol, order.exchange)
            if not quote:
                return OrderResult(
                    success=False,
                    message="Unable to get market quote",
                    status=OrderStatus.REJECTED
                )
            
            # Determine execution price
            if order.order_type == OrderType.MARKET:
                exec_price = quote.ask if order.side == OrderSide.BUY else quote.bid
                if exec_price == 0:
                    exec_price = quote.ltp
                status = OrderStatus.FILLED
            elif order.order_type == OrderType.LIMIT:
                # Check if limit order can be filled
                if order.side == OrderSide.BUY and order.price >= quote.ask:
                    exec_price = order.price
                    status = OrderStatus.FILLED
                elif order.side == OrderSide.SELL and order.price <= quote.bid:
                    exec_price = order.price
                    status = OrderStatus.FILLED
                else:
                    exec_price = 0
                    status = OrderStatus.OPEN
            else:
                # SL orders
                exec_price = 0
                status = OrderStatus.OPEN
            
            # Calculate trade value
            trade_value = exec_price * order.quantity
            
            # Check capital for buy orders
            if order.side == OrderSide.BUY and status == OrderStatus.FILLED:
                if trade_value > self.available_capital:
                    return OrderResult(
                        success=False,
                        message="Insufficient capital",
                        status=OrderStatus.REJECTED
                    )
                self.available_capital -= trade_value
            
            # Store order
            order_data = {
                "orderid": order_id,
                "tradingsymbol": order.symbol,
                "exchange": order.exchange,
                "transactiontype": order.side.value,
                "ordertype": order.order_type.value,
                "producttype": order.product_type.value,
                "quantity": order.quantity,
                "price": order.price or 0,
                "triggerprice": order.trigger_price or 0,
                "status": status.value.lower(),
                "filledshares": order.quantity if status == OrderStatus.FILLED else 0,
                "averageprice": exec_price,
                "timestamp": datetime.now().isoformat()
            }
            
            self._orders[order_id] = order_data
            self._order_book.append(order_data)
            
            # Update positions if filled
            if status == OrderStatus.FILLED:
                await self._update_position(order, exec_price)
            
            logger.info(
                f"[PAPER] Order {status.value}: {order_id} - "
                f"{order.symbol} {order.side.value} {order.quantity} @ ₹{exec_price:.2f}"
            )
            
            return OrderResult(
                success=True,
                order_id=order_id,
                broker_order_id=order_id,
                message=f"Paper order {status.value.lower()}",
                status=status,
                filled_quantity=order.quantity if status == OrderStatus.FILLED else 0,
                average_price=exec_price,
                raw_response=order_data
            )
            
        except Exception as e:
            logger.error(f"Paper order error: {str(e)}")
            return OrderResult(success=False, message=str(e))
    
    async def _update_position(self, order: OrderRequest, price: float) -> None:
        """Update positions after order fill."""
        pos_key = f"{order.exchange}:{order.symbol}"
        
        if pos_key in self._positions:
            pos = self._positions[pos_key]
            
            if order.side == OrderSide.BUY:
                if pos.side == OrderSide.BUY:
                    # Add to long position
                    total_qty = pos.quantity + order.quantity
                    avg_price = (pos.average_price * pos.quantity + price * order.quantity) / total_qty
                    pos.quantity = total_qty
                    pos.average_price = avg_price
                else:
                    # Close short position
                    if order.quantity >= pos.quantity:
                        # Fully closed
                        realized_pnl = (pos.average_price - price) * pos.quantity
                        remaining = order.quantity - pos.quantity
                        
                        if remaining > 0:
                            # Flip to long
                            self._positions[pos_key] = Position(
                                symbol=order.symbol,
                                exchange=order.exchange,
                                symbol_token=order.symbol_token or "",
                                quantity=remaining,
                                average_price=price,
                                ltp=price,
                                pnl=0,
                                pnl_pct=0,
                                product_type=order.product_type,
                                side=OrderSide.BUY
                            )
                        else:
                            del self._positions[pos_key]
                        
                        self.available_capital += realized_pnl
                    else:
                        # Partially closed
                        realized_pnl = (pos.average_price - price) * order.quantity
                        pos.quantity -= order.quantity
                        self.available_capital += realized_pnl
            else:
                # SELL logic (mirror of BUY)
                if pos.side == OrderSide.SELL:
                    total_qty = pos.quantity + order.quantity
                    avg_price = (pos.average_price * pos.quantity + price * order.quantity) / total_qty
                    pos.quantity = total_qty
                    pos.average_price = avg_price
                else:
                    if order.quantity >= pos.quantity:
                        realized_pnl = (price - pos.average_price) * pos.quantity
                        remaining = order.quantity - pos.quantity
                        
                        if remaining > 0:
                            self._positions[pos_key] = Position(
                                symbol=order.symbol,
                                exchange=order.exchange,
                                symbol_token=order.symbol_token or "",
                                quantity=remaining,
                                average_price=price,
                                ltp=price,
                                pnl=0,
                                pnl_pct=0,
                                product_type=order.product_type,
                                side=OrderSide.SELL
                            )
                        else:
                            del self._positions[pos_key]
                        
                        self.available_capital += realized_pnl + (pos.average_price * pos.quantity)
                    else:
                        realized_pnl = (price - pos.average_price) * order.quantity
                        pos.quantity -= order.quantity
                        self.available_capital += realized_pnl + (pos.average_price * order.quantity)
        else:
            # New position
            self._positions[pos_key] = Position(
                symbol=order.symbol,
                exchange=order.exchange,
                symbol_token=order.symbol_token or "",
                quantity=order.quantity,
                average_price=price,
                ltp=price,
                pnl=0,
                pnl_pct=0,
                product_type=order.product_type,
                side=order.side
            )
    
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None
    ) -> OrderResult:
        """Modify a simulated order."""
        if order_id not in self._orders:
            return OrderResult(success=False, message="Order not found")
        
        order = self._orders[order_id]
        if order["status"] not in ["open", "pending"]:
            return OrderResult(
                success=False,
                message="Cannot modify completed order"
            )
        
        if quantity:
            order["quantity"] = quantity
        if price:
            order["price"] = price
        if trigger_price:
            order["triggerprice"] = trigger_price
        
        logger.info(f"[PAPER] Order modified: {order_id}")
        
        return OrderResult(
            success=True,
            order_id=order_id,
            message="Order modified",
            raw_response=order
        )
    
    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel a simulated order."""
        if order_id not in self._orders:
            return OrderResult(success=False, message="Order not found")
        
        order = self._orders[order_id]
        if order["status"] not in ["open", "pending"]:
            return OrderResult(
                success=False,
                message="Cannot cancel completed order"
            )
        
        order["status"] = "cancelled"
        logger.info(f"[PAPER] Order cancelled: {order_id}")
        
        return OrderResult(
            success=True,
            order_id=order_id,
            status=OrderStatus.CANCELLED,
            message="Order cancelled"
        )
    
    async def get_order_status(self, order_id: str) -> OrderResult:
        """Get status of a simulated order."""
        if order_id not in self._orders:
            return OrderResult(success=False, message="Order not found")
        
        order = self._orders[order_id]
        status_map = {
            "complete": OrderStatus.FILLED,
            "filled": OrderStatus.FILLED,
            "rejected": OrderStatus.REJECTED,
            "cancelled": OrderStatus.CANCELLED,
            "open": OrderStatus.OPEN,
            "pending": OrderStatus.PENDING
        }
        
        return OrderResult(
            success=True,
            order_id=order_id,
            status=status_map.get(order["status"], OrderStatus.PENDING),
            filled_quantity=order.get("filledshares", 0),
            average_price=order.get("averageprice", 0),
            raw_response=order
        )
    
    async def get_order_book(self) -> List[Dict[str, Any]]:
        """Get all simulated orders."""
        return self._order_book.copy()
    
    # ============================================
    # Position & Holdings (Simulated)
    # ============================================
    
    async def get_positions(self) -> List[Position]:
        """Get simulated positions with updated P&L."""
        positions = []
        
        for pos_key, pos in self._positions.items():
            # Update LTP and P&L
            quote = await self.data_broker.get_quote(pos.symbol, pos.exchange)
            if quote:
                pos.ltp = quote.ltp
                if pos.side == OrderSide.BUY:
                    pos.pnl = (pos.ltp - pos.average_price) * pos.quantity
                else:
                    pos.pnl = (pos.average_price - pos.ltp) * pos.quantity
                pos.pnl_pct = (pos.pnl / (pos.average_price * pos.quantity)) * 100
            
            positions.append(pos)
        
        return positions
    
    async def get_holdings(self) -> List[Holding]:
        """Get simulated holdings."""
        return list(self._holdings.values())
    
    # ============================================
    # Market Data (Delegated to real broker)
    # ============================================
    
    async def get_ltp(self, symbol: str, exchange: str) -> float:
        """Get LTP from real data broker."""
        return await self.data_broker.get_ltp(symbol, exchange)
    
    async def get_quote(self, symbol: str, exchange: str) -> Optional[Quote]:
        """Get quote from real data broker."""
        return await self.data_broker.get_quote(symbol, exchange)
    
    async def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Candle]:
        """Get historical data from real data broker."""
        return await self.data_broker.get_historical_data(
            symbol, exchange, interval, from_date, to_date
        )
    
    async def get_symbol_token(self, symbol: str, exchange: str) -> str:
        """Get symbol token from real data broker."""
        return await self.data_broker.get_symbol_token(symbol, exchange)
    
    async def search_symbols(self, query: str) -> List[Dict[str, Any]]:
        """Search symbols via real data broker."""
        return await self.data_broker.search_symbols(query)
    
    # ============================================
    # Account Information (Simulated)
    # ============================================
    
    async def get_profile(self) -> Dict[str, Any]:
        """Get simulated profile."""
        return {
            "clientcode": "PAPER_USER",
            "name": "Paper Trading Account",
            "email": "paper@trading.local",
            "mobileno": "1234567890",
            "exchanges": ["NSE", "BSE", "NFO", "MCX"]
        }
    
    async def get_funds(self) -> Dict[str, float]:
        """Get simulated funds."""
        # Calculate used margin
        used_margin = sum(
            pos.average_price * pos.quantity
            for pos in self._positions.values()
        )
        
        return {
            "available_cash": self.available_capital,
            "available_margin": self.available_capital,
            "used_margin": used_margin,
            "collateral": 0.0,
            "initial_capital": self.initial_capital,
            "total_pnl": self.available_capital - self.initial_capital + used_margin
        }
    
    def reset(self) -> None:
        """Reset paper trading account."""
        self.available_capital = self.initial_capital
        self._orders.clear()
        self._positions.clear()
        self._holdings.clear()
        self._order_book.clear()
        self._trade_history.clear()
        logger.info("Paper trading account reset")
