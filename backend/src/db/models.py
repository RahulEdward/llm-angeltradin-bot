"""
Database Models for LLM-AngelAgent Trading Platform
Complete schema for trades, orders, strategies, backtests, and audit logs
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, 
    Text, ForeignKey, JSON, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


# ============================================
# Enums
# ============================================

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "SL"
    STOP_LOSS_MARKET = "SL-M"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class ProductType(str, Enum):
    INTRADAY = "INTRADAY"
    DELIVERY = "DELIVERY"
    MARGIN = "MARGIN"
    CARRYFORWARD = "CARRYFORWARD"


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"
    MCX = "MCX"
    BFO = "BFO"
    CDS = "CDS"


class TradingMode(str, Enum):
    LIVE = "LIVE"
    PAPER = "PAPER"
    BACKTEST = "BACKTEST"


class RiskEventType(str, Enum):
    VETO = "VETO"
    POSITION_LIMIT = "POSITION_LIMIT"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    KILL_SWITCH = "KILL_SWITCH"
    DRAWDOWN_ALERT = "DRAWDOWN_ALERT"


# ============================================
# User Model
# ============================================

class User(Base):
    """User authentication and profile"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    
    # Angel One credentials (encrypted)
    angel_client_id = Column(String(100), nullable=True)
    angel_api_key_encrypted = Column(Text, nullable=True)
    angel_totp_encrypted = Column(Text, nullable=True)
    
    # Preferences
    default_mode = Column(SQLEnum(TradingMode), default=TradingMode.PAPER)
    risk_tolerance = Column(Float, default=1.0)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    strategies = relationship("Strategy", back_populates="user")
    trades = relationship("Trade", back_populates="user")
    orders = relationship("Order", back_populates="user")
    backtest_runs = relationship("BacktestRun", back_populates="user")


# ============================================
# Strategy Model
# ============================================

class Strategy(Base):
    """Trading strategy configurations"""
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Strategy parameters
    symbols = Column(JSON, nullable=False)  # List of symbols
    timeframes = Column(JSON, default=["5m", "15m", "1h"])
    exchange = Column(SQLEnum(Exchange), default=Exchange.NSE)
    product_type = Column(SQLEnum(ProductType), default=ProductType.INTRADAY)
    
    # Agent configuration
    agents_config = Column(JSON, default={})
    
    # Risk parameters
    max_position_size = Column(Float, default=100000.0)
    stop_loss_pct = Column(Float, default=2.0)
    take_profit_pct = Column(Float, default=4.0)
    max_trades_per_day = Column(Integer, default=10)
    
    # LLM settings
    use_llm_reasoning = Column(Boolean, default=True)
    llm_model = Column(String(100), default="gpt-4-turbo-preview")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="strategies")
    trades = relationship("Trade", back_populates="strategy")
    backtest_runs = relationship("BacktestRun", back_populates="strategy")


# ============================================
# Trade Model
# ============================================

class Trade(Base):
    """Executed trades across all modes"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    
    # Trade identification
    trade_id = Column(String(50), unique=True, nullable=False, index=True)
    mode = Column(SQLEnum(TradingMode), nullable=False)
    
    # Symbol details
    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(SQLEnum(Exchange), nullable=False)
    symbol_token = Column(String(20), nullable=True)
    
    # Trade details
    side = Column(SQLEnum(OrderSide), nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    
    # P&L
    realized_pnl = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True)
    fees = Column(Float, default=0.0)
    
    # Timing
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    
    # Risk management
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    trailing_stop = Column(Float, nullable=True)
    
    # LLM reasoning
    entry_reasoning = Column(Text, nullable=True)
    exit_reasoning = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # Status
    is_open = Column(Boolean, default=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="trades")
    strategy = relationship("Strategy", back_populates="trades")
    orders = relationship("Order", back_populates="trade")
    
    __table_args__ = (
        Index("ix_trades_symbol_mode", "symbol", "mode"),
        Index("ix_trades_entry_time", "entry_time"),
    )


# ============================================
# Order Model
# ============================================

class Order(Base):
    """Order lifecycle tracking"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=True)
    
    # Order identification
    order_id = Column(String(50), unique=True, nullable=False, index=True)
    broker_order_id = Column(String(100), nullable=True)
    mode = Column(SQLEnum(TradingMode), nullable=False)
    
    # Symbol details
    symbol = Column(String(50), nullable=False)
    exchange = Column(SQLEnum(Exchange), nullable=False)
    symbol_token = Column(String(20), nullable=True)
    
    # Order details
    side = Column(SQLEnum(OrderSide), nullable=False)
    order_type = Column(SQLEnum(OrderType), nullable=False)
    product_type = Column(SQLEnum(ProductType), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=True)  # For limit orders
    trigger_price = Column(Float, nullable=True)  # For SL orders
    
    # Execution
    filled_quantity = Column(Integer, default=0)
    average_price = Column(Float, nullable=True)
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING)
    
    # Timing
    placed_at = Column(DateTime, nullable=False)
    filled_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    # Response
    broker_response = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="orders")
    trade = relationship("Trade", back_populates="orders")


# ============================================
# Backtest Run Model
# ============================================

class BacktestRun(Base):
    """Backtest session metadata"""
    __tablename__ = "backtest_runs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    
    # Run identification
    run_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    
    # Configuration
    symbols = Column(JSON, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    initial_capital = Column(Float, nullable=False)
    
    # Settings used
    config_snapshot = Column(JSON, nullable=False)
    use_llm = Column(Boolean, default=False)
    
    # Results
    final_capital = Column(Float, nullable=True)
    total_return_pct = Column(Float, nullable=True)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, nullable=True)
    
    # Risk metrics
    max_drawdown_pct = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    avg_win = Column(Float, nullable=True)
    avg_loss = Column(Float, nullable=True)
    
    # Equity curve
    equity_curve = Column(JSON, nullable=True)
    
    # Status
    status = Column(String(20), default="running")  # running, completed, failed
    error_message = Column(Text, nullable=True)
    
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="backtest_runs")
    strategy = relationship("Strategy", back_populates="backtest_runs")
    backtest_trades = relationship("BacktestTrade", back_populates="backtest_run")


# ============================================
# Backtest Trade Model
# ============================================

class BacktestTrade(Base):
    """Individual trades within a backtest"""
    __tablename__ = "backtest_trades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    backtest_run_id = Column(Integer, ForeignKey("backtest_runs.id"), nullable=False)
    
    # Trade details
    symbol = Column(String(50), nullable=False)
    side = Column(SQLEnum(OrderSide), nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=False)
    
    # P&L
    pnl = Column(Float, nullable=False)
    pnl_pct = Column(Float, nullable=False)
    
    # Exit reason
    exit_reason = Column(String(50), nullable=True)  # SL, TP, Signal, TimeExit
    
    # LLM reasoning (if enabled)
    reasoning = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    
    # Relationships
    backtest_run = relationship("BacktestRun", back_populates="backtest_trades")


# ============================================
# Agent Log Model
# ============================================

class AgentLog(Base):
    """Agent decision audit trail"""
    __tablename__ = "agent_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Context
    session_id = Column(String(50), nullable=False, index=True)
    cycle_id = Column(String(50), nullable=False)
    mode = Column(SQLEnum(TradingMode), nullable=False)
    
    # Agent info
    agent_name = Column(String(50), nullable=False, index=True)
    agent_type = Column(String(50), nullable=True)  # LLM or Local
    
    # Input/Output
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    decision = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    
    # LLM specific
    llm_prompt = Column(Text, nullable=True)
    llm_response = Column(Text, nullable=True)
    llm_tokens_used = Column(Integer, nullable=True)
    
    # Timing
    execution_time_ms = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index("ix_agent_logs_session_cycle", "session_id", "cycle_id"),
    )


# ============================================
# Risk Event Model
# ============================================

class RiskEvent(Base):
    """Risk violations and vetoes"""
    __tablename__ = "risk_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Context
    session_id = Column(String(50), nullable=False, index=True)
    mode = Column(SQLEnum(TradingMode), nullable=False)
    
    # Event details
    event_type = Column(SQLEnum(RiskEventType), nullable=False)
    severity = Column(String(20), nullable=False)  # INFO, WARNING, CRITICAL
    
    # Details
    symbol = Column(String(50), nullable=True)
    trigger_value = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)
    description = Column(Text, nullable=False)
    action_taken = Column(String(100), nullable=True)
    
    # Related decision
    blocked_trade_id = Column(String(50), nullable=True)
    original_decision = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())


# ============================================
# System State Model
# ============================================

class SystemState(Base):
    """Platform state snapshots"""
    __tablename__ = "system_state"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Session info
    session_id = Column(String(50), nullable=False, index=True)
    mode = Column(SQLEnum(TradingMode), nullable=False)
    
    # State data
    active_positions = Column(JSON, nullable=True)
    pending_orders = Column(JSON, nullable=True)
    daily_pnl = Column(Float, default=0.0)
    daily_trades = Column(Integer, default=0)
    
    # Agent states
    agents_status = Column(JSON, nullable=True)
    
    # Health
    broker_connected = Column(Boolean, default=False)
    data_feed_active = Column(Boolean, default=False)
    last_data_time = Column(DateTime, nullable=True)
    
    # Kill switch
    kill_switch_active = Column(Boolean, default=False)
    kill_switch_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
