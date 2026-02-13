# 🤖 Reference Repo Agent Architecture - Complete Analysis Report

> Reference repo ek crypto trading bot hai (Binance) jo multi-agent pipeline use karta hai.
> Yeh report unke agent system ka detailed analysis hai — hamare Indian stock market (Angel One) app ke comparison ke saath.

---

## 📋 Overview: 5-Layer Pipeline

Reference repo ka core architecture ek **5-step pipeline** hai jo har trading cycle mein sequentially execute hota hai:

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRADING DECISION PIPELINE                     │
│                                                                  │
│  Step 1: DATA FETCH                                             │
│  🕵️ DataSyncAgent (The Oracle)                                  │
│  → Concurrent 5m/15m/1h kline fetch                             │
│  → Dual-view: stable (closed) + live (current)                  │
│  → Funding rate, OI, institutional flow                         │
│                        ↓                                        │
│  Step 2: TECHNICAL ANALYSIS                                     │
│  👨‍🔬 QuantAnalystAgent (The Strategist)                          │
│  → Trend analysis (EMA20/60 alignment)                          │
│  → Oscillator analysis (RSI, KDJ)                               │
│  → Sentiment (funding rate, volume proxy)                       │
│  → Market trap detection (bull trap, weak rebound, etc.)        │
│                        ↓                                        │
│  Step 2.5: ML PREDICTION (Optional)                             │
│  🔮 PredictAgent (The Prophet)                                  │
│  → Rule-based scoring OR LightGBM model                        │
│  → 30min price up probability (0.0 - 1.0)                      │
│                        ↓                                        │
│  Step 3: DECISION MAKING                                        │
│  ⚖️ DecisionCoreAgent (The Critic)                               │
│  → Weighted voting across all signals                           │
│  → Multi-period alignment check (1h > 15m > 5m)                │
│  → Overtrading guard                                            │
│  → Market trap filtering                                        │
│  → Dynamic trade params (SL/TP/size)                            │
│                        ↓                                        │
│  Step 4: RISK AUDIT                                             │
│  🛡️ RiskAuditAgent (The Guardian)                                │
│  → Stop-loss direction auto-correction                          │
│  → Margin sufficiency check                                     │
│  → Reverse position block (veto power)                          │
│  → Regime-based filtering                                       │
│  → Position quality check                                       │
│                        ↓                                        │
│  Step 5: EXECUTION                                              │
│  🚀 Executor Engine                                             │
│  → Binance API order placement                                  │
│  → Only if RiskAudit PASSED                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Agent Categories

### Core Agents (Always ON — disable nahi kar sakte)

| Agent | Alias | Role |
|-------|-------|------|
| DataSyncAgent | The Oracle | Market data fetch (5m/15m/1h concurrent) |
| QuantAnalystAgent | The Strategist | Technical analysis + sentiment + trap detection |
| RiskAuditAgent | The Guardian | Risk control with veto power |

### Optional Agents (Config se ON/OFF)

| Agent | Default | Role |
|-------|---------|------|
| PredictAgent | ✅ ON | ML prediction (LightGBM or rule-based) |
| RegimeDetector | ✅ ON | Market state detection (trending/choppy/volatile) |
| TriggerDetector | ✅ ON | 5m entry patterns (engulfing, breakout) |
| PositionAnalyzer | ❌ OFF | Price position in range (support/resistance) |
| SymbolSelector | ✅ ON | AUTO3 (backtest) + AUTO1 (momentum) symbol selection |
| TrendAgent (Local) | ✅ ON | 1h trend rule-based analysis |
| SetupAgent (Local) | ✅ ON | 15m setup rule-based analysis |
| TriggerAgent (Local) | ✅ ON | 5m trigger rule-based analysis |
| ReflectionAgent (Local) | ✅ ON | Post-trade rule-based reflection |
| TrendAgent (LLM) | ❌ OFF | 1h trend via LLM (expensive) |
| SetupAgent (LLM) | ❌ OFF | 15m setup via LLM |
| TriggerAgent (LLM) | ❌ OFF | 5m trigger via LLM |
| ReflectionAgent (LLM) | ❌ OFF | Trade reflection via LLM |
| AIPredictionFilter | ✅ ON | AI veto mechanism |

---

## 🔍 Agent-by-Agent Deep Dive

### 1. 🕵️ DataSyncAgent (The Oracle)

**File:** `src/agents/data_sync_agent.py`

**Kya karta hai:**
- Async concurrent fetch — `asyncio.gather` se 5m, 15m, 1h data ek saath laata hai (60% time save)
- **Dual-view data structure:**
  - `stable_view` = `iloc[:-1]` — completed candles (indicators ke liye)
  - `live_view` = `iloc[-1]` — current incomplete candle (latest price ke liye)
- Time alignment verification (5m vs 15m vs 1h timestamps match karte hain ya nahi)
- External data: Funding rate, Open Interest, institutional netflow
- **Incremental K-line cache** — pehle cache check, sirf naye data fetch karo
- WebSocket support (optional, REST fallback)

**Output:** `MarketSnapshot` dataclass with:
```python
@dataclass
class MarketSnapshot:
    stable_5m: pd.DataFrame    # Completed 5m candles
    live_5m: Dict              # Current 5m candle
    stable_15m: pd.DataFrame   # Completed 15m candles
    live_15m: Dict             # Current 15m candle
    stable_1h: pd.DataFrame    # Completed 1h candles
    live_1h: Dict              # Current 1h candle
    quant_data: Dict           # External quant data
    binance_funding: Dict      # Funding rate
    symbol: str                # Trading pair
```

**Key Pattern:** Dual-view solve karta hai ek common problem — agar current incomplete candle ko indicators mein include karo toh noisy results aate hain. Stable view se accurate indicators, live view se latest price.

---

### 2. 👨‍🔬 QuantAnalystAgent (The Strategist)

**File:** `src/agents/quant_analyst_agent.py`

**Kya karta hai:**
- **Trend Analysis** (per timeframe): EMA20/EMA60 alignment → score -100 to +100
  - Price > EMA20 > EMA60 = Bullish (+60)
  - Price < EMA20 < EMA60 = Bearish (-60)
- **Oscillator Analysis** (per timeframe): RSI + KDJ → score -100 to +100
  - RSI < 30 = Oversold (+40), RSI > 70 = Overbought (-40)
  - KDJ J < 20 = Bullish (+30), J > 80 = Bearish (-30)
- **Sentiment Analysis:** Funding rate + volume change proxy
- **Volatility:** ATR calculation per timeframe
- **Market Regime Detection:** RegimeDetector integration
- **🆕 Market Trap Detection** (user experience logic):
  - `bull_trap_risk` — Rapid rise, slow fall (急涨缓跌 = distribution)
  - `weak_rebound` — Crash followed by low-volume bounce (don't bottom-fish)
  - `volume_divergence` — High price, low volume (smart money exiting)
  - `accumulation` — Bottom with increasing volume (smart money buying)
  - `panic_bottom` — Extreme oversold + high volume (contrarian buy)
  - `fomo_top` — Extreme overbought + high volume (contrarian sell)

**Output:** Dict with trend scores, oscillator scores, sentiment, regime, traps, overall_score

---

### 3. 🔮 PredictAgent (The Prophet)

**File:** `src/agents/predict_agent.py`

**Kya karta hai:**
- **Dual mode:**
  - **Rule-based scoring** (default): Weighted feature scoring system
  - **ML model** (optional): LightGBM trained model (`models/prophet_lgb_{symbol}.pkl`)
- **Input:** 80+ technical features (trend confirmation, RSI, BB position, EMA cross, volume ratio, momentum, etc.)
- **Output:** `PredictResult` with:
  - `probability_up` (0.0 - 1.0): Price up probability
  - `probability_down` (0.0 - 1.0)
  - `confidence` (0.0 - 1.0): Prediction confidence
  - `signal`: strong_bullish / bullish / neutral / bearish / strong_bearish
  - `factors`: Factor decomposition (kaunsa feature kitna contribute kiya)
- **Rule-based scoring logic:**
  - Trend confirmation score ≥ 2 → +0.15 bullish
  - RSI < 30 → +0.12 bullish (oversold reversal)
  - BB position < 20 → +0.10 bullish
  - EMA cross strength > 0.5 → +0.08 bullish
  - Volume ratio > 1.5 → amplifies existing direction
  - Final probability = sigmoid-style normalization
- **ML mode:** LightGBM predict_proba → confidence scaled by validation AUC
- **Safety:** Rule-based confidence capped at 70% to prevent over-aggressive AI veto

---

### 4. ⚖️ DecisionCoreAgent (The Critic)

**File:** `src/agents/decision_core_agent.py` (1070 lines — sabse complex agent)

**Kya karta hai:**

#### Signal Weights (Optimized Config):
```python
SignalWeight:
  trend_5m:      0.03   # Minimal — 5m is noisy
  trend_15m:     0.12   # Medium
  trend_1h:      0.30   # Highest — core trend judgment
  oscillator_5m: 0.03   # Minimal
  oscillator_15m:0.07   # Medium
  oscillator_1h: 0.10   # Important
  prophet:       0.05   # Low — avoid ML overfitting
  sentiment:     0.25   # Dynamic (0 if no data)
```

#### Decision Flow:
1. **Overtrading Guard Check** — Same symbol min 4 cycles gap, max 2 positions in 6h, consecutive loss cooldown
2. **Extract Scores** — Trend/oscillator/sentiment/prophet scores from QuantAnalyst output
3. **Market Regime + Position Analysis** — RegimeDetector + PositionAnalyzer
4. **Weighted Score Calculation** — All signals × weights → single score (-100 to +100)
5. **Early Filter** — Choppy market + middle position + weak signal → forced HOLD
6. **Multi-Period Alignment** — 1h/15m/5m direction check:
   - All 3 same direction = Strong alignment ✅
   - 1h + 15m same = Partial alignment ✅
   - Otherwise = No alignment ❌
7. **Choppy Market Branch** — Mean reversion strategy (RSI oversold → buy, overbought → sell)
8. **Trend Market Branch** — Score-to-action mapping with dynamic thresholds
9. **Volume/Trend Filters** — RVOL < 0.5 → block, ADX < 20 + low volume → block
10. **Market Trap Filtering** — Bull trap blocks long, FOMO top blocks long, panic bottom blocks short
11. **Institutional Flow Divergence** — Tech says long but institutions selling → 50% confidence cut
12. **Dynamic Trade Params** — SL/TP/position size based on regime + position + confidence
13. **Output:** `VoteResult` with action, confidence, weighted_score, trade_params

#### Overtrading Guard:
```python
MIN_CYCLES_SAME_SYMBOL = 4      # Same symbol gap
MAX_POSITIONS_6H = 2            # Max opens in 6 hours
LOSS_STREAK_COOLDOWN = 6        # Cooldown after 2 consecutive losses
```

#### Score-to-Action Mapping:
- **Trending Up:** Long threshold = 22, Short threshold = 32
- **Trending Down:** Long threshold = 32, Short threshold = 18
- **Choppy:** Both thresholds = 30
- **Aligned:** Thresholds reduced by 2
- **Strong signal (aligned + high score):** 85% confidence
- **Medium signal:** 55-75% confidence
- **Weak/conflicting:** HOLD

---

### 5. 🛡️ RiskAuditAgent (The Guardian)

**File:** `src/agents/risk_audit_agent.py` (981 lines — second most complex)

**Kya karta hai — VETO POWER hai iske paas:**

#### Risk Parameters:
```python
max_leverage: 12.0
max_position_pct: 35%        # Single position max
max_total_risk_pct: 1.2%     # Total risk exposure
min_stop_loss_pct: 0.2%      # Minimum SL distance
max_stop_loss_pct: 2.5%      # Maximum SL distance
```

#### Check Sequence (order matters):
1. **Hold/Wait → Auto-pass**
2. **Balance check** — Zero balance → block
3. **Regime filter:**
   - Unknown regime + low confidence → block
   - Volatile + low confidence → block
   - Choppy + confidence < 60 → block
4. **Short-specific guards** (bahut strict):
   - Short confidence < 55 → block
   - Short without strong setup + confidence < 65 → block
   - Short consecutive losses ≥ 2 → cooldown block
   - Short in volatile_directionless without strong setup → block
   - Short when sentiment bullish → block
   - Short when ATR > 3% + low confidence → block
5. **Symbol-specific rules** (FILUSDT, FETUSDT, LINKUSDT special handling)
6. **Position filter:**
   - Middle zone (40-60%) + low confidence → block (R/R too poor)
   - Long at high position (>80%) + low confidence → block
   - Short at low position → block
7. **Oscillator conflict:**
   - Long when oscillator strongly overbought (< -70) → block
   - Short when oscillator strongly oversold (> +50) → block
8. **R/R ratio check** — reward/risk < 1.15 → block
9. **Duplicate position block** — Already have position → no new open
10. **Reverse position block** — Have long, trying short → FATAL block
11. **Stop-loss auto-correction:**
    - Long SL ≥ entry → auto-fix using ATR-based distance
    - Short SL ≤ entry → auto-fix
    - SL too tight or too wide → auto-adjust
12. **Margin sufficiency** — Required margin > 95% balance → block
13. **Leverage check** — > max_leverage → block
14. **Position size check** — > 35% of balance → warning
15. **Total risk exposure** — > 1.2% → warning
16. **Market trap audit** — Bull trap + long → block

**Key Feature:** ATR-based dynamic stop-loss — `1.5 × ATR` as SL distance, bounded by min/max limits.

---

### 6. 🔄 RegimeDetector

**File:** `src/agents/regime_detector_agent.py`

**Market States:**
| Regime | Condition | Trading Impact |
|--------|-----------|----------------|
| TRENDING_UP | TSS ≥ 70 + direction up | Lower long threshold, higher short threshold |
| TRENDING_DOWN | TSS ≥ 70 + direction down | Lower short threshold, higher long threshold |
| CHOPPY | ADX < 20 | Mean reversion only, higher thresholds |
| VOLATILE | ATR% > 2% | Reduce position size, widen SL |
| VOLATILE_DIRECTIONLESS | ADX high but no alignment | Very cautious, block most trades |

**Trend Strength Score (TSS):**
- ADX > 25 → +40 points
- EMA aligned → +30 points
- MACD momentum confirmed → +30 points
- TSS ≥ 70 = Strong trend, TSS ≥ 30 = Weak trend

**Choppy Market Analysis:**
- Bollinger Band squeeze detection (width < 70% of average)
- Support/resistance identification
- Breakout probability estimation
- Mean reversion signal (buy dip / sell rally)

---

### 7. 🎯 TriggerDetector

**File:** `src/agents/trigger_detector_agent.py`

**5-minute entry pattern detection:**

| Pattern | Condition | Use |
|---------|-----------|-----|
| Engulfing (阳包阴) | Previous bearish + current bullish wraps it | Reversal entry |
| Volume Breakout | Close > max(prev 3 highs) + Volume > 1.0× MA3 | Momentum entry |
| RVOL Momentum | RVOL ≥ 0.5 + candle direction matches trade direction | Fallback trigger |

**RVOL (Relative Volume):**
- Current volume / 10-bar average volume
- RVOL > 1.5 = High interest
- RVOL > 2.0 = Potential institutional activity
- RVOL < 0.5 = Weak conviction

---

### 8. 📍 PositionAnalyzer

**File:** `src/agents/position_analyzer_agent.py`

**Price position in recent range:**
| Position % | Location | Quality | Allow Long | Allow Short |
|-----------|----------|---------|------------|-------------|
| 0-15% | Support | Excellent | ✅ | ❌ |
| 15-30% | Lower | Good | ✅ | ❌ |
| 30-40% | Lower-Mid | Poor | ✅ | ✅ |
| 40-60% | Middle | Terrible | ❌ | ❌ |
| 60-70% | Upper-Mid | Poor | ✅ | ✅ |
| 70-85% | Upper | Good | ❌ | ✅ |
| 85-100% | Resistance | Excellent | ❌ | ✅ |

**Core Rule:** Middle zone (40-60%) mein koi bhi trade nahi — R/R ratio bahut kharab hota hai.

---

### 9. 🔝 SymbolSelectorAgent

**File:** `src/agents/symbol_selector_agent.py`

**Two modes:**

**AUTO3 (Heavy — 6h refresh):**
1. Get AI500 Top 10 by 24h volume
2. Stage 1: Coarse filter (1h backtest, step=12) → Top 5
3. Stage 2: Fine filter (15m backtest, step=3) → Top 3
4. Composite scoring: Return (30%) + Sharpe (20%) + Win Rate (25%) + Drawdown (15%) + Trade Count (10%)
5. Cache results for 6 hours

**AUTO1 (Lightweight — per cycle):**
1. Last 30 minutes momentum analysis
2. ADX filter (< 20 = skip, no trend)
3. Score = |change%| × volume_ratio × ADX_boost
4. Select strongest UP mover + strongest DOWN mover
5. Volume + price minimum filters

---

## ⚙️ Configuration System

**File:** `src/agents/agent_config.py`

```python
@dataclass
class AgentConfig:
    predict_agent: bool = True
    ai_prediction_filter_agent: bool = True
    regime_detector_agent: bool = True
    position_analyzer_agent: bool = False    # Default OFF
    trigger_detector_agent: bool = True
    trend_agent_llm: bool = False            # LLM agents default OFF (expensive)
    setup_agent_llm: bool = False
    trigger_agent_llm: bool = False
    trend_agent_local: bool = True           # Local agents default ON
    setup_agent_local: bool = True
    trigger_agent_local: bool = True
    reflection_agent_llm: bool = False
    reflection_agent_local: bool = True
    symbol_selector_agent: bool = True
```

**Override methods:**
- `config.yaml` file
- Environment variables: `AGENT_PREDICT_AGENT=false`
- Env vars take priority over config file

**Registry Pattern:**
```python
registry = AgentRegistry(config)
registry.register_class('predict_agent', PredictAgent)
agent = registry.get('predict_agent')  # Returns None if disabled
```
- Lazy initialization — agent tab hi create hota hai jab pehli baar use ho
- Dependency validation — AIPredictionFilter requires PredictAgent

---

## 🔄 Base Agent Pattern

**File:** `src/agents/base_agent.py`

```python
class BaseAgent(ABC, Generic[InputT, OutputT]):
    @property
    @abstractmethod
    def name(self) -> str: ...          # snake_case identifier

    @property
    def is_optional(self) -> bool:       # Override for core agents
        return True

    @abstractmethod
    async def execute(self, input_data: InputT) -> OutputT: ...
```

- Generic typed input/output
- Async-first design with sync wrapper
- `AgentResult` standard wrapper (success, data, error)

---

## 📊 Hamare App Se Comparison

| Feature | Reference Repo (Crypto/Binance) | Hamara App (Indian Stocks/Angel One) |
|---------|-------------------------------|--------------------------------------|
| **Pipeline** | 5-step sequential | Supervisor loop with agents |
| **Data Source** | Binance API + WebSocket | Angel One API + Local CSV |
| **Timeframes** | 5m, 15m, 1h | 5m, 15m, 1h, 1d |
| **Dual View** | ✅ stable + live | ❌ Single view |
| **ML Prediction** | LightGBM + rule fallback | ❌ Not implemented |
| **Regime Detection** | ADX + BB + ATR + TSS | ❌ Not implemented |
| **Trap Detection** | 6 trap patterns | ❌ Not implemented |
| **Overtrading Guard** | ✅ Cycle-based + loss cooldown | ❌ Not implemented |
| **Risk Audit** | 981 lines, 16+ checks | Basic risk checks |
| **Position Analysis** | Range-based quality scoring | ❌ Not implemented |
| **Symbol Selection** | AUTO3 backtest + AUTO1 momentum | Fixed 10 symbols |
| **Stop-Loss** | ATR-based dynamic | Fixed percentage |
| **Signal Weights** | Configurable per signal | Not weighted |
| **Multi-Period Alignment** | 1h > 15m > 5m priority | Not implemented |
| **Market** | Crypto (24/7, futures, leverage) | Indian stocks (9:15-3:30, cash) |
| **Broker** | Binance | Angel One |

---

## 🎯 Key Takeaways — Kya Seekh Sakte Hain

1. **Dual-View Data** — Stable (completed candles) alag, live (current) alag. Indicators stable pe calculate karo, price live se lo.

2. **Weighted Voting** — Har signal ko weight do. 1h trend ko zyada weight (0.30), 5m noise ko kam (0.03). Blindly sab equal mat rakho.

3. **Multi-Period Alignment** — Sirf tab trade karo jab 1h aur 15m same direction mein ho. 5m noise ignore karo.

4. **Overtrading Guard** — Same symbol pe baar baar trade mat karo. Consecutive loss ke baad cooldown rakho.

5. **Market Regime Awareness** — Trending market mein trend follow karo, choppy mein mean reversion karo, volatile mein position size kam karo.

6. **Risk Audit Veto Power** — Risk agent ko final say do. Agar risk agent bole "no" toh trade nahi hoga, chahe baaki sab "yes" bole.

7. **ATR-Based Dynamic SL** — Fixed percentage SL ki jagah ATR use karo. Volatile market mein SL wider, calm market mein tighter.

8. **Trap Detection** — User experience se seekho. Bull trap, weak rebound, volume divergence — yeh sab real patterns hain jo losses cause karte hain.

9. **Position Quality** — Middle zone (40-60%) mein trade mat karo. Support pe buy, resistance pe sell — basic but effective.

10. **Config-Driven Architecture** — Agents ko ON/OFF karna easy hona chahiye. Environment variables se override ho sake.

---

*Report generated: February 13, 2026*
*Source: reference-repo/src/agents/*
