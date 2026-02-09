"""
Execution Agent
Responsible for order placement and position management
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from loguru import logger

from .base import BaseAgent, AgentType, AgentMessage, MessageType
from ..broker import BrokerFactory, BaseBroker, OrderRequest, OrderSide, OrderType, ProductType
from ..config.settings import settings, TradingMode


class ExecutionAgent(BaseAgent):
    """
    Execution Agent - The Executor.
    Places orders via broker abstraction (doesn't know if live or paper).
    """
    
    def __init__(self, name: str = "ExecutionAgent", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, AgentType.EXECUTION, config or {})
        
        self._broker: Optional[BaseBroker] = None
        self._pending_orders: Dict[str, Dict] = {}
        self._executed_trades: List[Dict] = []
    
    async def initialize(self) -> bool:
        self._broker = BrokerFactory.get_instance()
        if not self._broker:
            self._broker = BrokerFactory.create()
        
        if self._broker:
            try:
                if not await self._broker.is_connected():
                    connected = await self._broker.connect()
                    if not connected:
                        logger.warning("Broker not connected - ExecutionAgent will wait")
            except Exception as e:
                logger.warning(f"Broker connection check failed: {e}")
        else:
            logger.warning("No broker available - ExecutionAgent running in limited mode")
        
        logger.info(f"ExecutionAgent initialized - Mode: {settings.trading_mode.value}")
        return True
    
    async def process_cycle(self) -> List[AgentMessage]:
        messages = []
        
        for msg in self.get_pending_messages():
            if msg.type == MessageType.DECISION:
                result = await self._execute_decision(msg.payload)
                messages.append(AgentMessage(
                    type=MessageType.EXECUTION,
                    source_agent=self.name,
                    payload=result,
                    priority=2
                ))
        
        # Update pending orders status
        await self._update_order_status()
        
        return messages
    
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.type == MessageType.DECISION:
            result = await self._execute_decision(message.payload)
            return AgentMessage(
                type=MessageType.EXECUTION,
                source_agent=self.name,
                target_agent=message.source_agent,
                payload=result,
                correlation_id=message.id
            )
        return None
    
    async def shutdown(self) -> None:
        # Cancel any pending orders
        for order_id in list(self._pending_orders.keys()):
            try:
                await self._broker.cancel_order(order_id)
            except:
                pass
        logger.info("ExecutionAgent shutdown")
    
    async def _execute_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a trading decision."""
        result = {
            "success": False,
            "trade_id": str(uuid.uuid4())[:12],
            "symbol": decision.get("symbol", ""),
            "action": decision.get("action", ""),
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            action = decision.get("action", "").upper()
            if action not in ["BUY", "SELL"]:
                result["error"] = f"Invalid action: {action}"
                return result
            
            symbol = decision.get("symbol", "")
            exchange = decision.get("exchange", "NSE")
            entry_price = decision.get("entry_price", 0)
            stop_loss = decision.get("stop_loss") or decision.get("risk_assessment", {}).get("adjusted_stop_loss")
            take_profit = decision.get("take_profit") or decision.get("risk_assessment", {}).get("adjusted_take_profit")
            
            # Calculate quantity
            position_size = decision.get("risk_assessment", {}).get("position_size", 1)
            if isinstance(position_size, float) and position_size <= 1:
                # It's a percentage
                max_pos = settings.max_position_size
                quantity = int((max_pos * position_size) / entry_price) if entry_price > 0 else 1
            else:
                quantity = int(position_size)
            
            quantity = max(1, quantity)
            
            # Create order request
            order = OrderRequest(
                symbol=symbol,
                exchange=exchange,
                side=OrderSide.BUY if action == "BUY" else OrderSide.SELL,
                quantity=quantity,
                order_type=OrderType.MARKET,
                product_type=ProductType.INTRADAY,
                tag=f"LLM_{result['trade_id']}"
            )
            
            # Place main order
            order_result = await self._broker.place_order(order)
            
            if order_result.success:
                result["success"] = True
                result["order_id"] = order_result.order_id
                result["quantity"] = quantity
                result["fill_price"] = order_result.average_price or entry_price
                result["status"] = order_result.status.value
                
                # Place stop loss order
                if stop_loss:
                    sl_order = OrderRequest(
                        symbol=symbol,
                        exchange=exchange,
                        side=OrderSide.SELL if action == "BUY" else OrderSide.BUY,
                        quantity=quantity,
                        order_type=OrderType.STOP_LOSS_MARKET,
                        product_type=ProductType.INTRADAY,
                        trigger_price=stop_loss,
                        tag=f"SL_{result['trade_id']}"
                    )
                    sl_result = await self._broker.place_order(sl_order)
                    result["sl_order_id"] = sl_result.order_id if sl_result.success else None
                
                # Store trade
                self._executed_trades.append(result)
                logger.info(f"Order executed: {symbol} {action} {quantity} @ ₹{result['fill_price']:.2f}")
            else:
                result["error"] = order_result.message
                logger.error(f"Order failed: {order_result.message}")
                
        except Exception as e:
            result["error"] = str(e)
            self.log_error(f"Execution error: {str(e)}")
        
        return result
    
    async def _update_order_status(self) -> None:
        """Update status of pending orders."""
        for order_id in list(self._pending_orders.keys()):
            try:
                status = await self._broker.get_order_status(order_id)
                if status.success:
                    self._pending_orders[order_id]["status"] = status.status.value
                    if status.status.value in ["FILLED", "CANCELLED", "REJECTED"]:
                        del self._pending_orders[order_id]
            except:
                pass
    
    async def get_positions(self) -> List[Dict]:
        """Get current positions."""
        if self._broker:
            positions = await self._broker.get_positions()
            return [{"symbol": p.symbol, "quantity": p.quantity, "pnl": p.pnl} for p in positions]
        return []
    
    async def close_position(self, symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
        """Close an open position."""
        positions = await self._broker.get_positions()
        
        for pos in positions:
            if pos.symbol == symbol:
                order = OrderRequest(
                    symbol=symbol,
                    exchange=exchange,
                    side=OrderSide.SELL if pos.side == OrderSide.BUY else OrderSide.BUY,
                    quantity=pos.quantity,
                    order_type=OrderType.MARKET,
                    product_type=ProductType.INTRADAY
                )
                result = await self._broker.place_order(order)
                return {"success": result.success, "message": result.message}
        
        return {"success": False, "message": "Position not found"}
