"""
Decision Core Agent — The Critic
=================================
Weighted voting mechanism integrating quantitative signals from multiple
timeframes, ML predictions, and market regime awareness.

Adapted for Indian equity markets:
  - No short-selling (long-only + exit signals)
  - Leverage fixed at 1x (delivery-based)
  - INR currency
  - No crypto-specific logic

Core capabilities:
  1. Weighted voting — configurable signal weights across timeframes
  2. Multi-period alignment — 1h > 15m > 5m priority
  3. Overtrading guard — cooldown after consecutive losses
  4. Market regime filtering — choppy/volatile market protection
  5. Dynamic trade params — SL/TP/size based on regime + confidence
"""

import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

import pandas as pd

from .position_analyzer_agent import PositionAnalyzer
from .regime_detector import RegimeDetector
from .predict_agent import PredictResult


# ============================================
# Overtrading Guard
# ============================================
@dataclass
class TradeRecord:
    """Individual trade record for tracking."""
    symbol: str
    action: str
    timestamp: datetime
    pnl: float = 0.0


class OvertradingGuard:
    """
    Overtrading Prevention — prevents frequent trading and consecutive loss spirals.

    Rules:
      - Same symbol minimum 4 cycle gap
      - Maximum 2 new positions per 6 hours
      - Cooldown of 6 cycles after 2 consecutive losses
    """

    MIN_CYCLES_SAME_SYMBOL = 4
    MAX_POSITIONS_6H = 2
    LOSS_STREAK_COOLDOWN = 6
    CONSECUTIVE_LOSS_THRESHOLD = 2

    def __init__(self):
        self.trade_history: List[TradeRecord] = []
        self.consecutive_losses = 0
        self.last_trade_cycle: Dict[str, int] = {}
        self.cooldown_until_cycle: int = 0

    def record_trade(self, symbol: str, action: str, pnl: float = 0.0, current_cycle: int = 0):
        """Record a completed trade."""
        self.trade_history.append(TradeRecord(
            symbol=symbol, action=action, timestamp=datetime.now(), pnl=pnl
        ))
        self.last_trade_cycle[symbol] = current_cycle

        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.CONSECUTIVE_LOSS_THRESHOLD:
                self.cooldown_until_cycle = current_cycle + self.LOSS_STREAK_COOLDOWN
                logger.warning(
                    f"⚠️ {self.consecutive_losses} consecutive losses — "
                    f"cooldown until cycle {self.cooldown_until_cycle}"
                )
        else:
            self.consecutive_losses = 0

    def can_open_position(self, symbol: str, current_cycle: int = 0) -> Tuple[bool, str]:
        """Check if a new position is allowed."""
        # Cooldown period
        if current_cycle < self.cooldown_until_cycle:
            remaining = self.cooldown_until_cycle - current_cycle
            return False, f"Loss cooldown active — {remaining} cycles remaining"

        # Same symbol interval
        if symbol in self.last_trade_cycle:
            cycles_since = current_cycle - self.last_trade_cycle[symbol]
            if cycles_since < self.MIN_CYCLES_SAME_SYMBOL:
                wait = self.MIN_CYCLES_SAME_SYMBOL - cycles_since
                return False, f"{symbol} too recent — wait {wait} cycles"

        # 6-hour position limit
        six_hours_ago = datetime.now().timestamp() - 6 * 3600
        recent_opens = sum(
            1 for t in self.trade_history
            if t.timestamp.timestamp() > six_hours_ago and "open" in t.action.lower()
        )
        if recent_opens >= self.MAX_POSITIONS_6H:
            return False, f"6h limit reached ({recent_opens}/{self.MAX_POSITIONS_6H})"

        return True, "Position allowed"

    def get_status(self) -> Dict:
        return {
            "consecutive_losses": self.consecutive_losses,
            "cooldown_until": self.cooldown_until_cycle,
            "recent_trades": len(self.trade_history),
            "symbols_traded": list(self.last_trade_cycle.keys()),
        }


# ============================================
# Signal Weights
# ============================================
@dataclass
class SignalWeight:
    """
    Configurable signal weights for weighted voting.
    All weights (excluding dynamic sentiment) should sum to ~1.0.

    Indian equity focus:
      - 1h timeframe gets highest weight (core trend)
      - 5m is mostly noise, kept minimal
      - No short-biased weights
    """
    # Trend signals (total ~0.45)
    trend_5m: float = 0.03
    trend_15m: float = 0.12
    trend_1h: float = 0.30
    # Oscillator signals (total ~0.20)
    oscillator_5m: float = 0.03
    oscillator_15m: float = 0.07
    oscillator_1h: float = 0.10
    # ML prediction weight
    prophet: float = 0.05
    # Sentiment signal (dynamic)
    sentiment: float = 0.25
    # LLM signal (future)
    llm_signal: float = 0.0


# ============================================
# Vote Result
# ============================================
@dataclass
class VoteResult:
    """Decision output from the voting mechanism."""
    action: str                    # 'buy', 'sell', 'hold'
    confidence: float              # 0-100
    weighted_score: float          # -100 to +100
    vote_details: Dict[str, float] = field(default_factory=dict)
    multi_period_aligned: bool = False
    reason: str = ""
    regime: Optional[Dict] = None
    position: Optional[Dict] = None
    trade_params: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "weighted_score": self.weighted_score,
            "vote_details": self.vote_details,
            "multi_period_aligned": self.multi_period_aligned,
            "reason": self.reason,
            "regime": self.regime,
            "position": self.position,
            "trade_params": self.trade_params,
        }


# ============================================
# Decision Core Agent
# ============================================
class DecisionCoreAgent:
    """
    The Critic — Weighted voting decision engine.

    Core flow:
      1. Extract signal scores from quant analysis
      2. Detect market regime and price position
      3. Apply weighted voting
      4. Filter by regime, alignment, volume, traps
      5. Calculate dynamic trade parameters
      6. Output final VoteResult

    Indian equity adaptations:
      - Actions: 'buy', 'sell' (exit), 'hold' (no short-selling)
      - No leverage adjustments (always 1x)
      - INR-denominated position sizing
    """

    def __init__(self, weights: Optional[SignalWeight] = None):
        self.weights = weights or SignalWeight()
        self.history: List[VoteResult] = []

        # Sub-analyzers
        self.position_analyzer = PositionAnalyzer()
        self.regime_detector = RegimeDetector()

        # Performance tracking per signal
        self.performance_tracker = {
            "trend_5m": {"total": 0, "correct": 0},
            "trend_15m": {"total": 0, "correct": 0},
            "trend_1h": {"total": 0, "correct": 0},
            "oscillator_5m": {"total": 0, "correct": 0},
            "oscillator_15m": {"total": 0, "correct": 0},
            "oscillator_1h": {"total": 0, "correct": 0},
        }

        # Overtrading guard
        self.overtrading_guard = OvertradingGuard()
        self.current_cycle = 0

        logger.info("DecisionCoreAgent (The Critic) initialized — Indian equity mode")

    async def make_decision(
        self,
        quant_analysis: Dict,
        predict_result: Optional[PredictResult] = None,
        market_data: Optional[Dict] = None,
    ) -> VoteResult:
        """
        Execute weighted voting decision.

        Args:
            quant_analysis: Output from QuantAnalystAgent with trend/oscillator/sentiment
            predict_result: PredictAgent ML prediction (optional)
            market_data: Dict with df_5m, df_15m, df_1h, current_price

        Returns:
            VoteResult with action, confidence, and trade parameters
        """
        self.current_cycle += 1
        symbol = quant_analysis.get("symbol", "UNKNOWN")

        # ========== Overtrading check ==========
        overtrade_ok, overtrade_reason = self.overtrading_guard.can_open_position(
            symbol, self.current_cycle
        )

        # 1. Extract signal scores
        trend_data = quant_analysis.get("trend", {})
        osc_data = quant_analysis.get("oscillator", {})
        sentiment_data = quant_analysis.get("sentiment", {})
        traps = quant_analysis.get("traps", {})

        scores = {
            "trend_5m": trend_data.get("trend_5m_score", 0),
            "trend_15m": trend_data.get("trend_15m_score", 0),
            "trend_1h": trend_data.get("trend_1h_score", 0),
            "oscillator_5m": osc_data.get("osc_5m_score", 0),
            "oscillator_15m": osc_data.get("osc_15m_score", 0),
            "oscillator_1h": osc_data.get("osc_1h_score", 0),
            "sentiment": sentiment_data.get("total_sentiment_score", 0),
        }

        # Integrate Prophet prediction
        if predict_result:
            prob = predict_result.probability_up
            prophet_score = (prob - 0.5) * 200  # Map 0-1 to -100..+100
            scores["prophet"] = prophet_score
        else:
            scores["prophet"] = 0.0

        # Dynamic sentiment weight
        has_sentiment = scores.get("sentiment", 0) != 0
        w_sentiment = self.weights.sentiment if has_sentiment else 0.0
        w_others = 1.0 - w_sentiment

        # 2. Market regime and position analysis
        regime = None
        position = None
        if market_data:
            df_5m = market_data.get("df_5m")
            curr_price = market_data.get("current_price")
            if df_5m is not None and curr_price is not None:
                regime = self.regime_detector.detect_regime(df_5m)
                position = self.position_analyzer.analyze_position(df_5m, curr_price)

        volume_ratio = self._get_volume_ratio(
            market_data.get("df_5m") if market_data else None
        )

        # 3. Weighted score calculation (-100 to +100)
        weighted_score = (
            (scores["trend_5m"] * self.weights.trend_5m +
             scores["trend_15m"] * self.weights.trend_15m +
             scores["trend_1h"] * self.weights.trend_1h +
             scores["oscillator_5m"] * self.weights.oscillator_5m +
             scores["oscillator_15m"] * self.weights.oscillator_15m +
             scores["oscillator_1h"] * self.weights.oscillator_1h +
             scores.get("prophet", 0) * self.weights.prophet) * w_others +
            (scores.get("sentiment", 0) * w_sentiment)
        )

        # 4. Vote details for dashboard
        vote_details = {
            "trend_5m": scores["trend_5m"] * self.weights.trend_5m * w_others,
            "trend_15m": scores["trend_15m"] * self.weights.trend_15m * w_others,
            "trend_1h": scores["trend_1h"] * self.weights.trend_1h * w_others,
            "oscillator_5m": scores["oscillator_5m"] * self.weights.oscillator_5m * w_others,
            "oscillator_15m": scores["oscillator_15m"] * self.weights.oscillator_15m * w_others,
            "oscillator_1h": scores["oscillator_1h"] * self.weights.oscillator_1h * w_others,
            "prophet": scores.get("prophet", 0) * self.weights.prophet * w_others,
            "sentiment": scores.get("sentiment", 0) * w_sentiment,
        }

        # 5. Choppy + bad position early filter
        if regime and position:
            if (regime["regime"] == "choppy" and
                position["location"] == "middle" and
                abs(weighted_score) < 30):
                result = VoteResult(
                    action="hold",
                    confidence=10.0,
                    weighted_score=0,
                    vote_details=vote_details,
                    multi_period_aligned=False,
                    reason=f"Choppy market + mid-range position ({position['position_pct']:.1f}%) — no edge",
                    regime=regime,
                    position=position,
                )
                self.history.append(result)
                return result

        # 6. Multi-period alignment
        aligned, alignment_reason = self._check_multi_period_alignment(
            scores["trend_1h"], scores["trend_15m"], scores["trend_5m"]
        )

        # ========== Choppy market strategy branch ==========
        is_choppy = False
        if regime:
            regime_type = (regime.get("regime", "") or "").lower()
            if regime_type in ("volatile_directionless", "choppy", "ranging"):
                is_choppy = True

        if is_choppy:
            logger.info("🔄 [Choppy Market] Switching to mean reversion strategy")
            action, base_confidence, alignment_reason = self._evaluate_choppy_strategy(
                quant_analysis, position
            )
        else:
            action, base_confidence = self._score_to_action(weighted_score, aligned, regime)

        # ========== Weak alignment + weak trend filter ==========
        if action in ("buy",) and regime and not aligned:
            adx = regime.get("adx", 0)
            if adx < 25:
                logger.warning(f"🚫 Weak alignment + low ADX ({adx:.1f} < 25) — hold")
                action = "hold"
                base_confidence = 0.1
                alignment_reason = f"Weak alignment + low ADX ({adx:.1f} < 25)"

        # ========== Low volume / weak trend filter ==========
        if action in ("buy",) and regime:
            adx = regime.get("adx", 0)
            if volume_ratio is not None and volume_ratio < 0.5:
                logger.warning(f"🚫 Low volume filter: RVOL {volume_ratio:.2f} < 0.5")
                action = "hold"
                base_confidence = 0.1
                alignment_reason = f"Low volume filter (RVOL {volume_ratio:.2f} < 0.5)"
            elif volume_ratio is not None and adx < 20 and volume_ratio < 0.8:
                if abs(weighted_score) < 40:
                    logger.warning(f"🚫 Low volume + weak trend: ADX {adx:.1f}, RVOL {volume_ratio:.2f}")
                    action = "hold"
                    base_confidence = 0.1
                    alignment_reason = f"Low volume + weak trend (ADX {adx:.1f}, RVOL {volume_ratio:.2f})"
                else:
                    base_confidence *= 0.80
                    alignment_reason += f" | Volume penalty (ADX {adx:.1f}, RVOL {volume_ratio:.2f})"
            elif volume_ratio is not None and volume_ratio > 1.5:
                base_confidence = min(base_confidence * 1.15, 0.95)
                alignment_reason += f" | High volume confirmation (RVOL {volume_ratio:.2f})"

        # ========== Overtrading guard ==========
        if action in ("buy",):
            if not overtrade_ok:
                logger.warning(f"🚫 Overtrading guard: {overtrade_reason}")
                action = "hold"
                base_confidence = 0.1
                alignment_reason = overtrade_reason

        # ========== Market trap filters ==========
        if action == "buy":
            # Bull trap risk
            if traps.get("bull_trap_risk"):
                logger.warning("🚫 Bull trap risk — blocking buy")
                action = "hold"
                base_confidence = 0.1
                alignment_reason = "Bull trap risk detected — avoiding chase"

            # Weak rebound
            if traps.get("weak_rebound"):
                base_confidence *= 0.5
                alignment_reason += " | Weak rebound warning (low volume bounce)"
                if base_confidence < 0.6:
                    action = "hold"
                    alignment_reason = "Weak rebound — confidence too low"

            # Volume divergence (high price, low volume)
            if traps.get("volume_divergence"):
                base_confidence *= 0.7
                alignment_reason += " | Volume divergence warning (price up, volume down)"

            # Accumulation pattern
            if traps.get("accumulation"):
                base_confidence = min(base_confidence * 1.2, 0.95)
                alignment_reason += " | Accumulation pattern confirmed"

            # Panic bottom (good for buying)
            if traps.get("panic_bottom"):
                base_confidence = min(base_confidence * 1.3, 0.95)
                alignment_reason += " | Panic selling opportunity (oversold + volume surge)"

            # FOMO top (bad for buying)
            if traps.get("fomo_top"):
                logger.warning("🚫 FOMO top — blocking buy")
                action = "hold"
                base_confidence = 0.1
                alignment_reason = "FOMO top exhaustion — avoid buying"

        # For sell (exit) signals
        if action == "sell":
            if traps.get("panic_bottom"):
                logger.warning("🚫 Panic bottom — blocking sell")
                action = "hold"
                base_confidence = 0.1
                alignment_reason = "Panic bottom — hold position, don't sell into fear"

        # 8. Confidence calibration
        final_confidence = base_confidence * 100

        if regime and position:
            final_confidence = self._calculate_confidence(
                final_confidence, regime, position, aligned
            )

        # 9. Generate reason
        reason = self._generate_reason(
            weighted_score, aligned, alignment_reason, quant_analysis,
            prophet_score=scores.get("prophet", 0), regime=regime
        )

        # 10. Dynamic trade parameters
        trade_params = self._calculate_trade_params(regime, position, final_confidence, action)

        # 11. Build result
        result = VoteResult(
            action=action,
            confidence=final_confidence,
            weighted_score=weighted_score,
            vote_details=vote_details,
            multi_period_aligned=aligned,
            reason=reason,
            regime=regime,
            position=position,
            trade_params=trade_params,
        )

        self.history.append(result)
        return result

    # ===================== Volume helper =====================

    def _get_volume_ratio(self, df: Optional[pd.DataFrame], window: int = 20) -> Optional[float]:
        """Current volume / rolling average volume."""
        if df is None or df.empty or "volume" not in df.columns:
            return None

        if "volume_ratio" in df.columns:
            try:
                return float(df["volume_ratio"].iloc[-1])
            except Exception:
                pass

        if len(df) < window:
            return None

        series = df["volume"].iloc[-window:]
        avg = series.mean()
        if avg <= 0:
            return None

        return float(series.iloc[-1] / avg)

    # ===================== Confidence =====================

    def _calculate_confidence(
        self, base_conf: float, regime: Dict, position: Dict, aligned: bool
    ) -> float:
        """Calculate comprehensive confidence with bonuses and penalties."""
        conf = base_conf

        # Bonuses
        if aligned:
            conf += 15
        if regime["regime"] in ("trending_up", "trending_down"):
            conf += 10
        if position.get("quality") == "excellent":
            conf += 15

        # Penalties
        if regime["regime"] == "choppy":
            conf -= 25
        if position.get("location") == "middle":
            conf -= 30
        if regime["regime"] == "volatile":
            conf -= 20

        return max(5.0, min(100.0, conf))

    # ===================== Trade parameters =====================

    def _calculate_trade_params(
        self, regime: Optional[Dict], position: Optional[Dict],
        confidence: float, action: str
    ) -> Dict:
        """
        Dynamic trade parameters based on market state.

        Indian equity: no leverage, INR-denominated sizing.
        """
        base_size = 10000.0       # Base position ₹10,000
        base_stop_loss = 1.5      # Base SL %
        base_take_profit = 3.0    # Base TP %

        size_mult = 1.0
        sl_mult = 1.0
        tp_mult = 1.0

        if regime:
            regime_type = (regime.get("regime", "") or "").lower()
            if "volatile" in regime_type:
                size_mult *= 0.5
                sl_mult *= 1.5
                tp_mult *= 1.5
            elif regime_type in ("trending_up", "trending_down"):
                size_mult *= 1.2
                tp_mult *= 1.5
            elif regime_type in ("choppy", "volatile_directionless", "ranging"):
                size_mult *= 0.7
                sl_mult *= 0.5
                tp_mult *= 0.4

        if position:
            quality = position.get("quality", "average")
            if quality == "excellent":
                size_mult *= 1.3
            elif quality == "poor":
                size_mult *= 0.5

        if confidence > 70:
            size_mult *= min(confidence / 70, 1.5)
        elif confidence < 50:
            size_mult *= 0.7

        if action == "hold":
            size_mult = 0

        return {
            "position_size_inr": round(base_size * size_mult, 2),
            "stop_loss_pct": round(base_stop_loss * sl_mult, 2),
            "take_profit_pct": round(base_take_profit * tp_mult, 2),
            "leverage": 1,  # Always 1x for Indian equity delivery
            "reason": f"size_mult={size_mult:.2f}, sl_mult={sl_mult:.2f}, tp_mult={tp_mult:.2f}",
        }

    # ===================== Multi-period alignment =====================

    def _check_multi_period_alignment(
        self, score_1h: float, score_15m: float, score_5m: float
    ) -> Tuple[bool, str]:
        """
        Multi-period trend alignment check.

        Priority: 1h > 15m > 5m. 1h must confirm direction.
        """
        signs = [
            1 if score_1h >= 25 else (-1 if score_1h <= -25 else 0),
            1 if score_15m >= 18 else (-1 if score_15m <= -18 else 0),
            1 if score_5m >= 12 else (-1 if score_5m <= -12 else 0),
        ]

        # Full 3-period alignment
        if signs[0] == signs[1] == signs[2] and signs[0] != 0:
            direction = "bullish" if signs[0] > 0 else "bearish"
            return True, f"Strong {direction} alignment (1h+15m+5m)"

        # 1h + 15m alignment
        if signs[0] == signs[1] and signs[0] != 0:
            direction = "bullish" if signs[0] > 0 else "bearish"
            return True, f"Mid-long {direction} alignment (1h+15m)"

        return False, f"Period divergence (1h:{signs[0]}, 15m:{signs[1]}, 5m:{signs[2]}) — waiting for 1h confirmation"

    # ===================== Choppy strategy =====================

    def _evaluate_choppy_strategy(
        self, quant_analysis: Dict, position: Optional[Dict] = None
    ) -> Tuple[str, float, str]:
        """
        Mean reversion strategy for choppy/ranging markets.

        Indian equity: only buy signals (no short-selling).
        RSI oversold + low position → buy opportunity.
        RSI overbought + high position → sell (exit) signal.
        """
        osc_data = quant_analysis.get("oscillator", {})
        rsi_15m = osc_data.get("rsi_15m", 50)
        rsi_5m = osc_data.get("rsi_5m", 50)
        rsi = rsi_15m if rsi_15m != 50 else rsi_5m

        pos_pct = 50
        if position:
            pos_pct = position.get("position_pct", 50)

        # Mean reversion buy: RSI oversold + low position
        if rsi < 40 or pos_pct < 40:
            if rsi < 35 and pos_pct < 45:
                confidence = 0.70 + (35 - rsi) * 0.005
                logger.info(f"📈 [Choppy] Strong mean reversion buy: RSI={rsi:.1f}, pos={pos_pct:.1f}%")
                return "buy", min(confidence, 0.80), f"Choppy buy (RSI={rsi:.1f}, pos={pos_pct:.1f}%)"
            elif rsi < 40 and pos_pct < 50:
                logger.info(f"📈 [Choppy] Mean reversion buy: RSI={rsi:.1f}, pos={pos_pct:.1f}%")
                return "buy", 0.60, f"Choppy buy (RSI={rsi:.1f}, pos={pos_pct:.1f}%)"

        # Mean reversion sell (exit): RSI overbought + high position
        if rsi > 60 or pos_pct > 60:
            if rsi > 65 and pos_pct > 55:
                confidence = 0.70 + (rsi - 65) * 0.005
                logger.info(f"📉 [Choppy] Strong mean reversion sell: RSI={rsi:.1f}, pos={pos_pct:.1f}%")
                return "sell", min(confidence, 0.80), f"Choppy sell/exit (RSI={rsi:.1f}, pos={pos_pct:.1f}%)"
            elif rsi > 60 and pos_pct > 50:
                logger.info(f"📉 [Choppy] Mean reversion sell: RSI={rsi:.1f}, pos={pos_pct:.1f}%")
                return "sell", 0.60, f"Choppy sell/exit (RSI={rsi:.1f}, pos={pos_pct:.1f}%)"

        return "hold", 0.3, f"Choppy hold (RSI={rsi:.1f}, pos={pos_pct:.1f}%)"

    # ===================== Score → Action =====================

    def _score_to_action(
        self, weighted_score: float, aligned: bool, regime: Optional[Dict] = None
    ) -> Tuple[str, float]:
        """
        Map weighted score to trading action.

        Indian equity: 'buy' or 'sell' (exit) or 'hold'.
        No short-selling.
        """
        buy_threshold = 20
        sell_threshold = 18  # Used for exit signals

        if regime:
            regime_type = (regime.get("regime", "") or "").lower()
            if regime_type == "trending_down":
                sell_threshold = 18
                buy_threshold = 32
            elif regime_type == "trending_up":
                buy_threshold = 22
                sell_threshold = 32
            elif regime_type in ("volatile_directionless", "choppy"):
                buy_threshold = 30
                sell_threshold = 30

        if aligned:
            buy_threshold = max(12, buy_threshold - 2)
            sell_threshold = max(12, sell_threshold - 2)

        buy_high = buy_threshold + 15
        sell_high = sell_threshold + 15

        # Strong buy
        if weighted_score > buy_high and aligned:
            return "buy", 0.85

        # Standard buy
        if weighted_score > buy_threshold:
            conf = 0.65 if aligned else 0.55
            return "buy", conf

        # Sell (exit) signal — strong bearish score
        if weighted_score < -sell_high and aligned:
            return "sell", 0.85

        # Standard sell (exit)
        if weighted_score < -sell_threshold:
            conf = 0.65 if aligned else 0.55
            return "sell", conf

        return "hold", 0.3

    # ===================== Reason generation =====================

    def _generate_reason(
        self, weighted_score: float, aligned: bool, alignment_reason: str,
        quant_analysis: Dict, prophet_score: float = 0, regime: Optional[Dict] = None
    ) -> str:
        """Generate human-readable decision reason."""
        parts = []

        # Score summary
        if weighted_score > 0:
            parts.append(f"Bullish score: {weighted_score:.1f}")
        elif weighted_score < 0:
            parts.append(f"Bearish score: {weighted_score:.1f}")
        else:
            parts.append("Neutral score")

        # Alignment
        parts.append(f"Alignment: {alignment_reason}")

        # Prophet
        if prophet_score != 0:
            direction = "bullish" if prophet_score > 0 else "bearish"
            parts.append(f"ML prediction: {direction} ({prophet_score:+.1f})")

        # Regime
        if regime:
            parts.append(f"Market: {regime.get('regime', 'unknown')} (ADX: {regime.get('adx', 0):.1f})")

        return " | ".join(parts)
