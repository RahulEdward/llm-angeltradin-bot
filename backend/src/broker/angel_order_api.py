"""
Angel One Order API

REST API for order placement, modification, and cancellation with Angel One broker.
Uses httpx for connection pooling and async-compatible requests.
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx
from loguru import logger


class AngelOrderAPI:
    """
    Angel One Order API wrapper.
    
    Handles all order-related operations including:
    - Place orders (market, limit, stop-loss)
    - Modify orders
    - Cancel orders
    - Get order book
    - Get trade book
    - Get positions
    - Get holdings
    - Smart order placement (position management)
    """
    
    BASE_URL = "https://apiconnect.angelbroking.com"
    
    def __init__(self, auth_token: str, api_key: str, client: httpx.Client = None):
        """
        Initialize the Order API.
        
        Args:
            auth_token: JWT auth token from login
            api_key: API key from Angel One
            client: Optional httpx client (for connection pooling)
        """
        self.auth_token = auth_token
        self.api_key = api_key
        self._client = client or httpx.Client(timeout=30.0)
        self._owns_client = client is None
        
    def _get_headers(self) -> Dict[str, str]:
        """Get standard headers for Angel One API."""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "CLIENT_LOCAL_IP",
            "X-ClientPublicIP": "CLIENT_PUBLIC_IP",
            "X-MACAddress": "MAC_ADDRESS",
            "X-PrivateKey": self.api_key,
        }
    
    def _make_request(
        self, 
        endpoint: str, 
        method: str = "GET", 
        payload: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make API request to Angel One.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST, etc.)
            payload: Request payload for POST requests
            
        Returns:
            JSON response as dictionary
        """
        url = f"{self.BASE_URL}{endpoint}"
        headers = self._get_headers()
        
        try:
            if method == "GET":
                response = self._client.get(url, headers=headers)
            elif method == "POST":
                content = json.dumps(payload) if payload else ""
                response = self._client.post(url, headers=headers, content=content)
            else:
                content = json.dumps(payload) if payload else ""
                response = self._client.request(method, url, headers=headers, content=content)
            
            if not response.text:
                return {}
            
            return response.json()
            
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from {endpoint}: {response.text}")
            return {}
        except Exception as e:
            logger.error(f"API request error: {e}")
            return {"status": False, "message": str(e)}
    
    def get_order_book(self) -> Dict[str, Any]:
        """Get all orders for the day."""
        return self._make_request("/rest/secure/angelbroking/order/v1/getOrderBook")
    
    def get_trade_book(self) -> Dict[str, Any]:
        """Get all trades for the day."""
        return self._make_request("/rest/secure/angelbroking/order/v1/getTradeBook")
    
    def get_positions(self) -> Dict[str, Any]:
        """Get current positions."""
        return self._make_request("/rest/secure/angelbroking/order/v1/getPosition")
    
    def get_holdings(self) -> Dict[str, Any]:
        """Get portfolio holdings."""
        return self._make_request("/rest/secure/angelbroking/portfolio/v1/getAllHolding")
    
    def get_funds(self) -> Dict[str, Any]:
        """Get available funds/margin."""
        return self._make_request("/rest/secure/angelbroking/user/v1/getRMS")
    
    def get_profile(self) -> Dict[str, Any]:
        """Get user profile."""
        return self._make_request("/rest/secure/angelbroking/user/v1/getProfile")
    
    def place_order(
        self,
        symbol: str,
        token: str,
        exchange: str,
        transaction_type: str,  # BUY or SELL
        quantity: int,
        order_type: str = "MARKET",  # MARKET, LIMIT, STOPLOSS_LIMIT, STOPLOSS_MARKET
        product_type: str = "INTRADAY",  # INTRADAY, DELIVERY, MARGIN
        price: float = 0,
        trigger_price: float = 0,
        variety: str = "NORMAL",  # NORMAL, STOPLOSS, AMO, ROBO
        duration: str = "DAY",  # DAY, IOC
        squareoff: float = 0,
        stoploss: float = 0,
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Place an order.
        
        Args:
            symbol: Trading symbol
            token: Symbol token
            exchange: Exchange (NSE, BSE, NFO, MCX, etc.)
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: Order type (MARKET, LIMIT, etc.)
            product_type: Product type (INTRADAY, DELIVERY, etc.)
            price: Limit price (for LIMIT orders)
            trigger_price: Trigger price (for stop-loss orders)
            variety: Order variety
            duration: Order duration
            squareoff: Squareoff value (for bracket orders)
            stoploss: Stoploss value (for bracket orders)
            
        Returns:
            Tuple of (response dict, order_id or None)
        """
        payload = {
            "variety": variety,
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": transaction_type,
            "exchange": exchange,
            "ordertype": order_type,
            "producttype": product_type,
            "duration": duration,
            "price": str(price),
            "triggerprice": str(trigger_price),
            "squareoff": str(squareoff),
            "stoploss": str(stoploss),
            "quantity": str(quantity),
        }
        
        logger.debug(f"Placing order: {payload}")
        
        response = self._make_request(
            "/rest/secure/angelbroking/order/v1/placeOrder",
            method="POST",
            payload=payload
        )
        
        order_id = None
        if response.get("status") == True:
            order_id = response.get("data", {}).get("orderid")
            logger.info(f"Order placed successfully: {order_id}")
        else:
            logger.error(f"Order placement failed: {response.get('message')}")
            
        return response, order_id
    
    def modify_order(
        self,
        order_id: str,
        symbol: str,
        token: str,
        exchange: str,
        order_type: str,
        quantity: int,
        price: float = 0,
        trigger_price: float = 0,
        variety: str = "NORMAL",
        duration: str = "DAY",
    ) -> Dict[str, Any]:
        """
        Modify an existing order.
        
        Args:
            order_id: Order ID to modify
            symbol: Trading symbol
            token: Symbol token
            exchange: Exchange
            order_type: New order type
            quantity: New quantity
            price: New price
            trigger_price: New trigger price
            variety: Order variety
            duration: Order duration
            
        Returns:
            Response dictionary
        """
        payload = {
            "variety": variety,
            "orderid": order_id,
            "tradingsymbol": symbol,
            "symboltoken": token,
            "exchange": exchange,
            "ordertype": order_type,
            "quantity": str(quantity),
            "price": str(price),
            "triggerprice": str(trigger_price),
            "duration": duration,
        }
        
        response = self._make_request(
            "/rest/secure/angelbroking/order/v1/modifyOrder",
            method="POST",
            payload=payload
        )
        
        if response.get("status") == True or response.get("message") == "SUCCESS":
            return {"status": "success", "orderid": response.get("data", {}).get("orderid")}
        else:
            return {"status": "error", "message": response.get("message", "Failed to modify order")}
    
    def cancel_order(self, order_id: str, variety: str = "NORMAL") -> Dict[str, Any]:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            variety: Order variety
            
        Returns:
            Response dictionary
        """
        payload = {
            "variety": variety,
            "orderid": order_id,
        }
        
        response = self._make_request(
            "/rest/secure/angelbroking/order/v1/cancelOrder",
            method="POST",
            payload=payload
        )
        
        if response.get("status"):
            return {"status": "success", "orderid": order_id}
        else:
            return {"status": "error", "message": response.get("message", "Failed to cancel order")}
    
    def cancel_all_orders(self) -> Tuple[List[str], List[str]]:
        """
        Cancel all open orders.
        
        Returns:
            Tuple of (cancelled order IDs, failed order IDs)
        """
        order_book = self.get_order_book()
        
        if order_book.get("status") != True:
            return [], []
        
        # Filter orders that are open or trigger pending
        orders_to_cancel = [
            order for order in order_book.get("data", [])
            if order.get("status") in ["open", "trigger pending"]
        ]
        
        cancelled = []
        failed = []
        
        for order in orders_to_cancel:
            order_id = order.get("orderid")
            result = self.cancel_order(order_id)
            
            if result.get("status") == "success":
                cancelled.append(order_id)
            else:
                failed.append(order_id)
        
        return cancelled, failed
    
    def close_all_positions(self) -> Dict[str, Any]:
        """
        Close all open positions by placing opposite orders.
        
        Returns:
            Result dictionary
        """
        positions = self.get_positions()
        
        if not positions.get("data"):
            return {"status": "success", "message": "No open positions found"}
        
        closed = []
        failed = []
        
        for position in positions.get("data", []):
            net_qty = int(position.get("netqty", 0))
            
            if net_qty == 0:
                continue
            
            # Determine action based on position direction
            action = "SELL" if net_qty > 0 else "BUY"
            quantity = abs(net_qty)
            
            response, order_id = self.place_order(
                symbol=position.get("tradingsymbol"),
                token=position.get("symboltoken"),
                exchange=position.get("exchange"),
                transaction_type=action,
                quantity=quantity,
                order_type="MARKET",
                product_type=position.get("producttype", "INTRADAY"),
            )
            
            if order_id:
                closed.append(order_id)
            else:
                failed.append(position.get("tradingsymbol"))
        
        return {
            "status": "success",
            "message": f"Closed {len(closed)} positions",
            "closed_orders": closed,
            "failed": failed
        }
    
    def get_open_position(
        self, 
        symbol: str, 
        exchange: str, 
        product_type: str
    ) -> int:
        """
        Get net quantity for a specific position.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            product_type: Product type
            
        Returns:
            Net quantity (positive for long, negative for short, 0 if no position)
        """
        positions = self.get_positions()
        
        if not positions.get("status") or not positions.get("data"):
            return 0
        
        for position in positions.get("data", []):
            if (position.get("tradingsymbol") == symbol and
                position.get("exchange") == exchange and
                position.get("producttype") == product_type):
                return int(position.get("netqty", 0))
        
        return 0
    
    def smart_order(
        self,
        symbol: str,
        token: str,
        exchange: str,
        action: str,
        quantity: int,
        position_size: int,
        product_type: str = "INTRADAY",
        order_type: str = "MARKET",
        price: float = 0,
    ) -> Tuple[Optional[Dict], Dict[str, Any], Optional[str]]:
        """
        Smart order placement with position management.
        
        Automatically calculates the correct quantity and direction based on
        desired position size vs current position.
        
        Args:
            symbol: Trading symbol
            token: Symbol token
            exchange: Exchange
            action: BUY or SELL (for initial direction)
            quantity: Order quantity (if position_size is 0)
            position_size: Desired final position size
            product_type: Product type
            order_type: Order type
            price: Limit price (for LIMIT orders)
            
        Returns:
            Tuple of (raw response, response dict, order_id)
        """
        current_position = self.get_open_position(symbol, exchange, product_type)
        
        logger.info(f"Target position: {position_size}, Current: {current_position}")
        
        # If position_size matches current, no action needed
        if position_size == current_position:
            if quantity == 0:
                return None, {"status": "success", "message": "No open position found"}, None
            return None, {"status": "success", "message": "Position already at target"}, None
        
        # Calculate action and quantity needed
        final_action = None
        final_quantity = 0
        
        if position_size == 0 and current_position == 0 and quantity != 0:
            # New position
            final_action = action
            final_quantity = quantity
        elif position_size == 0 and current_position > 0:
            # Close long position
            final_action = "SELL"
            final_quantity = abs(current_position)
        elif position_size == 0 and current_position < 0:
            # Close short position
            final_action = "BUY"
            final_quantity = abs(current_position)
        elif current_position == 0:
            # Open new position
            final_action = "BUY" if position_size > 0 else "SELL"
            final_quantity = abs(position_size)
        elif position_size > current_position:
            # Increase position
            final_action = "BUY"
            final_quantity = position_size - current_position
        elif position_size < current_position:
            # Decrease position
            final_action = "SELL"
            final_quantity = current_position - position_size
        
        if final_action and final_quantity > 0:
            response, order_id = self.place_order(
                symbol=symbol,
                token=token,
                exchange=exchange,
                transaction_type=final_action,
                quantity=final_quantity,
                order_type=order_type,
                product_type=product_type,
                price=price,
            )
            return response, response, order_id
        
        return None, {"status": "success", "message": "No action needed"}, None
    
    def close(self):
        """Close the HTTP client if we own it."""
        if self._owns_client and self._client:
            self._client.close()
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
