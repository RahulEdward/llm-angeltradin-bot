"""
Angel One SmartAPI Broker Implementation
Production-ready integration with Angel One's trading platform
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
import pyotp
from loguru import logger

try:
    from SmartApi import SmartConnect
except ImportError:
    SmartConnect = None
    logger.warning("SmartApi not installed. Install with: pip install smartapi-python")

from .base import (
    BaseBroker, OrderRequest, OrderResult, Position, Holding,
    Quote, Candle, OrderSide, OrderType, ProductType, OrderStatus
)


class AngelOneBroker(BaseBroker):
    """
    Angel One SmartAPI broker implementation.
    Provides complete trading functionality for Indian markets.
    """
    
    # Exchange mappings
    EXCHANGE_MAP = {
        "NSE": "NSE",
        "BSE": "BSE",
        "NFO": "NFO",
        "MCX": "MCX",
        "BFO": "BFO",
        "CDS": "CDS"
    }
    
    # Interval mappings for historical data
    INTERVAL_MAP = {
        "1m": "ONE_MINUTE",
        "3m": "THREE_MINUTE",
        "5m": "FIVE_MINUTE",
        "10m": "TEN_MINUTE",
        "15m": "FIFTEEN_MINUTE",
        "30m": "THIRTY_MINUTE",
        "1h": "ONE_HOUR",
        "1d": "ONE_DAY"
    }
    
    # Product type mappings
    PRODUCT_MAP = {
        ProductType.INTRADAY: "INTRADAY",
        ProductType.DELIVERY: "DELIVERY",
        ProductType.MARGIN: "MARGIN",
        ProductType.CARRYFORWARD: "CARRYFORWARD"
    }
    
    # Order type mappings
    ORDER_TYPE_MAP = {
        OrderType.MARKET: "MARKET",
        OrderType.LIMIT: "LIMIT",
        OrderType.STOP_LOSS: "STOPLOSS_LIMIT",
        OrderType.STOP_LOSS_MARKET: "STOPLOSS_MARKET"
    }
    
    # Hardcoded NSE token map for common symbols (reliable fallback)
    NSE_TOKEN_MAP = {
        "RELIANCE": ("2885", "RELIANCE-EQ"),
        "TCS": ("11536", "TCS-EQ"),
        "INFY": ("1594", "INFY-EQ"),
        "HDFCBANK": ("1333", "HDFCBANK-EQ"),
        "ICICIBANK": ("4963", "ICICIBANK-EQ"),
        "SBIN": ("3045", "SBIN-EQ"),
        "WIPRO": ("3787", "WIPRO-EQ"),
        "BAJFINANCE": ("317", "BAJFINANCE-EQ"),
        "LT": ("11483", "LT-EQ"),
        "TATASTEEL": ("3499", "TATASTEEL-EQ"),
    }
    
    def __init__(
        self,
        api_key: str,
        client_id: str,
        password: str,
        totp_secret: str
    ):
        """
        Initialize Angel One broker connection.
        
        Args:
            api_key: Angel One API key
            client_id: Trading client ID
            password: Trading password
            totp_secret: TOTP secret for 2FA
        """
        self.api_key = api_key
        self.client_id = client_id
        self.password = password
        self.totp_secret = totp_secret
        
        self._client: Optional[SmartConnect] = None
        self._auth_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._feed_token: Optional[str] = None
        
        # Symbol token cache
        self._symbol_cache: Dict[str, str] = {}
        self._symbol_name_cache: Dict[str, str] = {}  # Maps "NSE:RELIANCE" -> "RELIANCE-EQ"
        
    async def connect(self) -> bool:
        """Establish connection with Angel One API."""
        if SmartConnect is None:
            logger.error("SmartApi library not available")
            return False
            
        try:
            self._client = SmartConnect(api_key=self.api_key)
            
            # Generate TOTP
            totp = pyotp.TOTP(self.totp_secret)
            totp_value = totp.now()
            
            # Login
            login_response = await asyncio.to_thread(
                self._client.generateSession,
                self.client_id,
                self.password,
                totp_value
            )
            
            if login_response.get("status"):
                self._auth_token = login_response["data"]["jwtToken"]
                self._refresh_token = login_response["data"]["refreshToken"]
                self._feed_token = login_response["data"]["feedToken"]
                self._token_expiry = datetime.now() + timedelta(hours=6)
                
                logger.info(f"Connected to Angel One - Client: {self.client_id}")
                return True
            else:
                logger.error(f"Login failed: {login_response.get('message')}")
                return False
                
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            return False
    
    async def disconnect(self) -> None:
        """Logout and disconnect from Angel One."""
        if self._client:
            try:
                await asyncio.to_thread(self._client.terminateSession, self.client_id)
                logger.info("Disconnected from Angel One")
            except Exception as e:
                logger.warning(f"Disconnect error: {str(e)}")
            finally:
                self._client = None
                self._auth_token = None
    
    async def is_connected(self) -> bool:
        """Check if connection is active."""
        if not self._client or not self._auth_token:
            return False
        
        # Check token expiry
        if self._token_expiry and datetime.now() >= self._token_expiry:
            return await self.refresh_token()
        
        return True
    
    async def refresh_token(self) -> bool:
        """Refresh the authentication token."""
        if not self._client or not self._refresh_token:
            return await self.connect()
        
        try:
            response = await asyncio.to_thread(
                self._client.generateToken,
                self._refresh_token
            )
            
            if response.get("status"):
                self._auth_token = response["data"]["jwtToken"]
                self._refresh_token = response["data"]["refreshToken"]
                self._token_expiry = datetime.now() + timedelta(hours=6)
                logger.info("Token refreshed successfully")
                return True
            else:
                logger.warning("Token refresh failed, reconnecting...")
                return await self.connect()
                
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            return await self.connect()
    
    # ============================================
    # Order Management
    # ============================================
    
    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Place a new order with Angel One."""
        if not await self.is_connected():
            return OrderResult(
                success=False,
                message="Not connected to broker"
            )
        
        try:
            # Get symbol token if not provided
            symbol_token = order.symbol_token
            if not symbol_token:
                symbol_token = await self.get_symbol_token(
                    order.symbol, order.exchange
                )
            
            if not symbol_token:
                return OrderResult(
                    success=False,
                    message=f"Could not resolve token for {order.exchange}:{order.symbol}",
                    status=OrderStatus.REJECTED
                )
            
            # Use resolved trading symbol (e.g., RELIANCE-EQ)
            cache_key = f"{order.exchange}:{order.symbol}"
            trading_symbol = self._symbol_name_cache.get(cache_key, order.symbol)
            
            logger.info(f"Placing order: {order.side.value} {trading_symbol} (token={symbol_token}) qty={order.quantity}")
            
            # Build order params (matching Angel One API exactly)
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": trading_symbol,
                "symboltoken": symbol_token,
                "transactiontype": order.side.value,
                "exchange": self.EXCHANGE_MAP.get(order.exchange, order.exchange),
                "ordertype": self.ORDER_TYPE_MAP.get(order.order_type, "MARKET"),
                "producttype": self.PRODUCT_MAP.get(order.product_type, "INTRADAY"),
                "duration": "DAY",
                "quantity": str(order.quantity),
                "squareoff": "0",
                "stoploss": "0",
            }
            
            # Add price for limit orders
            if order.order_type == OrderType.LIMIT and order.price:
                order_params["price"] = str(order.price)
            else:
                order_params["price"] = "0"
            
            # Add trigger price for SL orders
            if order.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LOSS_MARKET]:
                if order.trigger_price:
                    order_params["triggerprice"] = str(order.trigger_price)
            else:
                order_params["triggerprice"] = "0"
            
            # Add tag if provided
            if order.tag:
                order_params["ordertag"] = order.tag
            
            # Place order
            response = await asyncio.to_thread(
                self._client.placeOrder,
                order_params
            )
            
            if response.get("status"):
                order_id = response["data"]["orderid"]
                logger.info(f"Order placed: {order_id} - {order.symbol} {order.side.value}")
                
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    broker_order_id=order_id,
                    message="Order placed successfully",
                    status=OrderStatus.OPEN,
                    raw_response=response
                )
            else:
                error_msg = response.get("message", "Unknown error")
                logger.error(f"Order failed: {error_msg}")
                
                return OrderResult(
                    success=False,
                    message=error_msg,
                    status=OrderStatus.REJECTED,
                    raw_response=response
                )
                
        except Exception as e:
            logger.error(f"Place order error: {str(e)}")
            return OrderResult(
                success=False,
                message=str(e),
                status=OrderStatus.REJECTED
            )
    
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None
    ) -> OrderResult:
        """Modify an existing order."""
        if not await self.is_connected():
            return OrderResult(success=False, message="Not connected")
        
        try:
            # Get existing order details first
            order_book = await self.get_order_book()
            existing_order = None
            for order in order_book:
                if order.get("orderid") == order_id:
                    existing_order = order
                    break
            
            if not existing_order:
                return OrderResult(
                    success=False,
                    message="Order not found"
                )
            
            modify_params = {
                "variety": existing_order.get("variety", "NORMAL"),
                "orderid": order_id,
                "ordertype": existing_order.get("ordertype"),
                "producttype": existing_order.get("producttype"),
                "duration": "DAY",
                "quantity": str(quantity) if quantity else existing_order.get("quantity"),
                "price": str(price) if price else existing_order.get("price", "0"),
                "triggerprice": str(trigger_price) if trigger_price else existing_order.get("triggerprice", "0"),
                "exchange": existing_order.get("exchange"),
                "symboltoken": existing_order.get("symboltoken"),
                "tradingsymbol": existing_order.get("tradingsymbol")
            }
            
            response = await asyncio.to_thread(
                self._client.modifyOrder,
                modify_params
            )
            
            if response.get("status"):
                logger.info(f"Order modified: {order_id}")
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    message="Order modified successfully",
                    raw_response=response
                )
            else:
                return OrderResult(
                    success=False,
                    message=response.get("message", "Modification failed"),
                    raw_response=response
                )
                
        except Exception as e:
            logger.error(f"Modify order error: {str(e)}")
            return OrderResult(success=False, message=str(e))
    
    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel an existing order."""
        if not await self.is_connected():
            return OrderResult(success=False, message="Not connected")
        
        try:
            response = await asyncio.to_thread(
                self._client.cancelOrder,
                order_id,
                "NORMAL"
            )
            
            if response.get("status"):
                logger.info(f"Order cancelled: {order_id}")
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    message="Order cancelled",
                    status=OrderStatus.CANCELLED,
                    raw_response=response
                )
            else:
                return OrderResult(
                    success=False,
                    message=response.get("message", "Cancellation failed"),
                    raw_response=response
                )
                
        except Exception as e:
            logger.error(f"Cancel order error: {str(e)}")
            return OrderResult(success=False, message=str(e))
    
    async def get_order_status(self, order_id: str) -> OrderResult:
        """Get current status of an order."""
        try:
            order_book = await self.get_order_book()
            for order in order_book:
                if order.get("orderid") == order_id:
                    status_map = {
                        "complete": OrderStatus.FILLED,
                        "rejected": OrderStatus.REJECTED,
                        "cancelled": OrderStatus.CANCELLED,
                        "open": OrderStatus.OPEN,
                        "pending": OrderStatus.PENDING
                    }
                    
                    broker_status = order.get("status", "").lower()
                    status = status_map.get(broker_status, OrderStatus.PENDING)
                    
                    return OrderResult(
                        success=True,
                        order_id=order_id,
                        status=status,
                        filled_quantity=int(order.get("filledshares", 0)),
                        average_price=float(order.get("averageprice", 0)),
                        raw_response=order
                    )
            
            return OrderResult(
                success=False,
                message="Order not found"
            )
            
        except Exception as e:
            logger.error(f"Get order status error: {str(e)}")
            return OrderResult(success=False, message=str(e))
    
    async def get_order_book(self) -> List[Dict[str, Any]]:
        """Get all orders for the day."""
        if not await self.is_connected():
            return []
        
        try:
            response = await asyncio.to_thread(self._client.orderBook)
            if response.get("status") and response.get("data"):
                return response["data"]
            return []
        except Exception as e:
            logger.error(f"Get order book error: {str(e)}")
            return []
    
    # ============================================
    # Position & Holdings
    # ============================================
    
    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
        if not await self.is_connected():
            return []
        
        try:
            response = await asyncio.to_thread(self._client.position)
            if not response.get("status") or not response.get("data"):
                return []
            
            positions = []
            for pos in response["data"]:
                net_qty = int(pos.get("netqty", 0))
                if net_qty == 0:
                    continue
                
                avg_price = float(pos.get("averageprice", 0))
                ltp = float(pos.get("ltp", 0))
                pnl = (ltp - avg_price) * net_qty
                pnl_pct = ((ltp - avg_price) / avg_price * 100) if avg_price > 0 else 0
                
                positions.append(Position(
                    symbol=pos.get("tradingsymbol"),
                    exchange=pos.get("exchange"),
                    symbol_token=pos.get("symboltoken"),
                    quantity=abs(net_qty),
                    average_price=avg_price,
                    ltp=ltp,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    product_type=ProductType(pos.get("producttype", "INTRADAY")),
                    side=OrderSide.BUY if net_qty > 0 else OrderSide.SELL
                ))
            
            return positions
            
        except Exception as e:
            logger.error(f"Get positions error: {str(e)}")
            return []
    
    async def get_holdings(self) -> List[Holding]:
        """Get all holdings/portfolio."""
        if not await self.is_connected():
            return []
        
        try:
            response = await asyncio.to_thread(self._client.holding)
            if not response.get("status") or not response.get("data"):
                return []
            
            holdings = []
            for hold in response["data"]:
                qty = int(hold.get("quantity", 0))
                if qty == 0:
                    continue
                
                avg_price = float(hold.get("averageprice", 0))
                ltp = float(hold.get("ltp", 0))
                pnl = (ltp - avg_price) * qty
                pnl_pct = ((ltp - avg_price) / avg_price * 100) if avg_price > 0 else 0
                
                holdings.append(Holding(
                    symbol=hold.get("tradingsymbol"),
                    exchange=hold.get("exchange"),
                    quantity=qty,
                    average_price=avg_price,
                    ltp=ltp,
                    pnl=pnl,
                    pnl_pct=pnl_pct
                ))
            
            return holdings
            
        except Exception as e:
            logger.error(f"Get holdings error: {str(e)}")
            return []
    
    # ============================================
    # Market Data
    # ============================================
    
    async def get_ltp(self, symbol: str, exchange: str) -> float:
        """Get last traded price for a symbol."""
        quote = await self.get_quote(symbol, exchange)
        return quote.ltp if quote else 0.0
    
    async def get_quote(self, symbol: str, exchange: str) -> Optional[Quote]:
        """Get full market quote for a symbol."""
        if not await self.is_connected():
            return None
        
        try:
            symbol_token = await self.get_symbol_token(symbol, exchange)
            if not symbol_token:
                logger.warning(f"No token for {exchange}:{symbol}, cannot fetch quote")
                return None
            
            # Use resolved trading symbol name (e.g. RELIANCE-EQ)
            trading_symbol = self._symbol_name_cache.get(f"{exchange}:{symbol}", symbol)
            
            response = await asyncio.to_thread(
                self._client.ltpData,
                self.EXCHANGE_MAP.get(exchange, exchange),
                trading_symbol,
                symbol_token
            )
            
            if response.get("status") and response.get("data"):
                data = response["data"]
                return Quote(
                    symbol=symbol,
                    exchange=exchange,
                    ltp=float(data.get("ltp", 0)),
                    open=float(data.get("open", 0)),
                    high=float(data.get("high", 0)),
                    low=float(data.get("low", 0)),
                    close=float(data.get("close", 0)),
                    volume=int(data.get("volume", 0)),
                    bid=float(data.get("bidprice", 0)),
                    ask=float(data.get("askprice", 0)),
                    timestamp=datetime.now()
                )
            return None
            
        except Exception as e:
            logger.error(f"Get quote error for {exchange}:{symbol}: {str(e)}")
            return None
    
    async def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Candle]:
        """Get historical OHLCV data."""
        if not await self.is_connected():
            return []
        
        try:
            symbol_token = await self.get_symbol_token(symbol, exchange)
            angel_interval = self.INTERVAL_MAP.get(interval, "FIVE_MINUTE")
            
            params = {
                "exchange": self.EXCHANGE_MAP.get(exchange, exchange),
                "symboltoken": symbol_token,
                "interval": angel_interval,
                "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
                "todate": to_date.strftime("%Y-%m-%d %H:%M")
            }
            
            response = await asyncio.to_thread(
                self._client.getCandleData,
                params
            )
            
            if not response.get("status") or not response.get("data"):
                return []
            
            candles = []
            for candle_data in response["data"]:
                candles.append(Candle(
                    timestamp=datetime.strptime(candle_data[0], "%Y-%m-%dT%H:%M:%S%z"),
                    open=float(candle_data[1]),
                    high=float(candle_data[2]),
                    low=float(candle_data[3]),
                    close=float(candle_data[4]),
                    volume=int(candle_data[5])
                ))
            
            return candles
            
        except Exception as e:
            logger.error(f"Get historical data error: {str(e)}")
            return []
    
    # ============================================
    # Symbol Management
    # ============================================
    
    async def get_symbol_token(self, symbol: str, exchange: str) -> str:
        """Get broker-specific token for a symbol using local symbols.json."""
        cache_key = f"{exchange}:{symbol}"
        
        if cache_key in self._symbol_cache:
            return self._symbol_cache[cache_key]
        
        # ─── Method 0: Hardcoded NSE tokens (instant, always correct) ───
        if exchange == "NSE" and symbol in self.NSE_TOKEN_MAP:
            token, trading_sym = self.NSE_TOKEN_MAP[symbol]
            self._symbol_cache[cache_key] = token
            self._symbol_name_cache[cache_key] = trading_sym
            logger.info(f"Symbol resolved from hardcoded map: {cache_key} -> token={token}")
            return token
        
        # ─── Method 1: Local symbols.json lookup (fast & reliable) ───
        try:
            symbols_file = Path(__file__).parent.parent.parent / "data" / "symbols.json"
            if symbols_file.exists():
                import json
                symbols_data = json.loads(symbols_file.read_text(encoding="utf-8"))
                
                # Search by name (e.g., "RELIANCE") and exchange
                for entry in symbols_data:
                    entry_name = entry.get("name", "")
                    entry_sym = entry.get("symbol", "")
                    entry_exch = entry.get("exchange", "")
                    
                    if entry_name == symbol and entry_exch == exchange:
                        token = entry.get("token", "")
                        if token:
                            self._symbol_cache[cache_key] = token
                            self._symbol_name_cache[cache_key] = entry_sym  # e.g., "RELIANCE-EQ"
                            logger.info(f"Symbol resolved from local DB: {cache_key} -> token={token}, trading_symbol={entry_sym}")
                            return token
                    
                    # Also try matching by symbol directly (e.g., "RELIANCE-EQ")
                    if entry_sym == symbol and entry_exch == exchange:
                        token = entry.get("token", "")
                        if token:
                            self._symbol_cache[cache_key] = token
                            self._symbol_name_cache[cache_key] = entry_sym
                            logger.info(f"Symbol resolved from local DB (direct): {cache_key} -> token={token}")
                            return token
        except Exception as e:
            logger.warning(f"Local symbol lookup failed: {e}")
        
        # ─── Method 2: Fall back to API search ───
        name_variants = [symbol]
        if exchange in ("NSE", "BSE") and not symbol.endswith(("-EQ", "-BE", "-BL")):
            name_variants.append(f"{symbol}-EQ")
        
        for variant in name_variants:
            results = await self.search_symbols(variant, exchange)
            for result in results:
                result_sym = result.get("symbol", "") or result.get("name", "")
                result_exch = result.get("exch_seg", result.get("exchange", ""))
                if result_sym in (symbol, f"{symbol}-EQ") and result_exch == exchange:
                    token = result.get("token", result.get("symboltoken", ""))
                    if token:
                        self._symbol_cache[cache_key] = token
                        self._symbol_name_cache[cache_key] = result_sym
                        logger.info(f"Symbol resolved from API: {cache_key} -> {token} (matched {result_sym})")
                        return token
        
        logger.warning(f"Symbol token not found: {cache_key} (tried hardcoded + local DB + API)")
        return ""
    
    async def search_symbols(self, query: str, exchange: str = "NSE") -> List[Dict[str, Any]]:
        """Search for symbols by name or code."""
        if not await self.is_connected():
            return []
        
        try:
            exch = self.EXCHANGE_MAP.get(exchange, exchange)
            response = await asyncio.to_thread(
                self._client.searchScrip,
                exch,
                query
            )
            
            if response.get("status") and response.get("data"):
                return response["data"]
            return []
            
        except Exception as e:
            logger.error(f"Search symbols error: {str(e)}")
            return []
    
    # ============================================
    # Account Information
    # ============================================
    
    async def get_profile(self) -> Dict[str, Any]:
        """Get user profile information."""
        if not await self.is_connected():
            return {}
        
        try:
            response = await asyncio.to_thread(self._client.getProfile)
            if response.get("status") and response.get("data"):
                return response["data"]
            return {}
        except Exception as e:
            logger.error(f"Get profile error: {str(e)}")
            return {}
    
    async def get_funds(self) -> Dict[str, float]:
        """Get available funds/margins."""
        if not await self.is_connected():
            return {}
        
        try:
            response = await asyncio.to_thread(self._client.rmsLimit)
            if response.get("status") and response.get("data"):
                data = response["data"]
                return {
                    "available_cash": float(data.get("availablecash", 0)),
                    "available_margin": float(data.get("availableintradaypayin", 0)),
                    "used_margin": float(data.get("utiliseddebits", 0)),
                    "collateral": float(data.get("collateral", 0))
                }
            return {}
        except Exception as e:
            logger.error(f"Get funds error: {str(e)}")
            return {}
