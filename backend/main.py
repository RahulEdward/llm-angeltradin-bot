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


# Global state
supervisor: Optional[SupervisorAgent] = None
active_connections: List[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global supervisor
    
    # Startup
    logger.info("Starting LLM-AngelAgent Trading Platform...")
    
    supervisor = SupervisorAgent(config={
        "symbols": ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"],
        "use_llm": settings.llm_provider is not None,
        "cycle_interval": 60
    })
    
    await supervisor.initialize()
    logger.info(f"Platform ready in {settings.trading_mode.value} mode")
    
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
from src.database import authenticate_user, get_all_users, create_user


@app.post("/api/login")
async def login(request: LoginRequest):
    """Authenticate user and return token."""
    user = authenticate_user(request.username, request.password)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
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
        raise HTTPException(status_code=503, detail="System not initialized")
    return supervisor.get_system_status()


# ============================================
# Mode Management
# ============================================

@app.get("/api/mode")
async def get_mode():
    """Get current trading mode."""
    return {"mode": settings.trading_mode.value}


@app.post("/api/mode")
async def set_mode(request: TradingModeRequest):
    """Switch trading mode."""
    try:
        mode = TradingMode(request.mode.lower())
        # Note: In production, this would require restart
        return {"mode": mode.value, "message": "Mode change requires restart"}
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")


# ============================================
# Trading Control
# ============================================

@app.post("/api/trading/start")
async def start_trading():
    """Start the trading loop."""
    if not supervisor:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    asyncio.create_task(supervisor.start_loop())
    return {"status": "started", "mode": settings.trading_mode.value}


@app.post("/api/trading/stop")
async def stop_trading():
    """Stop the trading loop."""
    if not supervisor:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    await supervisor.stop_loop()
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
    """Get quote for a specific symbol."""
    broker = BrokerFactory.get_instance()
    if not broker:
        raise HTTPException(status_code=503, detail="Broker not connected")
    
    quote = await broker.get_quote(symbol, exchange)
    if quote:
        return {
            "symbol": quote.symbol,
            "ltp": quote.ltp,
            "open": quote.open,
            "high": quote.high,
            "low": quote.low,
            "close": quote.close,
            "volume": quote.volume
        }
    raise HTTPException(status_code=404, detail="Symbol not found")


# ============================================
# Positions & Orders
# ============================================

@app.get("/api/positions")
async def get_positions():
    """Get current positions."""
    broker = BrokerFactory.get_instance()
    if not broker:
        raise HTTPException(status_code=503, detail="Broker not connected")
    
    positions = await broker.get_positions()
    return [{
        "symbol": p.symbol,
        "exchange": p.exchange,
        "quantity": p.quantity,
        "average_price": p.average_price,
        "ltp": p.ltp,
        "pnl": p.pnl,
        "pnl_pct": p.pnl_pct,
        "side": p.side.value
    } for p in positions]


@app.get("/api/orders")
async def get_orders():
    """Get order book."""
    broker = BrokerFactory.get_instance()
    if not broker:
        raise HTTPException(status_code=503, detail="Broker not connected")
    
    return await broker.get_order_book()


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
        raise HTTPException(status_code=503, detail="Risk agent not available")
    
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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Send status updates every 5 seconds
            if supervisor:
                status = supervisor.get_system_status()
                await websocket.send_json({
                    "type": "status",
                    "data": status,
                    "timestamp": datetime.now().isoformat()
                })
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        active_connections.remove(websocket)


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
# Account
# ============================================

@app.get("/api/account/profile")
async def get_profile():
    """Get account profile."""
    broker = BrokerFactory.get_instance()
    if not broker:
        raise HTTPException(status_code=503, detail="Broker not connected")
    
    return await broker.get_profile()


@app.get("/api/account/funds")
async def get_funds():
    """Get account funds."""
    broker = BrokerFactory.get_instance()
    if not broker:
        raise HTTPException(status_code=503, detail="Broker not connected")
    
    return await broker.get_funds()


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


async def fetch_symbols_background(account_id: str):
    """Fetch symbols in background after connection."""
    try:
        if account_id not in connected_brokers:
            return
        
        broker_data = connected_brokers[account_id]
        
        if broker_data.get("demo"):
            # Demo: Create sample symbols
            logger.info("Using demo symbol data")
            return
        
        smart_api = broker_data.get("smart_api")
        if not smart_api:
            return
        
        # Fetch instrument list
        import requests
        
        instruments_url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        response = requests.get(instruments_url, timeout=30)
        
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
            
            # Save to file
            symbols_file = Path(__file__).parent / "data" / "symbols.json"
            symbols_file.parent.mkdir(parents=True, exist_ok=True)
            symbols_file.write_text(json.dumps(nse_symbols, indent=2))
            
            logger.info(f"Fetched {len(nse_symbols)} symbols")
            
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
