# 🤖 LLM-AngelAgent: AI-Powered Trading Platform for Indian Markets

## Architecture Overview

A production-ready, multi-agent LLM-powered autonomous trading platform for the Indian market with Angel One SmartAPI integration.

---

## 🎯 Platform Modes

### 1. LIVE TRADING MODE
- Real money execution via Angel One SmartAPI
- Strict risk controls & safety mechanisms
- Kill-switch capability

### 2. PAPER TRADING MODE
- Simulated execution with real market data
- No actual broker orders placed
- Same agents and logic as live mode

### 3. BACKTESTING MODE
- Historical data-based simulation
- Candle-by-candle replay
- Full performance metrics

---

## 🏗️ System Architecture (11-Layer Design)

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND UI LAYER                            │
│  (Next.js Dashboard - Mode Selector, Charts, Trade Logs)        │
├─────────────────────────────────────────────────────────────────┤
│                       API LAYER                                  │
│  (FastAPI - REST + WebSocket endpoints)                         │
├─────────────────────────────────────────────────────────────────┤
│                AGENT ORCHESTRATION LAYER                         │
│  (Supervisor Agent - coordinates all agents)                    │
├─────────────────────────────────────────────────────────────────┤
│                   LLM REASONING LAYER                            │
│  (Multi-LLM: OpenAI, Ollama, Mistral, LLaMA)                   │
├─────────────────────────────────────────────────────────────────┤
│                    STRATEGY LAYER                                │
│  (Four-Layer Filter: Trend → AI → Setup → Trigger)             │
├─────────────────────────────────────────────────────────────────┤
│                 BACKTESTING ENGINE                               │
│  (Historical replay, metrics calculation)                       │
├─────────────────────────────────────────────────────────────────┤
│                RISK MANAGEMENT LAYER                             │
│  (Veto power, position sizing, kill-switch)                     │
├─────────────────────────────────────────────────────────────────┤
│                  MARKET DATA LAYER                               │
│  (Real-time feeds, historical data, indicators)                │
├─────────────────────────────────────────────────────────────────┤
│               BROKER EXECUTION LAYER                             │
│  (Angel One SmartAPI abstraction)                               │
├─────────────────────────────────────────────────────────────────┤
│              MEMORY & PERSISTENCE LAYER                          │
│  (SQLite/PostgreSQL - trades, decisions, logs)                  │
├─────────────────────────────────────────────────────────────────┤
│               LOGGING & AUDIT LAYER                              │
│  (Full decision audit trail, white-box transparency)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🤖 Agent Architecture (7 Independent Agents)

### Core Agents
1. **Market Data Agent** - Fetches real-time/historical data
2. **Strategy Agent** - Technical analysis & signal generation
3. **Risk Manager Agent** - Position sizing, stop-loss, veto power
4. **Execution Agent** - Order placement via broker abstraction
5. **Memory Agent** - Persists decisions, trades, state
6. **Backtest Agent** - Historical simulation engine
7. **Supervisor Agent** - Orchestrates agent communication

### Agent Communication
- JSON-based structured messages
- Event-driven architecture
- Async message queue

---

## 📊 Database Schema

### Core Tables
- `users` - User authentication & preferences
- `strategies` - Strategy configurations
- `trades` - Executed trades (all modes)
- `orders` - Order lifecycle tracking
- `backtest_runs` - Backtest session metadata
- `backtest_trades` - Individual backtest trades
- `agent_logs` - Agent decision audit trail
- `risk_events` - Risk violations & vetoes
- `system_state` - Platform state snapshots

---

## 🔗 Angel One Integration

### Features
- Secure TOTP-based login
- Auto token refresh
- Symbol-token mapping for NSE/BSE/MCX
- Order types: MARKET, LIMIT, SL, SL-M
- Position & holdings management

### Broker Abstraction
```python
class BaseBroker(ABC):
    @abstractmethod
    async def place_order(...) -> OrderResult
    @abstractmethod
    async def get_positions(...) -> List[Position]
    @abstractmethod
    async def get_ltp(...) -> float
```

---

## 🖥️ Frontend Features

1. **Authentication** - Login/Register
2. **Mode Selector** - Live/Paper/Backtest toggle
3. **Dashboard** - Real-time P&L, positions
4. **Market Watch** - Live quotes, watchlist
5. **Strategy Config** - Enable/disable agents
6. **Trade Logs** - Order history
7. **Backtest Results** - Charts & metrics
8. **Agent Chat** - Decision reasoning logs
9. **Risk Metrics** - Drawdown, exposure
10. **System Health** - Connection status

---

## 📁 Project Structure

```
llm-angelagent/
├── backend/
│   ├── src/
│   │   ├── agents/           # All agent implementations
│   │   ├── api/              # FastAPI routes
│   │   ├── broker/           # Angel One integration
│   │   ├── data/             # Market data handlers
│   │   ├── execution/        # Order execution engine
│   │   ├── llm/              # Multi-LLM clients
│   │   ├── risk/             # Risk management
│   │   ├── strategy/         # Strategy logic
│   │   ├── backtest/         # Backtesting engine
│   │   ├── db/               # Database models
│   │   └── utils/            # Utilities
│   ├── config/
│   ├── tests/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── services/
│   ├── package.json
│   └── Dockerfile
├── data/                     # Stored market data
├── logs/                     # System logs
├── .env.example
├── docker-compose.yml
└── README.md
```
