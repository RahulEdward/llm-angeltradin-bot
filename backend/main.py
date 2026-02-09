"""
FastAPI Application - Main Entry Point
LLM-AngelAgent Trading Platform API
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

from src.config.settings import settings, TradingMode
from src.agents import SupervisorAgent
from src.broker import BrokerFactory
from src.agents.base import MessageType


# Global state
supervisor: Optional[SupervisorAgent] = None
active_connections: List[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global supervisor
    
    # Startup
    logger.info("Starting LLM-AngelAgent Trading Platform...")
    logger.info(f"Mode: {settings.trading_mode.value}")
    
    # Validate LLM connection
    llm_status = "OFF"
    try:
        from src.llm import LLMFactory
        if settings.openai_api_key or settings.anthropic_api_key or settings.groq_api_key:
            llm = LLMFactory.get_or_create()
            if llm:
                llm_status = f"ON ({settings.llm_provider.value}/{settings.llm_model})"
                logger.info(f"LLM connected: {settings.llm_provider.value} / {settings.llm_model}")
            else:
                logger.warning("LLM client creation failed")
        else:
            logger.info("No LLM API key configured - running in rule-based mode")
    except Exception as e:
        logger.warning(f"LLM initialization failed: {e}")
    
    logger.info(f"LLM Status: {llm_status}")
    
    # Auto-load saved API keys from DB into settings
    try:
        saved_keys = get_all_active_api_keys(user_id=1)
        for provider, key_data in saved_keys.items():
            api_key = key_data["api_key"]
            if provider == "openai" and api_key:
                settings.openai_api_key = api_key
                logger.info("Loaded OpenAI API key from DB")
            elif provider == "anthropic" and api_key:
                settings.anthropic_api_key = api_key
                logger.info("Loaded Anthropic API key from DB")
            elif provider == "groq" and api_key:
                settings.groq_api_key = api_key
                logger.info("Loaded Groq API key from DB")
            elif provider == "deepseek" and api_key:
                settings.openai_api_key = api_key  # DeepSeek uses OpenAI-compatible API
                logger.info("Loaded DeepSeek API key from DB")
            elif provider == "gemini" and api_key:
                # Store for future use
                logger.info("Loaded Gemini API key from DB")
            if key_data.get("model_name"):
                settings.llm_model = key_data["model_name"]
        
        # Re-check LLM after loading keys
        if saved_keys and llm_status == "OFF":
            try:
                from src.llm import LLMFactory
                llm = LLMFactory.get_or_create()
                if llm:
                    llm_status = f"ON ({settings.llm_provider.value}/{settings.llm_model})"
                    logger.info(f"LLM connected after loading DB keys: {llm_status}")
            except Exception as e:
                logger.warning(f"LLM re-init after key load failed: {e}")
    except Exception as e:
        logger.warning(f"Failed to load API keys from DB: {e}")
    
    supervisor = SupervisorAgent(config={
        "symbols": ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"],
        "use_llm": llm_status != "OFF",
        "cycle_interval": 60
    })
    
    await supervisor.initialize()
    logger.info("Platform ready - paper mode uses simulated data, connect broker for real data")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    if supervisor:
        await supervisor.shutdown()
    await BrokerFactory.shutdown()


app = FastAPI(
    title="LLM-AngelAgent Trading Platform",
    description="AI-powered autonomous trading platform for Indian markets",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# Pydantic Models
# ============================================

class TradingModeRequest(BaseModel):
    mode: str  # live, paper, backtest


class StrategyConfig(BaseModel):
    symbols: List[str]
    timeframes: List[str] = ["5m", "15m", "1h"]
    use_llm: bool = True
    min_confidence: float = 0.6
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 4.0


class BacktestRequest(BaseModel):
    symbol: str
    exchange: str = "NSE"
    start_date: str  # ISO format
    end_date: str
    initial_capital: float = 1000000
    timeframe: str = "5m"
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 4.0
    use_llm: bool = False


class OrderRequest(BaseModel):
    symbol: str
    exchange: str = "NSE"
    side: str  # BUY or SELL
    quantity: int
    order_type: str = "MARKET"
    price: Optional[float] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# ============================================
# Authentication Endpoints
# ============================================

# Import database module
from src.database import (
    authenticate_user, get_all_users, create_user, save_trade, 
    get_user_trades, save_agent_log, get_agent_logs,
    save_api_key, get_api_keys, get_api_key_decrypted, delete_api_key, get_all_active_api_keys
)


@app.post("/api/login")
async def login(request: LoginRequest):
    """Authenticate user and return token."""
    user = authenticate_user(request.username, request.password)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Auto-fetch symbols on every login (background, skips if <24h old)
    asyncio.create_task(fetch_symbols_public())
    
    # In production, generate a proper JWT token
    return {
        "success": True,
        "username": user["username"],
        "role": user["role"],
        "user_id": user["id"],
        "token": f"token_{user['username']}_{datetime.now().timestamp()}"
    }


@app.get("/api/users")
async def list_users():
    """Get all users (admin only)."""
    users = get_all_users()
    return {"users": users}


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    email: Optional[str] = None


@app.post("/api/users")
async def register_user(request: CreateUserRequest):
    """Create a new user."""
    user_id = create_user(request.username, request.password, request.role, request.email)
    
    if not user_id:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    return {"success": True, "user_id": user_id}


@app.get("/api/info")
async def get_info():
    """Get deployment info."""
    import os
    deployment_mode = os.getenv("DEPLOYMENT_MODE", "local")
    
    return {
        "name": "LLM-AngelAgent",
        "version": "1.0.0",
        "deployment_mode": deployment_mode,
        "trading_mode": settings.trading_mode.value
    }


# ============================================
# Health & Status Endpoints
# ============================================

@app.get("/")
async def root():
    return {
        "name": "LLM-AngelAgent Trading Platform",
        "version": "1.0.0",
        "mode": settings.trading_mode.value,
        "status": "running"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mode": settings.trading_mode.value
    }


@app.get("/api/status")
async def get_status():
    """Get system status."""
    if not supervisor:
        return {
            "is_running": False,
            "cycle_count": 0,
            "mode": settings.trading_mode.value,
            "broker_connected": len(connected_brokers) > 0
        }
    status = supervisor.get_system_status()
    status["mode"] = settings.trading_mode.value
    status["broker_connected"] = len(connected_brokers) > 0
    return status


@app.get("/api/debug/broker")
async def debug_broker():
    """Debug endpoint to check broker connection state."""
    broker_info = {}
    for acc_id, data in connected_brokers.items():
        broker_info[acc_id] = {
            "has_smart_api": data.get("smart_api") is not None,
            "is_demo": data.get("demo", False),
            "connected_at": data.get("connected_at")
        }
    
    smart_api = get_connected_smart_api()
    
    # Try a simple API call to verify session is alive
    session_alive = False
    rms_response = None
    if smart_api:
        try:
            response = await asyncio.to_thread(smart_api.rmsLimit)
            rms_response = str(response)[:500]
            session_alive = bool(response and response.get("data"))
        except Exception as e:
            rms_response = f"Error: {e}"
    
    return {
        "mode": settings.trading_mode.value,
        "connected_brokers_count": len(connected_brokers),
        "connected_brokers": broker_info,
        "smart_api_available": smart_api is not None,
        "session_alive": session_alive,
        "rms_response_preview": rms_response,
        "factory_connected_broker": BrokerFactory.get_connected_broker() is not None,
        "factory_instance": str(type(BrokerFactory.get_instance()).__name__) if BrokerFactory.get_instance() else None
    }


# ============================================
# Mode Management
# ============================================

@app.get("/api/mode")
async def get_mode():
    """Get current trading mode."""
    return {"mode": settings.trading_mode.value}


@app.post("/api/mode")
async def set_mode(request: TradingModeRequest):
    """Switch trading mode dynamically."""
    try:
        mode = TradingMode(request.mode.lower())
        old_mode = settings.trading_mode
        
        # Update the settings trading mode
        settings.trading_mode = mode
        
        if mode != old_mode:
            logger.info(f"Mode switching: {old_mode.value} → {mode.value}")
            logger.info(f"Connected brokers: {list(connected_brokers.keys())}")
            
            if mode == TradingMode.LIVE:
                # Live mode — check if broker is actually connected
                if len(connected_brokers) == 0:
                    logger.warning("Switched to LIVE but no broker connected!")
                    return {
                        "mode": mode.value, 
                        "message": "Switched to Live mode. Connect broker in Settings to see real data.",
                        "broker_connected": False
                    }
                else:
                    logger.info("Live mode: using existing connected broker session")
            else:
                # Paper/Backtest — recreate broker
                broker = BrokerFactory.create(mode)
                if broker:
                    try:
                        await broker.connect()
                    except Exception as e:
                        logger.warning(f"Broker connect on mode switch: {e}")
                    logger.info(f"Broker recreated for {mode.value} mode")
        
        logger.info(f"Trading mode switched to: {mode.value}")
        return {
            "mode": mode.value, 
            "message": f"Mode switched to {mode.value}",
            "broker_connected": len(connected_brokers) > 0
        }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")


# ============================================
# Trading Control
# ============================================

@app.post("/api/trading/start")
async def start_trading():
    """Start the multi-agent trading loop (reference-repo style)."""
    if not supervisor:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    # ─── Boot Messages (like reference-repo) ───
    await agent_ws_manager.send_agent_message("System", "**System initialized.** All agents are online and ready for parallel execution.")
    await agent_ws_manager.send_agent_message("Supervisor", f"🚀 Trading loop started | Mode: {settings.trading_mode.value}")
    await agent_ws_manager.send_agent_message("Supervisor", f"Symbols: RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK | Cycle: {supervisor._cycle_interval}s")
    
    # LLM status
    llm_status = "OFF"
    llm_info = "rule-based"
    try:
        from src.llm import LLMFactory
        llm = LLMFactory.get_instance()
        if not llm:
            llm = LLMFactory.get_or_create()
        if llm:
            llm_status = "ON"
            llm_info = f"{settings.llm_provider.value}/{settings.llm_model}"
    except:
        pass
    await agent_ws_manager.send_agent_message("Supervisor", f"LLM: {llm_status} ({llm_info})")
    
    # Data source
    broker_connected = len(connected_brokers) > 0
    if broker_connected:
        await agent_ws_manager.send_agent_message("Market Data Agent", "📊 Broker connected - using live market data")
    else:
        await agent_ws_manager.send_agent_message("Market Data Agent", "📊 No broker - using simulated market data (connect via Settings for real data)")
    
    # ─── Trading Loop ───
    async def trading_loop():
        while supervisor._is_running:
            try:
                cycle = supervisor._current_cycle + 1
                await agent_ws_manager.send_agent_message(
                    "Supervisor",
                    f"━━━ Cycle #{cycle} started ━━━ | {datetime.now().strftime('%H:%M:%S')}"
                )
                
                # Run the full multi-agent pipeline
                messages = await supervisor.process_cycle()
                
                # ─── Broadcast each message to chatroom (reference-repo style) ───
                for msg in messages:
                    agent_name = msg.source_agent
                    payload = msg.payload
                    
                    if msg.type == MessageType.MARKET_UPDATE:
                        quotes = payload.get("quotes", {})
                        source = payload.get("source", "unknown")
                        symbols = list(quotes.keys())
                        if symbols:
                            prices = []
                            for k in symbols[:5]:
                                q = quotes[k]
                                s = q.get("symbol", k.split(":")[-1])
                                p = q.get("ltp", 0)
                                prices.append(f"{s}=₹{p:,.2f}")
                            await agent_ws_manager.send_agent_message(
                                "Market Data Agent",
                                f"📊 Data ready ({source}): {' | '.join(prices)}"
                            )
                            await agent_ws_manager.send_symbol(symbols[0].split(":")[-1])
                    
                    elif msg.type == MessageType.SIGNAL:
                        action = payload.get("action", "HOLD")
                        symbol = payload.get("symbol", "")
                        confidence = payload.get("confidence", 0)
                        reasoning = payload.get("reasoning", "")[:120]
                        source = payload.get("source", "rule_based")
                        await agent_ws_manager.send_agent_message(
                            "Strategy Agent",
                            f"🧠 Signal: {action} {symbol} | Conf: {confidence:.0%} | Source: {source} | {reasoning}"
                        )
                    
                    elif msg.type == MessageType.DECISION:
                        action = payload.get("action", "HOLD")
                        symbol = payload.get("symbol", "")
                        risk = payload.get("risk_assessment", {})
                        await agent_ws_manager.send_agent_message(
                            "Risk Manager",
                            f"✅ PASSED: {action} {symbol} | Risk: {risk.get('risk_level', 'unknown')} | Position: {risk.get('position_size', 'N/A')}"
                        )
                    
                    elif msg.type == MessageType.VETO:
                        reason = payload.get("reason", "")
                        original = payload.get("original_signal", {})
                        symbol = original.get("symbol", "")
                        await agent_ws_manager.send_agent_message(
                            "Risk Manager",
                            f"🛡️ BLOCKED: {symbol} | {reason}"
                        )
                    
                    elif msg.type == MessageType.EXECUTION:
                        success = payload.get("success", False)
                        symbol = payload.get("symbol", "")
                        action = payload.get("action", "")
                        if success:
                            price = payload.get("fill_price", 0)
                            qty = payload.get("quantity", 0)
                            await agent_ws_manager.send_agent_message(
                                "Execution Agent",
                                f"⚡ Executed: {action} {symbol} x{qty} @ ₹{price:,.2f}"
                            )
                            try:
                                save_trade(user_id=1, trade_data={
                                    "symbol": symbol,
                                    "side": action,
                                    "quantity": qty,
                                    "entry_price": price,
                                    "status": "open",
                                    "entry_time": datetime.now().isoformat(),
                                    "strategy": "LLM-Agent"
                                })
                            except Exception as e:
                                logger.error(f"Failed to save trade: {e}")
                            await agent_ws_manager.send_trade({
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "symbol": symbol,
                                "side": action,
                                "entry": price,
                                "exit": None,
                                "pnl": 0
                            })
                        else:
                            error = payload.get("error", "Unknown error")
                            await agent_ws_manager.send_agent_message(
                                "Execution Agent",
                                f"❌ Failed: {action} {symbol} - {error}"
                            )
                    
                    elif msg.type == MessageType.ERROR:
                        error = payload.get("error", "Unknown error")
                        agent = payload.get("agent", agent_name)
                        await agent_ws_manager.send_agent_message(agent, f"❌ Error: {error}")
                    
                    elif msg.type == MessageType.STATE_UPDATE:
                        status_msg = payload.get("message", "")
                        if status_msg:
                            await agent_ws_manager.send_agent_message(agent_name, status_msg)
                
                # Cycle complete
                await agent_ws_manager.send_agent_message(
                    "Supervisor",
                    f"━━━ Cycle #{supervisor._current_cycle} complete ━━━ | {len(messages)} events"
                )
                
                try:
                    save_agent_log("Supervisor", f"Cycle #{supervisor._current_cycle} - {len(messages)} events", "info", supervisor._current_cycle)
                except:
                    pass
                
                await asyncio.sleep(supervisor._cycle_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                await agent_ws_manager.send_agent_message("Supervisor", f"❌ Loop error: {str(e)[:100]}")
                await asyncio.sleep(5)
        
        await agent_ws_manager.send_agent_message("Supervisor", "🛑 Trading loop stopped by user")
    
    supervisor._is_running = True
    asyncio.create_task(trading_loop())
    return {"status": "started", "mode": settings.trading_mode.value}


@app.post("/api/trading/stop")
async def stop_trading():
    """Stop the trading loop."""
    if not supervisor:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    supervisor._is_running = False
    await agent_ws_manager.send_agent_message("Supervisor", "🛑 Trading stopped by user")
    return {"status": "stopped"}


@app.post("/api/trading/cycle")
async def run_cycle():
    """Run a single trading cycle."""
    if not supervisor:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    messages = await supervisor.process_cycle()
    return {
        "messages": [m.to_dict() for m in messages],
        "count": len(messages)
    }


# ============================================
# Market Data
# ============================================

@app.get("/api/market/quotes")
async def get_quotes():
    """Get current market quotes."""
    if not supervisor:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    market_agent = supervisor.get_agent("market_data")
    if market_agent:
        return market_agent.get_market_snapshot()
    return {"quotes": {}, "indicators": {}}


@app.get("/api/market/quote/{symbol}")
async def get_quote(symbol: str, exchange: str = "NSE"):
    """Get quote for a specific symbol from connected broker."""
    smart_api = get_connected_smart_api()
    
    if smart_api:
        try:
            # Use Angel One's LTP API
            response = await asyncio.to_thread(
                smart_api.ltpData,
                exchange,
                symbol,
                ""  # symboltoken - empty to lookup by symbol
            )
            if response.get("status") and response.get("data"):
                data = response["data"]
                return {
                    "symbol": data.get("tradingsymbol", symbol),
                    "ltp": float(data.get("ltp", 0)),
                    "open": float(data.get("open", 0)),
                    "high": float(data.get("high", 0)),
                    "low": float(data.get("low", 0)),
                    "close": float(data.get("close", 0)),
                    "exchange": data.get("exchange", exchange)
                }
        except Exception as e:
            logger.error(f"Quote fetch error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=503, detail="Broker not connected. Please connect in Settings.")



# ============================================
# Positions & Orders
# ============================================

def get_connected_smart_api():
    """Get connected SmartAPI client from broker sessions."""
    for account_id, broker_data in connected_brokers.items():
        if broker_data.get("smart_api"):
            return broker_data["smart_api"]
    return None


@app.get("/api/positions")
async def get_positions():
    """Get current positions from connected broker or paper broker."""
    # Paper mode: return paper broker positions
    if settings.trading_mode == TradingMode.PAPER:
        broker = BrokerFactory.get_instance()
        if broker and hasattr(broker, 'get_positions'):
            try:
                positions = await broker.get_positions()
                return [
                    {
                        "symbol": p.symbol,
                        "exchange": p.exchange,
                        "quantity": p.quantity,
                        "average_price": p.average_price,
                        "ltp": p.ltp,
                        "pnl": p.pnl,
                        "pnl_pct": p.pnl_pct,
                        "side": p.side.value if hasattr(p.side, 'value') else str(p.side)
                    }
                    for p in positions
                ]
            except Exception as e:
                logger.error(f"Paper positions fetch error: {e}")
        return []

    # Live mode: get from connected broker
    smart_api = get_connected_smart_api()
    
    if smart_api:
        try:
            response = await asyncio.to_thread(smart_api.position)
            logger.info(f"Positions API response status: {response.get('status') if response else 'None'}")
            if response and response.get("data"):
                data = response["data"]
                # Handle case where data might be None or "No Data"
                if not data or data == "No Data":
                    return []
                positions = []
                for pos in data:
                    net_qty = int(pos.get("netqty", 0))
                    if net_qty == 0:
                        continue
                    avg_price = float(pos.get("averageprice", 0) or 0)
                    ltp = float(pos.get("ltp", 0) or 0)
                    pnl = (ltp - avg_price) * net_qty
                    pnl_pct = ((ltp - avg_price) / avg_price * 100) if avg_price > 0 else 0
                    positions.append({
                        "symbol": pos.get("tradingsymbol"),
                        "exchange": pos.get("exchange"),
                        "quantity": abs(net_qty),
                        "average_price": avg_price,
                        "ltp": ltp,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "side": "BUY" if net_qty > 0 else "SELL"
                    })
                return positions
            return []
        except Exception as e:
            logger.error(f"Positions fetch error: {e}")
            return []
    else:
        logger.warning("No connected smart_api for live positions")
    
    return []


@app.get("/api/orders")
async def get_orders():
    """Get order book from connected broker or paper broker."""
    # Paper mode: return paper broker orders
    if settings.trading_mode == TradingMode.PAPER:
        broker = BrokerFactory.get_instance()
        if broker and hasattr(broker, 'get_order_book'):
            try:
                return await broker.get_order_book()
            except Exception as e:
                logger.error(f"Paper orders fetch error: {e}")
        return []

    # Live mode
    smart_api = get_connected_smart_api()
    
    if smart_api:
        try:
            response = await asyncio.to_thread(smart_api.orderBook)
            if response and response.get("data") and response["data"] != "No Data":
                return response["data"]
            return []
        except Exception as e:
            logger.error(f"Orders fetch error: {e}")
            return []
    
    return []



@app.post("/api/orders")
async def place_order(order: OrderRequest):
    """Place a manual order."""
    if settings.trading_mode == TradingMode.BACKTEST:
        raise HTTPException(status_code=400, detail="Cannot place orders in backtest mode")
    
    exec_agent = supervisor.get_agent("execution") if supervisor else None
    if not exec_agent:
        raise HTTPException(status_code=503, detail="Execution agent not available")
    
    # Create decision payload
    decision = {
        "action": order.side.upper(),
        "symbol": order.symbol,
        "exchange": order.exchange,
        "quantity": order.quantity,
        "confidence": 1.0,
        "reasoning": "Manual order"
    }
    
    from src.agents.base import AgentMessage, MessageType
    msg = AgentMessage(
        type=MessageType.DECISION,
        source_agent="manual",
        payload=decision
    )
    
    result = await exec_agent.handle_message(msg)
    return result.payload if result else {"error": "Order failed"}


# ============================================
# Backtesting
# ============================================

@app.post("/api/backtest")
async def run_backtest(request: BacktestRequest):
    """Run a backtest."""
    if not supervisor:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        result = await supervisor.run_backtest(
            symbol=request.symbol,
            exchange=request.exchange,
            start_date=datetime.fromisoformat(request.start_date),
            end_date=datetime.fromisoformat(request.end_date),
            initial_capital=request.initial_capital,
            timeframe=request.timeframe,
            stop_loss_pct=request.stop_loss_pct,
            take_profit_pct=request.take_profit_pct,
            use_llm=request.use_llm
        )
        
        return {
            "run_id": result.run_id,
            "symbol": result.symbol,
            "total_return_pct": result.total_return_pct,
            "win_rate": result.win_rate,
            "total_trades": result.total_trades,
            "max_drawdown_pct": result.max_drawdown_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "profit_factor": result.profit_factor,
            "equity_curve": result.equity_curve[:100],  # Limit for response size
            "trades": len(result.trades)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backtest/{run_id}")
async def get_backtest_result(run_id: str):
    """Get backtest result by ID."""
    backtest_agent = supervisor.get_agent("backtest") if supervisor else None
    if not backtest_agent:
        raise HTTPException(status_code=503, detail="Backtest agent not available")
    
    result = backtest_agent.get_result(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    return {
        "run_id": result.run_id,
        "symbol": result.symbol,
        "initial_capital": result.initial_capital,
        "final_capital": result.final_capital,
        "total_return_pct": result.total_return_pct,
        "total_trades": result.total_trades,
        "winning_trades": result.winning_trades,
        "losing_trades": result.losing_trades,
        "win_rate": result.win_rate,
        "max_drawdown_pct": result.max_drawdown_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "sortino_ratio": result.sortino_ratio,
        "profit_factor": result.profit_factor
    }


# ============================================
# Risk Management
# ============================================

@app.get("/api/risk")
async def get_risk_status():
    """Get risk management status."""
    risk_agent = supervisor.get_agent("risk_manager") if supervisor else None
    if not risk_agent:
        return {
            "daily_pnl": 0,
            "daily_trades": 0,
            "max_daily_loss": settings.max_daily_loss,
            "max_trades": settings.max_trades_per_day,
            "open_positions": 0,
            "kill_switch": False,
            "drawdown_pct": 0
        }
    
    return risk_agent.get_risk_status()


@app.post("/api/risk/kill-switch")
async def toggle_kill_switch(activate: bool = True):
    """Toggle kill switch."""
    risk_agent = supervisor.get_agent("risk_manager") if supervisor else None
    if not risk_agent:
        raise HTTPException(status_code=503, detail="Risk agent not available")
    
    if activate:
        risk_agent._activate_kill_switch("Manual activation")
    else:
        risk_agent.deactivate_kill_switch()
    
    return {"kill_switch": activate}


# ============================================
# WebSocket for Real-time Updates
# ============================================

# ============================================
# WebSocket for Real-time Updates
# ============================================
# Note: Main /ws endpoint is defined later with AgentConnectionManager

async def broadcast_message(message: dict):
    """Broadcast message to all connected clients."""
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            pass


# ============================================
# Agent Logs
# ============================================

@app.get("/api/logs/agents")
async def get_agent_logs():
    """Get recent agent decision logs."""
    if not supervisor:
        return {"logs": []}
    
    logs = []
    for name, agent in supervisor._agents.items():
        status = agent.get_status()
        logs.append({
            "agent": name,
            "type": status.get("type"),
            "is_active": status.get("is_active"),
            "messages_processed": status.get("messages_processed"),
            "error_count": status.get("error_count"),
            "last_update": status.get("last_update")
        })
    
    return {"logs": logs}


# ============================================
# DB-backed Trade History
# ============================================

@app.get("/api/trades/history")
async def get_trade_history(limit: int = 100):
    """Get trade history from database."""
    trades = get_user_trades(limit=limit)
    return {"trades": trades}


@app.post("/api/trades/save")
async def save_trade_record(trade_data: dict):
    """Save a trade record to database."""
    trade_id = save_trade(user_id=1, trade_data=trade_data)
    return {"success": True, "trade_id": trade_id}


@app.get("/api/logs/history")
async def get_log_history(limit: int = 50):
    """Get agent logs from database."""
    logs = get_agent_logs(limit=limit)
    return {"logs": logs}


# ============================================
# Account
# ============================================

@app.get("/api/account/profile")
async def get_profile():
    """Get account profile from connected broker or paper simulation."""
    # Handle Paper Mode
    if settings.trading_mode == TradingMode.PAPER:
        return {
            "name": "Paper Trading User",
            "client_id": "PAPER-SIM",
            "email": "[email]",
            "mobile": "[phone_number]",
            "exchanges": ["NSE", "BSE", "NFO"],
            "mode": "paper"
        }

    # Handle Live Mode
    if settings.trading_mode == TradingMode.LIVE:
        smart_api = get_connected_smart_api()
        
        if smart_api:
            try:
                try:
                    refresh_token = None
                    for acc_id, data in connected_brokers.items():
                        if data.get("smart_api") == smart_api:
                            refresh_token = data.get("session", {}).get("data", {}).get("refreshToken")
                            break
                    
                    if refresh_token:
                        response = await asyncio.to_thread(smart_api.getProfile, refresh_token)
                    else:
                        response = await asyncio.to_thread(smart_api.getProfile)
                except TypeError:
                     response = await asyncio.to_thread(smart_api.getProfile)
                
                logger.info(f"Profile response: {response}")
                
                if response and response.get("status") and response.get("data"):
                    profile = response["data"]
                    profile["mode"] = "live"
                    return profile
                else:
                    logger.warning(f"Profile fetch failed: {response}")
                    for acc_id, data in connected_brokers.items():
                        if data.get("smart_api") == smart_api:
                            client_id = data.get("session", {}).get("data", {}).get("clientcode", acc_id)
                            return {
                                "name": f"User ({client_id})",
                                "client_id": client_id,
                                "email": "Fetched from Broker",
                                "mobile": "",
                                "exchanges": ["NSE", "BSE", "NFO"],
                                "mode": "live"
                            }

            except Exception as e:
                logger.error(f"Profile fetch error: {e}")
                for acc_id, data in connected_brokers.items():
                    if data.get("smart_api") == smart_api:
                        return {
                            "name": f"Connected ({acc_id})", 
                            "client_id": acc_id, 
                            "message": "Profile fetch failed, but connected",
                            "mode": "live"
                        }
        
        # No connected broker in live mode
        return {
            "name": "Not Connected", 
            "client_id": "--", 
            "message": "Connect broker in Settings",
            "mode": "live"
        }

    # Backtest mode
    return {"name": "Backtest User", "client_id": "BACKTEST", "mode": "backtest"}


@app.get("/api/account/funds")
async def get_funds():
    """Get account funds."""
    # Handle Paper Mode
    if settings.trading_mode == TradingMode.PAPER:
        broker = BrokerFactory.get_instance()
        if broker and hasattr(broker, "get_funds"):
            try:
                funds = await broker.get_funds()
                return {
                    "available": funds.get("available_cash", 1000000),
                    "utilized": funds.get("used_margin", 0),
                    "margin": funds.get("available_margin", 1000000),
                    "collateral": funds.get("collateral", 0),
                    "mode": "paper"
                }
            except Exception as e:
                logger.error(f"Paper funds fetch error: {e}")
        # Fallback paper funds when no broker instance
        return {
            "available": 1000000, 
            "utilized": 0, 
            "margin": 1000000, 
            "collateral": 0,
            "mode": "paper",
            "message": "Paper Trading Mode"
        }

    # Handle Live Mode
    if settings.trading_mode == TradingMode.LIVE:
        smart_api = get_connected_smart_api()
        if smart_api:
            try:
                response = await asyncio.to_thread(smart_api.rmsLimit)
                logger.info(f"Funds API response: {response}")
                if response and response.get("data"):
                    data = response["data"]
                    # Angel One rmsLimit returns data as a dict or list
                    # Handle both formats
                    if isinstance(data, list) and len(data) > 0:
                        data = data[0]
                    
                    available = float(data.get("availablecash", 0) or data.get("net", 0) or 0)
                    utilized = float(data.get("utiliseddebits", 0) or data.get("utilizedamount", 0) or 0)
                    margin = float(data.get("availableintradaypayin", 0) or data.get("availablelimitmargin", 0) or available)
                    collateral = float(data.get("collateral", 0) or 0)
                    
                    return {
                        "available": available,
                        "utilized": utilized,
                        "margin": margin,
                        "collateral": collateral,
                        "mode": "live"
                    }
                else:
                    logger.warning(f"Funds API returned no data: {response}")
            except Exception as e:
                logger.error(f"Funds fetch error: {e}")
        else:
            logger.warning("No connected smart_api found for live funds")
        # No connected broker in live mode
        return {
            "available": 0, 
            "utilized": 0, 
            "margin": 0, 
            "collateral": 0, 
            "mode": "live",
            "message": "Connect broker in Settings to see live funds"
        }

    # Backtest mode
    return {"available": 0, "utilized": 0, "margin": 0, "collateral": 0, "mode": "backtest"}


@app.get("/api/account/holdings")
async def get_holdings():
    """Get account holdings (delivery positions)."""
    # Paper mode: return paper broker holdings
    if settings.trading_mode == TradingMode.PAPER:
        broker = BrokerFactory.get_instance()
        if broker and hasattr(broker, 'get_holdings'):
            try:
                holdings = await broker.get_holdings()
                return [
                    {
                        "symbol": h.symbol if hasattr(h, 'symbol') else h.get("symbol", ""),
                        "exchange": h.exchange if hasattr(h, 'exchange') else h.get("exchange", ""),
                        "quantity": h.quantity if hasattr(h, 'quantity') else h.get("quantity", 0),
                        "average_price": h.average_price if hasattr(h, 'average_price') else h.get("average_price", 0),
                        "ltp": h.ltp if hasattr(h, 'ltp') else h.get("ltp", 0),
                        "pnl": h.pnl if hasattr(h, 'pnl') else h.get("pnl", 0),
                        "pnl_pct": h.pnl_pct if hasattr(h, 'pnl_pct') else h.get("pnl_pct", 0)
                    }
                    for h in holdings
                ]
            except Exception as e:
                logger.error(f"Paper holdings fetch error: {e}")
        return []

    # Live mode
    if settings.trading_mode == TradingMode.LIVE:
        smart_api = get_connected_smart_api()
        if smart_api:
            try:
                response = await asyncio.to_thread(smart_api.holding)
                logger.info(f"Holdings API response status: {response.get('status') if response else 'None'}")
                if response and response.get("data") and response["data"] != "No Data":
                    holdings = []
                    for hold in response["data"]:
                        qty = int(hold.get("quantity", 0) or 0)
                        if qty == 0:
                            continue
                        avg_price = float(hold.get("averageprice", 0) or 0)
                        ltp = float(hold.get("ltp", 0) or 0)
                        pnl = (ltp - avg_price) * qty
                        pnl_pct = ((ltp - avg_price) / avg_price * 100) if avg_price > 0 else 0
                        holdings.append({
                            "symbol": hold.get("tradingsymbol"),
                            "exchange": hold.get("exchange"),
                            "quantity": qty,
                            "average_price": avg_price,
                            "ltp": ltp,
                            "pnl": pnl,
                            "pnl_pct": pnl_pct
                        })
                    return holdings
            except Exception as e:
                logger.error(f"Live holdings fetch error: {e}")
        return []
    
    return []


@app.get("/api/trades")
async def get_trades():
    """Get trade book."""
    # Paper mode: return paper broker trade history
    if settings.trading_mode == TradingMode.PAPER:
        broker = BrokerFactory.get_instance()
        if broker and hasattr(broker, '_trade_history'):
            return broker._trade_history
        return []

    # Live mode
    if settings.trading_mode == TradingMode.LIVE:
        smart_api = get_connected_smart_api()
        if smart_api:
            try:
                response = await asyncio.to_thread(smart_api.tradeBook)
                if response and response.get("data") and response["data"] != "No Data":
                    return response["data"]
            except Exception as e:
                logger.error(f"Live trades fetch error: {e}")
        return []
    
    # Backtest mode
    return []


# ============================================
# Broker Account Management
# ============================================

import json
import base64
from pathlib import Path
from cryptography.fernet import Fernet
import hashlib

# Generate or load encryption key
BROKER_DATA_FILE = Path(__file__).parent / "data" / "broker_accounts.json"
ENCRYPTION_KEY_FILE = Path(__file__).parent / "data" / ".encryption_key"

def get_encryption_key():
    """Get or create encryption key."""
    ENCRYPTION_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if ENCRYPTION_KEY_FILE.exists():
        return ENCRYPTION_KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    ENCRYPTION_KEY_FILE.write_bytes(key)
    return key

def encrypt_value(value: str) -> str:
    """Encrypt a string value."""
    f = Fernet(get_encryption_key())
    return f.encrypt(value.encode()).decode()

def decrypt_value(encrypted: str) -> str:
    """Decrypt an encrypted value."""
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted.encode()).decode()

def load_broker_accounts():
    """Load broker accounts from file."""
    if not BROKER_DATA_FILE.exists():
        return []
    try:
        return json.loads(BROKER_DATA_FILE.read_text())
    except:
        return []

def save_broker_accounts(accounts: list):
    """Save broker accounts to file."""
    BROKER_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    BROKER_DATA_FILE.write_text(json.dumps(accounts, indent=2))

# In-memory connected sessions
connected_brokers: Dict[str, Any] = {}


class BrokerAccountRequest(BaseModel):
    broker: str
    client_id: str
    api_key: str
    pin: str


class BrokerConnectRequest(BaseModel):
    account_id: str
    totp: str


@app.get("/api/broker/accounts")
async def get_broker_accounts():
    """Get all saved broker accounts."""
    accounts = load_broker_accounts()
    
    # Return with masked credentials
    safe_accounts = []
    for acc in accounts:
        safe_acc = {
            "id": acc["id"],
            "broker": acc["broker"],
            "client_id": acc["client_id"],
            "status": "connected" if acc["id"] in connected_brokers else "disconnected",
            "masked_credentials": {
                "client_id": acc["client_id"],
                "api_key": "••••" + acc.get("api_key_last4", ""),
                "pin": "••••"
            },
            "created_at": acc.get("created_at")
        }
        safe_accounts.append(safe_acc)
    
    return {"accounts": safe_accounts}


@app.post("/api/broker/accounts")
async def save_broker_account(request: BrokerAccountRequest):
    """Save broker account with encrypted credentials."""
    accounts = load_broker_accounts()
    
    # Check if account already exists
    for acc in accounts:
        if acc["client_id"] == request.client_id and acc["broker"] == request.broker:
            raise HTTPException(status_code=400, detail="Account already exists")
    
    # Create new account with encrypted credentials
    account_id = f"{request.broker}_{request.client_id}_{int(datetime.now().timestamp())}"
    
    new_account = {
        "id": account_id,
        "broker": request.broker,
        "client_id": request.client_id,
        "api_key_encrypted": encrypt_value(request.api_key),
        "api_key_last4": request.api_key[-4:] if len(request.api_key) >= 4 else "",
        "pin_encrypted": encrypt_value(request.pin),
        "created_at": datetime.now().isoformat()
    }
    
    accounts.append(new_account)
    save_broker_accounts(accounts)
    
    logger.info(f"Saved broker account: {request.broker} - {request.client_id}")
    
    return {
        "success": True,
        "account": {
            "id": account_id,
            "broker": request.broker,
            "client_id": request.client_id,
            "status": "disconnected",
            "masked_credentials": {
                "client_id": request.client_id,
                "api_key": "••••" + new_account["api_key_last4"],
                "pin": "••••"
            }
        }
    }


@app.delete("/api/broker/accounts/{account_id}")
async def delete_broker_account(account_id: str):
    """Delete a broker account."""
    accounts = load_broker_accounts()
    accounts = [a for a in accounts if a["id"] != account_id]
    save_broker_accounts(accounts)
    
    # Disconnect if connected
    if account_id in connected_brokers:
        del connected_brokers[account_id]
    
    return {"success": True}


@app.post("/api/broker/connect")
async def connect_broker(request: BrokerConnectRequest):
    """Connect to broker using TOTP."""
    accounts = load_broker_accounts()
    
    # Find account
    account = None
    for acc in accounts:
        if acc["id"] == request.account_id:
            account = acc
            break
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Decrypt credentials
    try:
        api_key = decrypt_value(account["api_key_encrypted"])
        pin = decrypt_value(account["pin_encrypted"])
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to decrypt credentials")
    
    # Connect to Angel One
    if account["broker"] == "angelone":
        try:
            from SmartApi import SmartConnect
            
            smart_api = SmartConnect(api_key=api_key)
            
            # Generate session with TOTP
            session = smart_api.generateSession(
                clientCode=account["client_id"],
                password=pin,
                totp=request.totp
            )
            
            if session.get("status") == False:
                raise HTTPException(
                    status_code=401, 
                    detail=session.get("message", "Login failed")
                )
            
            # Store connected session
            connected_brokers[request.account_id] = {
                "smart_api": smart_api,
                "session": session,
                "connected_at": datetime.now().isoformat()
            }
            
            # Also create AngelOneBroker and register with factory for data access
            try:
                from src.broker import AngelOneBroker
                angel_broker = AngelOneBroker(
                    api_key=api_key,
                    client_id=account["client_id"],
                    password=pin,
                    totp_secret=""  # Not needed since we're already connected
                )
                # Inject the already-connected SmartConnect client
                angel_broker._client = smart_api
                angel_broker._auth_token = session.get("data", {}).get("jwtToken")
                angel_broker._refresh_token = session.get("data", {}).get("refreshToken")
                angel_broker._feed_token = session.get("data", {}).get("feedToken")
                angel_broker._connected = True
                
                # Register with factory
                BrokerFactory.set_connected_broker(angel_broker)
                
                # Re-create broker instance (Paper or Live) with the new connection
                BrokerFactory.create()
                
                logger.info(f"Broker registered with factory: {account['client_id']}")
            except Exception as e:
                logger.error(f"Failed to register broker with factory: {e}")
            
            logger.info(f"Broker connected: {account['client_id']}")
            
            # Start symbol fetching in background
            asyncio.create_task(fetch_symbols_background(request.account_id))
            
            return {
                "success": True,
                "message": "Connected successfully",
                "session": {
                    "feed_token": session.get("data", {}).get("feedToken"),
                    "refresh_token": session.get("data", {}).get("refreshToken")
                }
            }
            
        except ImportError:
            # SmartApi not installed - demo mode
            logger.warning("SmartApi not installed, using demo mode")
            connected_brokers[request.account_id] = {
                "demo": True,
                "connected_at": datetime.now().isoformat()
            }
            return {
                "success": True,
                "message": "Connected (Demo Mode)",
                "session": {"demo": True}
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise HTTPException(status_code=401, detail=str(e))
    
    raise HTTPException(status_code=400, detail="Unsupported broker")


@app.post("/api/broker/disconnect/{account_id}")
async def disconnect_broker(account_id: str):
    """Disconnect broker session."""
    if account_id in connected_brokers:
        broker_data = connected_brokers[account_id]
        
        if not broker_data.get("demo") and "smart_api" in broker_data:
            try:
                broker_data["smart_api"].terminateSession(
                    broker_data["session"]["data"]["clientId"]
                )
            except:
                pass
        
        del connected_brokers[account_id]
        logger.info(f"Broker disconnected: {account_id}")
    
    return {"success": True}


async def fetch_symbols_public(force: bool = False):
    """Fetch NSE equity symbols from Angel One's public ScripMaster URL.
    No broker auth needed — this is a public endpoint.
    Skips if symbols.json exists and is less than 24h old (unless force=True).
    """
    import os, time
    symbols_file = Path(__file__).parent / "data" / "symbols.json"

    # Skip if fresh file exists (< 24h old) and not forced
    if not force and symbols_file.exists():
        file_age = time.time() - os.path.getmtime(str(symbols_file))
        if file_age < 86400:  # 24 hours
            logger.info(f"symbols.json is fresh ({file_age/3600:.1f}h old), skipping fetch")
            return

    try:
        import requests
        instruments_url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        logger.info("Fetching symbols from Angel One ScripMaster (public URL)...")
        response = await asyncio.to_thread(requests.get, instruments_url, timeout=60)

        if response.ok:
            instruments = response.json()

            # Filter NSE equity symbols
            nse_symbols = [
                {
                    "token": inst["token"],
                    "symbol": inst["symbol"],
                    "name": inst["name"],
                    "exchange": inst["exch_seg"]
                }
                for inst in instruments
                if inst.get("exch_seg") == "NSE" and inst.get("instrumenttype") == "EQ"
            ][:500]  # Limit to 500 for performance

            symbols_file.parent.mkdir(parents=True, exist_ok=True)
            symbols_file.write_text(json.dumps(nse_symbols, indent=2))
            logger.info(f"Fetched and saved {len(nse_symbols)} NSE symbols")
        else:
            logger.warning(f"Symbol fetch HTTP error: {response.status_code}")
    except Exception as e:
        logger.error(f"Symbol fetch failed: {e}")


async def fetch_symbols_background(account_id: str):
    """Fetch symbols in background after broker connection (legacy wrapper)."""
    try:
        if account_id not in connected_brokers:
            return
        broker_data = connected_brokers[account_id]
        if broker_data.get("demo"):
            logger.info("Using demo symbol data")
            return
        # Reuse the public fetcher (force refresh on broker connect)
        await fetch_symbols_public(force=True)
    except Exception as e:
        logger.error(f"Symbol fetch failed: {e}")


@app.get("/api/broker/symbols")
async def get_symbols():
    """Get available symbols."""
    symbols_file = Path(__file__).parent / "data" / "symbols.json"
    
    if symbols_file.exists():
        try:
            return {"symbols": json.loads(symbols_file.read_text())}
        except:
            pass
    
    # Return default symbols
    return {
        "symbols": [
            {"token": "2885", "symbol": "RELIANCE", "name": "RELIANCE INDUSTRIES", "exchange": "NSE"},
            {"token": "1594", "symbol": "INFY", "name": "INFOSYS LTD", "exchange": "NSE"},
            {"token": "11536", "symbol": "TCS", "name": "TATA CONSULTANCY SERVICES", "exchange": "NSE"},
            {"token": "1333", "symbol": "HDFCBANK", "name": "HDFC BANK LTD", "exchange": "NSE"},
            {"token": "4963", "symbol": "ICICIBANK", "name": "ICICI BANK LTD", "exchange": "NSE"},
            {"token": "3045", "symbol": "SBIN", "name": "STATE BANK OF INDIA", "exchange": "NSE"},
            {"token": "881", "symbol": "KOTAKBANK", "name": "KOTAK MAHINDRA BANK", "exchange": "NSE"},
            {"token": "3456", "symbol": "TATAMOTORS", "name": "TATA MOTORS LTD", "exchange": "NSE"},
            {"token": "2475", "symbol": "ONGC", "name": "OIL AND NATURAL GAS CORP", "exchange": "NSE"},
            {"token": "467", "symbol": "HINDUNILVR", "name": "HINDUSTAN UNILEVER", "exchange": "NSE"}
        ]
    }


@app.post("/api/symbols/refresh")
async def refresh_symbols():
    """Manually trigger a symbol list refresh (force re-fetch regardless of cache age)."""
    asyncio.create_task(fetch_symbols_public(force=True))
    return {"success": True, "message": "Symbol refresh started in background"}


@app.get("/api/broker/status/{account_id}")
async def get_broker_status(account_id: str):
    """Get broker connection status."""
    is_connected = account_id in connected_brokers
    
    if is_connected:
        broker_data = connected_brokers[account_id]
        return {
            "connected": True,
            "connected_at": broker_data.get("connected_at"),
            "demo_mode": broker_data.get("demo", False)
        }
    
    return {"connected": False}


# ============================================
# WebSocket for Real-time Market Data
# ============================================

class ConnectionManager:
    """Manages WebSocket connections for market data streaming."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, set] = {}  # WebSocket -> set of subscribed symbols
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = set()
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")
        
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
        logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")
        
    def subscribe(self, websocket: WebSocket, symbol: str):
        """Subscribe a client to a symbol."""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].add(symbol)
            
    def unsubscribe(self, websocket: WebSocket, symbol: str):
        """Unsubscribe a client from a symbol."""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].discard(symbol)
            
    async def broadcast_to_subscribers(self, symbol: str, data: dict):
        """Broadcast data to all clients subscribed to a symbol."""
        for ws, symbols in self.subscriptions.items():
            if symbol in symbols:
                try:
                    await ws.send_json(data)
                except Exception as e:
                    logger.error(f"Error broadcasting to client: {e}")


ws_manager = ConnectionManager()


@app.websocket("/ws/market")
async def websocket_market_data(websocket: WebSocket):
    """
    WebSocket endpoint for real-time market data.
    
    Client messages:
    - {"action": "subscribe", "symbols": ["RELIANCE", "TCS"], "exchange": "NSE"}
    - {"action": "unsubscribe", "symbols": ["RELIANCE"]}
    
    Server messages:
    - {"type": "tick", "symbol": "RELIANCE", "ltp": 2450.50, "change": 1.2, ...}
    - {"type": "subscribed", "symbol": "RELIANCE"}
    - {"type": "error", "message": "..."}
    """
    await ws_manager.connect(websocket)
    
    try:
        while True:
            try:
                data = await websocket.receive_json()
                action = data.get("action")
                
                if action == "subscribe":
                    symbols = data.get("symbols", [])
                    exchange = data.get("exchange", "NSE")
                    
                    for symbol in symbols:
                        ws_manager.subscribe(websocket, f"{exchange}:{symbol}")
                        await websocket.send_json({
                            "type": "subscribed",
                            "symbol": symbol,
                            "exchange": exchange
                        })
                        logger.debug(f"Client subscribed to {exchange}:{symbol}")
                        
                elif action == "unsubscribe":
                    symbols = data.get("symbols", [])
                    exchange = data.get("exchange", "NSE")
                    
                    for symbol in symbols:
                        ws_manager.unsubscribe(websocket, f"{exchange}:{symbol}")
                        await websocket.send_json({
                            "type": "unsubscribed", 
                            "symbol": symbol,
                            "exchange": exchange
                        })
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await websocket.send_json({"type": "error", "message": str(e)})
                
    finally:
        ws_manager.disconnect(websocket)


@app.get("/api/market/ltp/{symbol}")
async def get_ltp(symbol: str, exchange: str = "NSE"):
    """
    Get Last Traded Price for a symbol.
    Uses the connected broker's LTP API.
    """
    smart_api = get_connected_smart_api()
    
    if not smart_api:
        raise HTTPException(status_code=503, detail="Broker not connected")
    
    try:
        # Angel One LTP API requires symbol token
        # For now, use a simple mapping for common symbols
        token_map = {
            "RELIANCE": "2885",
            "INFY": "1594", 
            "TCS": "11536",
            "HDFCBANK": "1333",
            "ICICIBANK": "4963",
            "SBIN": "3045",
            "KOTAKBANK": "881",
            "TATAMOTORS": "3456",
            "ONGC": "2475",
            "HINDUNILVR": "467",
            "NIFTY": "99926000",
            "BANKNIFTY": "99926009"
        }
        
        token = token_map.get(symbol.upper())
        if not token:
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found in token map")
        
        response = await asyncio.to_thread(
            smart_api.ltpData,
            exchange,
            symbol.upper(),
            token
        )
        
        if response.get("status") and response.get("data"):
            data = response["data"]
            return {
                "symbol": symbol.upper(),
                "exchange": exchange,
                "ltp": float(data.get("ltp", 0)),
                "open": float(data.get("open", 0)),
                "high": float(data.get("high", 0)),
                "low": float(data.get("low", 0)),
                "close": float(data.get("close", 0)),
                "token": token
            }
        
        raise HTTPException(status_code=500, detail="Failed to fetch LTP")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LTP fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# WebSocket for Agent Communication
# ============================================

class AgentConnectionManager:
    """Manages WebSocket connections for agent updates."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Agent WS client connected. Total: {len(self.active_connections)}")
        
        # Send welcome message
        await websocket.send_json({
            "type": "agent_message",
            "data": {
                "agent": "System",
                "message": "Connected to trading platform. Click ▶ to start agent.",
                "time": datetime.now().strftime("%H:%M:%S")
            }
        })
        
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Agent WS client disconnected. Total: {len(self.active_connections)}")
        
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
                
    async def send_agent_message(self, agent: str, message: str):
        """Send an agent message to all clients."""
        await self.broadcast({
            "type": "agent_message",
            "data": {
                "agent": agent,
                "message": message,
                "time": datetime.now().strftime("%H:%M:%S")
            }
        })
        
    async def send_trade(self, trade_data: dict):
        """Send trade update to all clients."""
        await self.broadcast({
            "type": "trade",
            "data": trade_data
        })
        
    async def send_symbol(self, symbol: str):
        """Send current symbol update."""
        await self.broadcast({
            "type": "symbol",
            "data": symbol
        })


agent_ws_manager = AgentConnectionManager()


@app.websocket("/ws")
async def websocket_agent(websocket: WebSocket):
    """
    WebSocket endpoint for agent communication.
    
    Sends:
    - agent_message: {"type": "agent_message", "data": {"agent": "...", "message": "...", "time": "..."}}
    - trade: {"type": "trade", "data": {...}}
    - symbol: {"type": "symbol", "data": "RELIANCE"}
    """
    await agent_ws_manager.connect(websocket)
    
    try:
        while True:
            try:
                # Keep connection alive and handle any incoming messages
                data = await websocket.receive_text()
                logger.debug(f"Received from client: {data}")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
    finally:
        agent_ws_manager.disconnect(websocket)


# Helper function to broadcast agent messages from anywhere in the app
async def broadcast_agent_message(agent: str, message: str):
    """Utility to broadcast agent message from any part of the application."""
    await agent_ws_manager.send_agent_message(agent, message)


# ============================================
# Agent Status & Control
# ============================================

@app.get("/api/agent/status")
async def get_agent_status():
    """Get current agent status."""
    broker_connected = len(connected_brokers) > 0
    is_running = supervisor._is_running if supervisor else False
    
    # Check LLM availability
    llm_enabled = bool(settings.openai_api_key or settings.anthropic_api_key or settings.groq_api_key)
    llm_ready = False
    try:
        from src.llm import LLMFactory
        llm = LLMFactory.get_instance()
        if llm:
            llm_ready = True
        elif llm_enabled:
            # Try to create LLM instance
            llm = LLMFactory.get_or_create()
            if llm:
                llm_ready = True
    except Exception as e:
        logger.warning(f"LLM check failed: {e}")
    
    return {
        "running": is_running,
        "broker_connected": broker_connected,
        "llm_enabled": llm_enabled,
        "llm_ready": llm_ready,
        "llm_provider": settings.llm_provider.value if settings.llm_provider else "none",
        "llm_model": settings.llm_model,
        "mode": settings.trading_mode.value,
        "cycle_count": supervisor._current_cycle if supervisor else 0,
        "symbols": ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"],
        "data_source": "broker" if broker_connected else "simulated",
        "message": "Ready - using simulated data" if not broker_connected else "Ready - broker connected"
    }


class SettingsUpdateRequest(BaseModel):
    llm_enabled: Optional[bool] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    llm_api_key: Optional[str] = None  # Generic key field from frontend
    trading_mode: Optional[str] = None
    max_position_size: Optional[float] = None
    max_daily_loss: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


@app.get("/api/settings")
async def get_settings():
    """Get user settings including saved API keys (masked)."""
    saved_keys = get_api_keys(user_id=1)
    
    # Find active provider
    active_provider = "none"
    active_key_info = None
    for k in saved_keys:
        if k["is_active"]:
            active_provider = k["provider"]
            active_key_info = k
            break
    
    return {
        "llm_provider": active_provider,
        "llm_model": settings.llm_model,
        "llm_api_key": f"••••••••{active_key_info['api_key_last4']}" if active_key_info else None,
        "api_keys": [
            {
                "provider": k["provider"],
                "masked_key": f"••••••••{k['api_key_last4']}",
                "model_name": k["model_name"],
                "is_active": k["is_active"],
                "updated_at": k["updated_at"]
            }
            for k in saved_keys
        ],
        "trading_mode": settings.trading_mode.value,
        "max_position_size": settings.max_position_size,
        "max_daily_loss": settings.max_daily_loss,
        "stop_loss_pct": settings.default_stop_loss_pct,
        "take_profit_pct": settings.default_take_profit_pct
    }


@app.post("/api/settings")
async def update_settings(request: SettingsUpdateRequest):
    """Update application settings."""
    updated = {}
    
    # Handle LLM API key save (from frontend)
    api_key_value = request.llm_api_key or request.openai_api_key
    provider = request.llm_provider or "openai"
    
    if api_key_value and api_key_value not in ("saved", ""):
        # Save encrypted to DB
        save_api_key(user_id=1, provider=provider, api_key=api_key_value, model_name=request.llm_model)
        
        # Also apply to runtime settings
        if provider in ("openai", "deepseek"):
            settings.openai_api_key = api_key_value
        elif provider == "anthropic":
            settings.anthropic_api_key = api_key_value
        elif provider == "groq":
            settings.groq_api_key = api_key_value
        
        # Update LLM provider setting
        provider_map = {"openai": "openai", "deepseek": "openai", "anthropic": "anthropic", "groq": "groq", "gemini": "openai"}
        try:
            from src.config.settings import LLMProvider
            settings.llm_provider = LLMProvider(provider_map.get(provider, "openai"))
        except Exception:
            pass
        
        updated["llm_api_key"] = "saved"
        updated["llm_provider"] = provider
        logger.info(f"API key saved for provider: {provider}")
    
    if request.llm_provider and request.llm_provider != "none" and not api_key_value:
        # Just switching provider, load key from DB
        db_key = get_api_key_decrypted(user_id=1, provider=request.llm_provider)
        if db_key:
            if request.llm_provider in ("openai", "deepseek"):
                settings.openai_api_key = db_key
            elif request.llm_provider == "anthropic":
                settings.anthropic_api_key = db_key
            elif request.llm_provider == "groq":
                settings.groq_api_key = db_key
            updated["llm_provider"] = request.llm_provider
    
    if request.llm_enabled is not None:
        if not request.llm_enabled:
            if supervisor:
                strategy = supervisor.get_agent("strategy")
                if strategy:
                    strategy.use_llm = False
            updated["llm_enabled"] = False
        else:
            try:
                from src.llm import LLMFactory
                llm = LLMFactory.get_or_create()
                if llm and supervisor:
                    strategy = supervisor.get_agent("strategy")
                    if strategy:
                        strategy.use_llm = True
                        strategy._llm = llm
                updated["llm_enabled"] = True
            except Exception as e:
                logger.error(f"Failed to enable LLM: {e}")
                updated["llm_enabled"] = False
                updated["error"] = str(e)
    
    if request.max_position_size is not None:
        settings.max_position_size = request.max_position_size
        updated["max_position_size"] = request.max_position_size
    
    if request.max_daily_loss is not None:
        settings.max_daily_loss = request.max_daily_loss
        updated["max_daily_loss"] = request.max_daily_loss
    
    return {"success": True, "updated": updated}


@app.delete("/api/settings/api-key/{provider}")
async def delete_api_key_endpoint(provider: str):
    """Delete a saved API key for a provider."""
    deleted = delete_api_key(user_id=1, provider=provider)
    
    if deleted:
        # Clear from runtime settings too
        if provider in ("openai", "deepseek"):
            settings.openai_api_key = None
        elif provider == "anthropic":
            settings.anthropic_api_key = None
        elif provider == "groq":
            settings.groq_api_key = None
        logger.info(f"API key deleted for provider: {provider}")
        return {"success": True, "message": f"{provider} API key deleted"}
    
    return {"success": False, "message": "Key not found"}


@app.post("/api/agent/start")
async def start_agent():
    """Start the trading agent."""
    if len(connected_brokers) == 0:
        await agent_ws_manager.send_agent_message(
            "System", 
            "⚠️ Cannot start: No broker connected. Go to Settings to connect."
        )
        return {"success": False, "message": "No broker connected"}
    
    await agent_ws_manager.send_agent_message("Supervisor", "🚀 Agent starting...")
    await agent_ws_manager.send_agent_message("Market Data Agent", "📊 Fetching market data...")
    
    return {"success": True, "message": "Agent started"}


@app.post("/api/agent/stop")  
async def stop_agent():
    """Stop the trading agent."""
    await agent_ws_manager.send_agent_message("Supervisor", "🛑 Agent stopped")
    return {"success": True, "message": "Agent stopped"}
