# 🤖 LLM-AngelAgent: Complete Codebase Explanation (Hindi)

## 📌 Project Overview (परियोजना का अवलोकन)

यह एक **AI-powered autonomous trading platform** है जो Indian stock market (NSE/BSE) के लिए बनाया गया है। यह Angel One SmartAPI के साथ integrate है और multiple LLM providers (OpenAI, DeepSeek, Gemini, Claude) का use करता है trading decisions लेने के लिए।

---

## 🏗️ Architecture (11-Layer Design)

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND UI LAYER                            │
│  (React + Vite Dashboard - Mode Selector, Charts, Trade Logs)   │
├─────────────────────────────────────────────────────────────────┤
│                       API LAYER                                  │
│  (FastAPI - REST + WebSocket endpoints)                         │
├─────────────────────────────────────────────────────────────────┤
│                AGENT ORCHESTRATION LAYER                         │
│  (Supervisor Agent - सभी agents को coordinate करता है)          │
├─────────────────────────────────────────────────────────────────┤
│                   LLM REASONING LAYER                            │
│  (Multi-LLM: OpenAI, DeepSeek, Gemini, Claude, Groq, Ollama)   │
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
│  (SQLite - trades, decisions, logs)                             │
├─────────────────────────────────────────────────────────────────┤
│               LOGGING & AUDIT LAYER                              │
│  (Full decision audit trail)                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Folder Structure (फोल्डर संरचना)

```
llm-angelagent/
├── backend/                    # Python FastAPI Backend
│   ├── main.py                 # Main entry point - सभी API endpoints
│   ├── src/
│   │   ├── agents/             # 7 Trading Agents
│   │   │   ├── base.py         # Base Agent class
│   │   │   ├── supervisor_agent.py    # Controller - सभी agents को manage करता है
│   │   │   ├── market_data_agent.py   # Market data fetch करता है
│   │   │   ├── strategy_agent.py      # Trading signals generate करता है
│   │   │   ├── risk_manager_agent.py  # Risk check + veto power
│   │   │   ├── execution_agent.py     # Orders place करता है
│   │   │   ├── backtest_agent.py      # Backtesting engine
│   │   │   ├── regime_detector.py     # Market regime detection
│   │   │   ├── predict_agent.py       # Price prediction
│   │   │   └── reflection_agent.py    # Trade analysis
│   │   │
│   │   ├── broker/             # Broker Integration
│   │   │   ├── base.py         # Abstract broker interface
│   │   │   ├── angel_one.py    # Angel One SmartAPI implementation
│   │   │   ├── paper_broker.py # Paper trading simulation
│   │   │   └── factory.py      # Broker factory pattern
│   │   │
│   │   ├── llm/                # LLM Clients
│   │   │   ├── base.py         # Base LLM interface
│   │   │   ├── openai_client.py    # OpenAI GPT
│   │   │   ├── deepseek_client.py  # DeepSeek
│   │   │   ├── gemini_client.py    # Google Gemini
│   │   │   ├── claude_client.py    # Anthropic Claude
│   │   │   ├── factory.py      # LLM factory
│   │   │   └── metrics.py      # Token/latency tracking
│   │   │
│   │   ├── config/             # Configuration
│   │   │   └── settings.py     # Pydantic settings
│   │   │
│   │   ├── db/                 # Database
│   │   │   ├── models.py       # SQLAlchemy models
│   │   │   └── database.py     # DB connection
│   │   │
│   │   └── database.py         # User auth, trades, API keys
│   │
│   └── data/                   # Data storage
│       ├── llm_agent.db        # SQLite database
│       ├── broker_accounts.json # Encrypted broker credentials
│       └── symbols.json        # NSE symbols cache
│
├── frontend/                   # React + Vite Frontend
│   ├── src/
│   │   ├── App.jsx             # Main app component
│   │   └── pages/
│   │       ├── Dashboard.jsx   # Main dashboard
│   │       ├── Backtest.jsx    # Backtesting UI
│   │       ├── Settings.jsx    # Broker + LLM settings
│   │       ├── TradeLog.jsx    # Trade history
│   │       ├── AgentChat.jsx   # Agent messages
│   │       └── RiskPanel.jsx   # Risk metrics
│   │
│   └── index.html
│
└── config.yaml                 # Global configuration
```

---

## 🤖 Multi-Agent System (7 Agents)

### 1. **Supervisor Agent** (Controller)
**File:** `backend/src/agents/supervisor_agent.py`

**Kya karta hai:**
- सभी agents को initialize करता है
- Trading loop manage करता है
- Agents के बीच messages route करता है
- Cycle-by-cycle execution orchestrate करता है

```python
# Supervisor ka main flow:
async def process_cycle():
    # 1. Market Data Agent se data fetch
    market_messages = await market_data_agent.process_cycle()
    
    # 2. Strategy Agent ko data bhejo
    strategy_agent.receive_messages(market_messages)
    signals = await strategy_agent.process_cycle()
    
    # 3. Risk Manager se approval lo
    risk_manager.receive_messages(signals)
    decisions = await risk_manager.process_cycle()
    
    # 4. Execution Agent se orders place karo
    execution_agent.receive_messages(decisions)
    executions = await execution_agent.process_cycle()
```

---

### 2. **Market Data Agent** (The Oracle)
**File:** `backend/src/agents/market_data_agent.py`

**Kya karta hai:**
- Real-time quotes fetch करता है (LTP, Open, High, Low, Close)
- Historical OHLCV data fetch करता है
- Technical indicators calculate करता है (EMA, RSI, MACD, Bollinger Bands)
- Data को other agents को distribute करता है

**Important:** Broker connected hona chahiye real data ke liye. Bina broker ke koi data nahi milega.

```python
# Indicators jo calculate hote hain:
- EMA 9, EMA 21 (Exponential Moving Average)
- RSI 14 (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands (Upper, Lower, Middle)
- ATR 14 (Average True Range)
- Volume SMA 20
```

---

### 3. **Strategy Agent** (The Strategist)
**File:** `backend/src/agents/strategy_agent.py`

**Kya karta hai:**
- 4-Layer Filter apply करता है:
  1. **Trend Filter:** EMA crossover check
  2. **AI Filter:** LLM se analysis (optional)
  3. **Setup Filter:** RSI + MACD confirmation
  4. **Trigger Filter:** Entry conditions check

- Trading signals generate करता है (BUY/SELL/HOLD)
- Confidence score calculate करता है (0-100%)

```python
# Signal generation logic:
def _generate_signal(indicators, price):
    bull_signals = 0
    bear_signals = 0
    
    # EMA crossover
    if ema9 > ema21: bull_signals += 1
    elif ema9 < ema21: bear_signals += 1
    
    # RSI
    if rsi < 35: bull_signals += 1  # Oversold
    elif rsi > 65: bear_signals += 1  # Overbought
    
    # MACD
    if macd_hist > 0: bull_signals += 1
    elif macd_hist < 0: bear_signals += 1
    
    # 3+ signals chahiye trade ke liye
    if bull_signals >= 3: return "long"
    elif bear_signals >= 3: return "short"
    return "hold"
```

---

### 4. **Risk Manager Agent** (The Guardian)
**File:** `backend/src/agents/risk_manager_agent.py`

**Kya karta hai:**
- **VETO POWER** - Risky trades block kar sakta hai
- Position sizing calculate करता है
- Daily loss limit check करता है
- Kill-switch activate kar sakta hai (emergency stop)
- Stop-loss auto-correction

**Risk Parameters:**
```python
max_position_size = ₹100,000   # Maximum position value
max_daily_loss = ₹10,000       # Daily loss limit
max_trades_per_day = 20        # Trade count limit
default_stop_loss = 2%         # Auto stop-loss
max_drawdown = 5%              # Portfolio drawdown limit
```

**Veto Reasons:**
- Position size too large
- Daily loss limit exceeded
- Too many trades today
- Kill-switch active
- High volatility regime

---

### 5. **Execution Agent** (The Executor)
**File:** `backend/src/agents/execution_agent.py`

**Kya karta hai:**
- Broker ke through orders place करता है
- Order status track करता है
- Fill price record करता है
- Trade history maintain करता है

**Important:** Execution Agent ko pata nahi hota ki Live hai ya Paper mode - Broker Factory handle karta hai.

```python
# Order placement flow:
async def _execute_decision(decision):
    # 1. Broker se current price lo
    price = await broker.get_ltp(symbol, exchange)
    
    # 2. Order create karo
    order = OrderRequest(
        symbol=symbol,
        side=OrderSide.BUY,  # ya SELL
        quantity=quantity,
        order_type=OrderType.MARKET,
        product_type=ProductType.INTRADAY
    )
    
    # 3. Broker se order place karo
    result = await broker.place_order(order)
    
    # 4. Stop-loss order bhi place karo
    if result.success:
        await _place_stop_loss(symbol, entry_price, stop_loss_pct)
```

---

### 6. **Backtest Agent** (Historical Simulator)
**File:** `backend/src/agents/backtest_agent.py`

**Kya karta hai:**
- Historical data pe strategy test करता है
- Candle-by-candle simulation
- Comprehensive metrics calculate करता है

**Metrics Calculated:**
```python
# Returns
total_return          # Total profit/loss %
final_equity          # Final portfolio value
max_drawdown          # Maximum peak-to-trough decline
max_drawdown_duration # Kitne din drawdown raha

# Risk Metrics
sharpe_ratio          # Risk-adjusted return
sortino_ratio         # Downside risk-adjusted return
calmar_ratio          # Return / Max Drawdown
volatility            # Price fluctuation

# Trade Stats
total_trades          # Total trades executed
win_rate              # Winning trades %
profit_factor         # Gross profit / Gross loss
avg_win               # Average winning trade
avg_loss              # Average losing trade
avg_holding_time      # Average trade duration

# Long/Short Stats
long_trades           # Long position count
short_trades          # Short position count
long_win_rate         # Long trades win %
short_win_rate        # Short trades win %
```

---

### 7. **Regime Detector** (Market State)
**File:** `backend/src/agents/regime_detector.py`

**Kya karta hai:**
- Market ka current state detect करता है
- Volatility measure करता है
- Trend strength calculate करता है

**Market Regimes:**
```python
TRENDING_UP    # Strong uptrend
TRENDING_DOWN  # Strong downtrend
RANGING        # Sideways market
HIGH_VOLATILITY # Choppy market
LOW_VOLATILITY  # Quiet market
```

---

## 🔗 Broker Integration (Angel One)

### **File:** `backend/src/broker/angel_one.py`

**Features:**
- TOTP-based secure login
- Auto token refresh (6 hours)
- Symbol-token mapping
- All order types support

**Connection Flow:**
```python
# 1. User Settings page pe credentials enter karta hai
# 2. TOTP code enter karta hai
# 3. Backend Angel One se connect karta hai

async def connect():
    # SmartConnect client create
    client = SmartConnect(api_key=api_key)
    
    # TOTP generate
    totp = pyotp.TOTP(totp_secret)
    totp_value = totp.now()
    
    # Login
    session = client.generateSession(
        clientCode=client_id,
        password=password,
        totp=totp_value
    )
    
    # Tokens store
    auth_token = session["data"]["jwtToken"]
    refresh_token = session["data"]["refreshToken"]
    feed_token = session["data"]["feedToken"]
```

**Supported Operations:**
```python
# Market Data
get_ltp(symbol, exchange)           # Last traded price
get_quote(symbol, exchange)         # Full quote
get_historical_data(...)            # OHLCV candles

# Orders
place_order(order_request)          # New order
modify_order(order_id, ...)         # Modify existing
cancel_order(order_id)              # Cancel order
get_order_status(order_id)          # Check status

# Portfolio
get_positions()                     # Open positions
get_holdings()                      # Delivery holdings
get_funds()                         # Available margin
```

---

### **Paper Broker** (Simulation)
**File:** `backend/src/broker/paper_broker.py`

**Kya karta hai:**
- Real broker jaisa interface
- Orders simulate karta hai
- Positions track karta hai
- P&L calculate karta hai

**Important:** Paper broker real prices use karta hai (agar broker connected hai), sirf execution simulated hai.

---

### **Broker Factory** (Mode Switching)
**File:** `backend/src/broker/factory.py`

**Kya karta hai:**
- Trading mode ke basis pe correct broker create karta hai
- Singleton pattern - ek hi instance share hota hai

```python
# Mode ke basis pe broker:
LIVE mode     → AngelOneBroker (real execution)
PAPER mode    → PaperBroker (simulated execution)
BACKTEST mode → PaperBroker (historical simulation)
```

---

## 🧠 LLM Integration (Multi-Provider)

### **Supported Providers:**

| Provider | File | API Type |
|----------|------|----------|
| OpenAI | `openai_client.py` | OpenAI SDK |
| DeepSeek | `deepseek_client.py` | OpenAI-compatible |
| Gemini | `gemini_client.py` | Google REST API |
| Claude | `claude_client.py` | Anthropic Messages API |
| Groq | (via OpenAI client) | OpenAI-compatible |
| Ollama | (via OpenAI client) | Local OpenAI-compatible |

### **LLM Factory**
**File:** `backend/src/llm/factory.py`

```python
# Provider ke basis pe client create:
def create(provider):
    if provider == "openai":
        return OpenAIClient(api_key, model)
    elif provider == "deepseek":
        return DeepSeekClient(api_key)  # OpenAI-compatible
    elif provider == "gemini":
        return GeminiClient(api_key)    # Custom implementation
    elif provider == "anthropic":
        return ClaudeClient(api_key)    # Custom implementation
    elif provider == "groq":
        return OpenAIClient(api_key, base_url="groq.com")
```

### **LLM Metrics Tracking**
**File:** `backend/src/llm/metrics.py`

```python
# Har LLM call pe track hota hai:
total_input_tokens    # Prompt tokens
total_output_tokens   # Response tokens
total_tokens          # Total tokens used
min_latency_ms        # Fastest response
avg_latency_ms        # Average response time
max_latency_ms        # Slowest response
token_speed_tps       # Tokens per second
```

---

## 🖥️ Frontend (React + Vite)

### **App.jsx** - Main Component
```javascript
// State management:
- isAuthenticated    // Login status
- mode              // paper/live/backtest
- isRunning         // Trading loop status
- cycleCount        // Current cycle number
- equity            // Total portfolio value

// WebSocket connection for real-time updates
```

### **Dashboard.jsx** - Main Screen
**Features:**
- Live positions display
- Agent chatroom (real-time messages)
- Trade records table
- LLM metrics panel
- Symbol performance ranking

### **Settings.jsx** - Configuration
**Features:**
- Broker account management (save/connect/disconnect)
- LLM API key management (save/delete)
- Provider selection dropdown

### **Backtest.jsx** - Historical Testing
**Features:**
- Symbol selection
- Date range picker
- Timeframe selection
- Results display with metrics

---

## 🔄 Complete Trading Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER LOGIN                                    │
│  → Username/Password → JWT Token → Auto-load API keys from DB   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                 BROKER CONNECTION (Settings)                     │
│  → Enter Angel One credentials → TOTP verification → Connected  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   MODE SELECTION                                 │
│  → Paper (default) / Live / Backtest                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                 START TRADING (Click ▶)                          │
│  → Supervisor Agent starts trading loop                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    TRADING CYCLE                                 │
│                                                                  │
│  1. Market Data Agent                                           │
│     → Fetch quotes for RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK │
│     → Calculate indicators (EMA, RSI, MACD, BB, ATR)            │
│     → Broadcast MARKET_UPDATE message                           │
│                              ↓                                   │
│  2. Strategy Agent                                              │
│     → Receive market data                                       │
│     → Apply 4-layer filter                                      │
│     → Generate signals (BUY/SELL/HOLD)                          │
│     → Broadcast SIGNAL message                                  │
│                              ↓                                   │
│  3. Risk Manager Agent                                          │
│     → Receive signals                                           │
│     → Check position limits                                     │
│     → Check daily loss limit                                    │
│     → APPROVE or VETO                                           │
│     → Broadcast DECISION or VETO message                        │
│                              ↓                                   │
│  4. Execution Agent                                             │
│     → Receive approved decisions                                │
│     → Place order via broker                                    │
│     → Place stop-loss order                                     │
│     → Broadcast EXECUTION message                               │
│                              ↓                                   │
│  5. WebSocket Broadcast                                         │
│     → All messages sent to frontend                             │
│     → Dashboard updates in real-time                            │
│                                                                  │
│  → Wait 60 seconds → Repeat cycle                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Database Schema

### **Users Table**
```sql
users:
  - id (PRIMARY KEY)
  - username (UNIQUE)
  - hashed_password
  - email
  - role (user/admin)
  - is_active
```

### **Trades Table**
```sql
trades:
  - id (PRIMARY KEY)
  - user_id (FOREIGN KEY)
  - symbol
  - exchange
  - side (BUY/SELL)
  - quantity
  - entry_price
  - exit_price
  - pnl
  - status (open/closed)
  - entry_time
  - exit_time
  - strategy
```

### **API Keys Table**
```sql
api_keys:
  - id (PRIMARY KEY)
  - user_id (FOREIGN KEY)
  - provider (openai/deepseek/gemini/anthropic)
  - api_key_encrypted
  - api_key_last4
  - model_name
  - is_active
  - created_at
  - updated_at
```

### **Agent Logs Table**
```sql
agent_logs:
  - id (PRIMARY KEY)
  - agent_name
  - message
  - level (info/warning/error)
  - cycle_number
  - timestamp
```

---

## ⚙️ Configuration (settings.py)

```python
# Trading Mode
trading_mode = "paper"  # paper/live/backtest

# Angel One Credentials
angel_api_key = ""
angel_client_id = ""
angel_password = ""
angel_totp_secret = ""

# LLM Configuration
llm_provider = "openai"  # openai/deepseek/gemini/anthropic/groq/ollama
llm_model = "gpt-4-turbo-preview"
openai_api_key = None
deepseek_api_key = None
gemini_api_key = None
anthropic_api_key = None

# Risk Management
max_position_size = 100000.0    # ₹1 lakh max position
max_daily_loss = 10000.0        # ₹10k daily loss limit
max_trades_per_day = 20         # 20 trades/day max
default_stop_loss_pct = 2.0     # 2% stop-loss
default_take_profit_pct = 4.0   # 4% take-profit
kill_switch_enabled = True      # Emergency stop enabled
```

---

## 🚀 API Endpoints Summary

### **Authentication**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/login` | User login |
| POST | `/api/users` | Create user |

### **Trading Control**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/trading/start` | Start trading loop |
| POST | `/api/trading/stop` | Stop trading |
| POST | `/api/trading/cycle` | Run single cycle |

### **Mode Management**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mode` | Get current mode |
| POST | `/api/mode` | Switch mode |

### **Market Data**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/positions` | Get positions |
| GET | `/api/orders` | Get order book |
| GET | `/api/trades` | Get trade book |
| GET | `/api/account/funds` | Get funds |
| GET | `/api/account/holdings` | Get holdings |

### **Broker Management**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/broker/accounts` | List saved accounts |
| POST | `/api/broker/accounts` | Save new account |
| POST | `/api/broker/connect` | Connect with TOTP |
| POST | `/api/broker/disconnect/{id}` | Disconnect |
| GET | `/api/broker/symbols` | Get symbols list |

### **Settings**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings` | Get settings |
| POST | `/api/settings` | Update settings |
| DELETE | `/api/settings/api-key/{provider}` | Delete API key |

### **Backtesting**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/backtest` | Run backtest |
| GET | `/api/backtest/{run_id}` | Get result |

### **Agent Status**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/agent/status` | Get agent status |
| GET | `/api/llm/metrics` | Get LLM metrics |

### **WebSocket**
| Endpoint | Description |
|----------|-------------|
| `/ws` | Agent messages, trades, status updates |
| `/ws/market` | Real-time market data |

---

## 🔐 Security Features

1. **Encrypted Storage**
   - Broker credentials encrypted with Fernet
   - API keys encrypted in database
   - Only last 4 characters shown in UI

2. **TOTP Authentication**
   - Angel One requires TOTP for login
   - 6-digit code from authenticator app

3. **JWT Tokens**
   - User authentication via JWT
   - Token expiry: 24 hours

4. **Kill Switch**
   - Emergency stop for all trading
   - Activates on max daily loss breach

---

## 📝 Summary (सारांश)

यह platform एक complete autonomous trading system है जो:

1. **Multi-Agent Architecture** use करता है - 7 specialized agents
2. **Angel One** broker के साथ integrate है
3. **Multiple LLM providers** support करता है
4. **Paper/Live/Backtest** modes provide करता है
5. **Real-time WebSocket** updates देता है
6. **Comprehensive risk management** implement करता है
7. **Full audit trail** maintain करता है

**Key Files:**
- `backend/main.py` - All API endpoints
- `backend/src/agents/supervisor_agent.py` - Main orchestrator
- `backend/src/broker/angel_one.py` - Broker integration
- `backend/src/llm/factory.py` - LLM provider management
- `frontend/src/App.jsx` - Main React component
- `frontend/src/pages/Dashboard.jsx` - Trading dashboard

---

*Document generated: February 2026*
*Version: 1.0.0*
