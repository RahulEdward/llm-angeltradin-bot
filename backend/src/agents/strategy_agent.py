"""
Strategy Agent - The Strategist + The Critic (Combined)
Full reference-repo agent flow integrated:

1. QuantAnalyst: Multi-timeframe technical analysis with trend/oscillator scores,
   KDJ calculation, market trap detection
2. DecisionCore: Weighted voting mechanism with configurable signal weights,
   multi-period alignment, OvertradingGuard, dynamic trade parameters
3. PredictAgent: Rule-based probability prediction integration
4. RegimeDetector: Market state detection integration

Pipeline per symbol:
  MarketData → Regime Detection → Quant Analysis → Trap Detection →
  Predict (Prophet) → Weighted Voting → Overtrading Guard → Signal Output
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
import pandas as pd
import numpy as np

from .base import BaseAgent, AgentType, AgentMessage, MessageType
from .regime_detector import RegimeDetector
from .predict_agent import PredictAgent
from ..llm import LLMFactory, BaseLLMClient, TradingDecision


# ─── Signal Weights (from reference-repo DecisionCoreAgent) ───
@dataclass
class SignalWeight:
    trend_5m: float = 0.03
    trend_15m: float = 0.12
    trend_1h: float = 0.30
    oscillator_5m: float = 0.03
    oscillator_15m: float = 0.07
    oscillator_1h: float = 0.10
    prophet: float = 0.05
    sentiment: float = 0.25  # unused for now (no crypto funding/OI)
    llm_signal: float = 0.05


# ─── Overtrading Guard (from reference-repo) ───
@dataclass
class TradeRecord:
    symbol: str
    action: str
    timestamp: datetime
    pnl: float = 0.0


class OvertradingGuard:
    """Prevents frequent trading and consecutive loss spiraling."""
    MIN_CYCLES_SAME_SYMBOL = 4
    MAX_POSITIONS_6H = 3
    LOSS_STREAK_COOLDOWN = 6
    CONSECUTIVE_LOSS_THRESHOLD = 2

    def __init__(self):
        self.trade_history: List[TradeRecord] = []
        self.consecutive_losses = 0
        self.last_trade_cycle: Dict[str, int] = {}
        self.cooldown_until_cycle: int = 0

    def record_trade(self, symbol: str, action: str, pnl: float = 0.0, current_cycle: int = 0):
        self.trade_history.append(TradeRecord(symbol=symbol, action=action, timestamp=datetime.now(), pnl=pnl))
        self.last_trade_cycle[symbol] = current_cycle
        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.CONSECUTIVE_LOSS_THRESHOLD:
                self.cooldown_until_cycle = current_cycle + self.LOSS_STREAK_COOLDOWN
                logger.warning(f"OvertradingGuard: {self.consecutive_losses} consecutive losses, cooldown until cycle {self.cooldown_until_cycle}")
        else:
            self.consecutive_losses = 0

    def can_open(self, symbol: str, current_cycle: int) -> Tuple[bool, str]:
        if current_cycle < self.cooldown_until_cycle:
            remaining = self.cooldown_until_cycle - current_cycle
            return False, f"Loss cooldown: {remaining} cycles remaining"
        if symbol in self.last_trade_cycle:
            since = current_cycle - self.last_trade_cycle[symbol]
            if since < self.MIN_CYCLES_SAME_SYMBOL:
                return False, f"{symbol} traded too recently ({since}/{self.MIN_CYCLES_SAME_SYMBOL} cycles)"
        six_h_ago = datetime.now().timestamp() - 6 * 3600
        recent = sum(1 for t in self.trade_history if t.timestamp.timestamp() > six_h_ago)
        if recent >= self.MAX_POSITIONS_6H:
            return False, f"Max positions in 6h reached ({recent}/{self.MAX_POSITIONS_6H})"
        return True, "OK"


class StrategyAgent(BaseAgent):
    """
    Strategy Agent - Full reference-repo flow:
    QuantAnalyst + DecisionCore + PredictAgent + RegimeDetector combined.
    """

    def __init__(self, name: str = "StrategyAgent", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, AgentType.STRATEGY, config or {})
        self.use_llm = self.config.get("use_llm", True)
        self.min_confidence = self.config.get("min_confidence", 0.6)
        self._llm: Optional[BaseLLMClient] = None
        self._current_data: Dict[str, Any] = {}

        # Sub-components (reference-repo agents)
        self.regime_detector = RegimeDetector()
        self.predict_agent = PredictAgent()
        self.overtrading_guard = OvertradingGuard()
        self.weights = SignalWeight()
        self._cycle_count = 0

    async def initialize(self) -> bool:
        if self.use_llm:
            try:
                self._llm = LLMFactory.get_or_create()
                if self._llm:
                    logger.info(f"StrategyAgent LLM ready: {self._llm.model}")
                else:
                    logger.warning("LLM not available - rule-based strategy")
                    self.use_llm = False
            except Exception as e:
                logger.warning(f"LLM init failed: {e}")
                self.use_llm = False
        logger.info(f"StrategyAgent initialized (LLM: {'ON' if self.use_llm else 'OFF'}) "
                     f"| Regime + Prophet + WeightedVoting + OvertradingGuard")
        return True

    async def process_cycle(self) -> List[AgentMessage]:
        messages = []
        self._cycle_count += 1

        for msg in self.get_pending_messages():
            if msg.type == MessageType.MARKET_UPDATE:
                self._current_data = msg.payload

        if not self._current_data:
            return messages

        quotes = self._current_data.get("quotes", {})
        indicators = self._current_data.get("indicators", {})
        source = self._current_data.get("source", "unknown")
        historical = self._current_data.get("historical", {})

        symbol_names = [q.get("symbol", k.split(":")[-1]) for k, q in quotes.items()]
        messages.append(AgentMessage(
            type=MessageType.STATE_UPDATE, source_agent="StrategyAgent",
            payload={"status": "analyzing", "message": f"🔍 Analyzing {len(quotes)} symbols ({source})"}
        ))

        for symbol_key, quote in quotes.items():
            sym_indicators = indicators.get(symbol_key, {})
            symbol = quote.get("symbol", symbol_key.split(":")[-1])
            ltp = quote.get("ltp", 0)
            if ltp <= 0:
                continue

            # ─── Step 1: Regime Detection ───
            regime = self._detect_regime(sym_indicators)
            regime_str = regime.get("regime", "unknown")

            # ─── Step 2: Quant Analysis (trend + oscillator scores per timeframe) ───
            quant = self._quant_analysis(sym_indicators, quote)

            # ─── Step 3: Trap Detection ───
            traps = self._detect_traps(sym_indicators, quote)

            # ─── Step 4: Prophet Prediction ───
            predict_result = await self._run_prediction(sym_indicators, quant)

            # ─── Step 5: Weighted Voting (DecisionCore) ───
            vote = self._weighted_vote(quant, predict_result, regime)

            # ─── Step 6: Multi-period alignment ───
            aligned, align_reason = self._check_alignment(quant)

            # ─── Step 7: Score to action ───
            action, base_conf = self._score_to_action(vote["weighted_score"], aligned, regime)

            # ─── Step 8: Regime-based filtering ───
            if regime_str in ("choppy", "volatile_directionless"):
                action, base_conf, align_reason = self._choppy_strategy(quant, regime, base_conf, align_reason)

            # ─── Step 9: Overtrading Guard ───
            if action in ("BUY", "SELL"):
                can_trade, guard_reason = self.overtrading_guard.can_open(symbol, self._cycle_count)
                if not can_trade:
                    messages.append(AgentMessage(
                        type=MessageType.STATE_UPDATE, source_agent="StrategyAgent",
                        payload={"status": "guard", "message": f"🛡️ {symbol}: {guard_reason}"}
                    ))
                    action = "HOLD"
                    base_conf = 0.1

            # ─── Step 10: Trap filtering ───
            if action == "BUY" and traps.get("bull_trap_risk"):
                action, base_conf = "HOLD", 0.1
                align_reason += " | Bull trap detected"
            if action == "BUY" and traps.get("weak_rebound"):
                base_conf *= 0.5
                if base_conf < 0.5:
                    action = "HOLD"
            if action == "BUY" and traps.get("volume_divergence"):
                base_conf *= 0.7
            if action == "BUY" and traps.get("accumulation"):
                base_conf = min(base_conf * 1.2, 0.95)
            if action == "BUY" and traps.get("panic_bottom"):
                base_conf = min(base_conf * 1.3, 0.95)
            if action == "SELL" and traps.get("panic_bottom"):
                action, base_conf = "HOLD", 0.1
            if action == "SELL" and traps.get("fomo_top"):
                base_conf = min(base_conf * 1.3, 0.95)
            if action == "BUY" and traps.get("fomo_top"):
                action, base_conf = "HOLD", 0.1

            # ─── Step 11: Confidence calibration with regime + position ───
            position = regime.get("position", {})
            final_conf = self._calibrate_confidence(base_conf * 100, regime, position, aligned) / 100

            # ─── Step 12: Dynamic trade params ───
            trade_params = self._dynamic_trade_params(regime, position, final_conf, action, ltp, sym_indicators)

            # ─── Report ───
            prophet_sig = predict_result.signal if predict_result else "N/A"
            filter_msg = (
                f"📊 {symbol}: Regime={regime_str} | Vote={vote['weighted_score']:.1f} | "
                f"Aligned={'✅' if aligned else '❌'} | Prophet={prophet_sig} | "
                f"Action={action} Conf={final_conf:.0%}"
            )
            if traps.get("bull_trap_risk") or traps.get("volume_divergence") or traps.get("panic_bottom"):
                trap_flags = [k for k, v in traps.items() if v and k != "details"]
                filter_msg += f" | Traps: {','.join(trap_flags)}"

            messages.append(AgentMessage(
                type=MessageType.STATE_UPDATE, source_agent="StrategyAgent",
                payload={"status": "analysis", "message": filter_msg}
            ))

            if action == "HOLD" or final_conf < self.min_confidence:
                continue

            # ─── LLM Enhancement (optional) ───
            if self.use_llm and self._llm and action in ("BUY", "SELL"):
                try:
                    llm_decision = await self._llm.analyze_market(quote, sym_indicators)
                    if llm_decision.action == action:
                        final_conf = min((final_conf * 0.6 + llm_decision.confidence * 0.4), 0.95)
                    elif llm_decision.action == "HOLD":
                        final_conf *= 0.7
                    else:
                        final_conf *= 0.4
                        action = "HOLD"
                    if llm_decision.stop_loss and llm_decision.stop_loss > 0:
                        trade_params["stop_loss"] = llm_decision.stop_loss
                    if llm_decision.take_profit and llm_decision.take_profit > 0:
                        trade_params["take_profit"] = llm_decision.take_profit
                except Exception as e:
                    logger.warning(f"LLM analysis failed for {symbol}: {e}")

            if action == "HOLD" or final_conf < self.min_confidence:
                continue

            # ─── Emit SIGNAL ───
            reasoning = (
                f"Regime:{regime_str} | Score:{vote['weighted_score']:.1f} | "
                f"Aligned:{aligned} | Prophet:{prophet_sig} | {align_reason[:80]}"
            )
            messages.append(AgentMessage(
                type=MessageType.STATE_UPDATE, source_agent="StrategyAgent",
                payload={"status": "signal", "message": (
                    f"🧠 {action} {symbol} | Conf: {final_conf:.0%} | "
                    f"Entry: ₹{ltp:.2f} | SL: ₹{trade_params['stop_loss']:.2f} | "
                    f"TP: ₹{trade_params['take_profit']:.2f}"
                )}
            ))
            messages.append(AgentMessage(
                type=MessageType.SIGNAL, source_agent=self.name, priority=2,
                payload={
                    "action": action, "symbol": symbol,
                    "exchange": quote.get("exchange", "NSE"),
                    "confidence": final_conf, "reasoning": reasoning,
                    "entry_price": ltp,
                    "stop_loss": trade_params["stop_loss"],
                    "take_profit": trade_params["take_profit"],
                    "risk_level": "low" if final_conf > 0.75 else "medium",
                    "regime": regime, "position": position, "traps": traps,
                    "vote_details": vote.get("details", {}),
                    "source": "llm+rules" if self.use_llm and self._llm else "rule_based",
                }
            ))

        return messages

    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.type == MessageType.MARKET_UPDATE:
            self._current_data = message.payload
        return None

    async def shutdown(self) -> None:
        logger.info("StrategyAgent shutdown")

    # ─── Quant Analysis (reference-repo QuantAnalystAgent) ───

    def _quant_analysis(self, indicators: Dict, quote: Dict) -> Dict:
        """Multi-timeframe trend + oscillator scoring."""
        result = {}
        for tf in ("1h", "15m", "5m"):
            tf_data = indicators.get(tf, {})
            result[f"trend_{tf}"] = self._trend_score(tf_data, quote.get("ltp", 0))
            result[f"osc_{tf}"] = self._oscillator_score(tf_data)
        return result

    def _trend_score(self, tf: Dict, ltp: float) -> float:
        """Trend score -100 to +100 from EMA alignment."""
        if not tf:
            return 0
        ema9 = tf.get("ema_9", ltp)
        ema21 = tf.get("ema_21", ltp)
        ema50 = tf.get("ema_50", ltp) or ltp
        if ltp > ema9 > ema21:
            score = 60
            if ema21 > ema50:
                score = 80
        elif ltp < ema9 < ema21:
            score = -60
            if ema21 < ema50:
                score = -80
        elif ltp > ema21:
            score = 20
        elif ltp < ema21:
            score = -20
        else:
            score = 0
        return score

    def _oscillator_score(self, tf: Dict) -> float:
        """Oscillator score -100 to +100 from RSI + KDJ."""
        if not tf:
            return 0
        score = 0
        rsi = tf.get("rsi_14", 50)
        if rsi < 30:
            score += 40
        elif rsi > 70:
            score -= 40
        elif rsi < 40:
            score += 15
        elif rsi > 60:
            score -= 15

        # KDJ from OHLC if available
        kdj_j = tf.get("kdj_j")
        if kdj_j is not None:
            if kdj_j < 20:
                score += 30
            elif kdj_j > 80:
                score -= 30
        return max(-100, min(100, score))

    # ─── Regime Detection ───

    def _detect_regime(self, indicators: Dict) -> Dict:
        """Run regime detection on 1h data."""
        tf_1h = indicators.get("1h", {})
        if not tf_1h:
            return {"regime": "unknown", "confidence": 30, "adx": 20, "atr_pct": 0.5,
                    "trend_direction": "neutral", "reason": "No 1h data",
                    "position": {"position_pct": 50, "location": "unknown"}}

        # Build a minimal DataFrame for regime detector
        # We use the indicator values directly since we don't have raw OHLCV here
        # Create a synthetic single-row DF with the values we have
        try:
            close = tf_1h.get("ema_21", 0)  # approximate
            ema9 = tf_1h.get("ema_9", close)
            ema21 = tf_1h.get("ema_21", close)
            bb_upper = tf_1h.get("bb_upper", close * 1.02)
            bb_lower = tf_1h.get("bb_lower", close * 0.98)
            bb_mid = tf_1h.get("bb_middle", close)
            atr = tf_1h.get("atr_14", close * 0.01)
            rsi = tf_1h.get("rsi_14", 50)

            # Calculate regime metrics directly
            adx_proxy = (abs(ema9 - ema21) / close * 100 * 10) if close > 0 else 20
            bb_width = ((bb_upper - bb_lower) / bb_mid * 100) if bb_mid > 0 else 2
            atr_pct = (atr / close * 100) if close > 0 else 0.5

            # Trend direction
            if close > 0 and ema9 > ema21:
                trend_dir = "up"
            elif close > 0 and ema9 < ema21:
                trend_dir = "down"
            else:
                trend_dir = "neutral"

            # TSS
            tss = 0
            if adx_proxy > 25:
                tss += 40
            elif adx_proxy > 20:
                tss += 20
            if trend_dir in ("up", "down"):
                tss += 30
            macd_h = tf_1h.get("macd_histogram", 0)
            if (trend_dir == "up" and macd_h > 0) or (trend_dir == "down" and macd_h < 0):
                tss += 30

            # Classify
            if atr_pct > 2.5:
                regime = "volatile"
                conf = 80
                reason = f"High volatility (ATR {atr_pct:.2f}%)"
            elif tss >= 70:
                regime = f"trending_{trend_dir}" if trend_dir != "neutral" else "unknown"
                conf = 85
                reason = f"Strong trend (TSS:{tss})"
            elif tss >= 30:
                regime = f"trending_{trend_dir}" if trend_dir != "neutral" else "choppy"
                conf = 60
                reason = f"Weak trend (TSS:{tss})"
            elif adx_proxy < 20:
                regime = "choppy"
                conf = 70
                reason = f"Choppy (ADX {adx_proxy:.1f})"
            else:
                regime = "volatile_directionless"
                conf = 65
                reason = f"Directionless (ADX {adx_proxy:.1f})"

            # Price position
            position = {"position_pct": 50.0, "location": "middle"}
            if bb_upper > bb_lower:
                pos_pct = ((close - bb_lower) / (bb_upper - bb_lower)) * 100
                pos_pct = max(0, min(100, pos_pct))
                loc = "low" if pos_pct <= 25 else ("high" if pos_pct >= 75 else "middle")
                position = {"position_pct": round(pos_pct, 1), "location": loc}

            return {
                "regime": regime, "confidence": conf, "adx": round(adx_proxy, 1),
                "atr_pct": round(atr_pct, 2), "bb_width_pct": round(bb_width, 2),
                "trend_direction": trend_dir, "reason": reason, "position": position,
            }
        except Exception as e:
            logger.warning(f"Regime detection error: {e}")
            return {"regime": "unknown", "confidence": 30, "adx": 20, "atr_pct": 0.5,
                    "trend_direction": "neutral", "reason": str(e),
                    "position": {"position_pct": 50, "location": "unknown"}}

    # ─── Trap Detection (reference-repo QuantAnalystAgent) ───

    def _detect_traps(self, indicators: Dict, quote: Dict) -> Dict:
        """Detect market traps from indicator data."""
        traps = {
            "bull_trap_risk": False, "weak_rebound": False,
            "volume_divergence": False, "accumulation": False,
            "panic_bottom": False, "fomo_top": False, "details": {},
        }
        tf_1h = indicators.get("1h", {})
        if not tf_1h:
            return traps

        rsi = tf_1h.get("rsi_14", 50)
        bb_upper = tf_1h.get("bb_upper", 0)
        bb_lower = tf_1h.get("bb_lower", 0)
        ltp = quote.get("ltp", 0)
        rel_vol = tf_1h.get("relative_volume", 1.0)

        # Panic bottom: price below BB lower + RSI oversold + high volume
        if ltp < bb_lower and rsi < 25 and rel_vol > 2.0:
            traps["panic_bottom"] = True

        # FOMO top: price above BB upper + RSI overbought + high volume
        if ltp > bb_upper and rsi > 75 and rel_vol > 2.0:
            traps["fomo_top"] = True

        # Volume divergence: near high but low volume
        if ltp > bb_upper * 0.98 and rel_vol < 0.7:
            traps["volume_divergence"] = True

        # Weak rebound: RSI still low + low volume (after a drop)
        if 30 < rsi < 40 and rel_vol < 0.8:
            traps["weak_rebound"] = True

        return traps

    # ─── Prophet Prediction ───

    async def _run_prediction(self, indicators: Dict, quant: Dict) -> Optional[Any]:
        """Run PredictAgent with extracted features."""
        try:
            tf_15m = indicators.get("15m", {})
            features = {
                "trend_score": quant.get("trend_1h", 0),
                "rsi": tf_15m.get("rsi_14", 50),
                "bb_position": 50,  # approximate
                "ema_cross_strength": 0,
                "volume_ratio": tf_15m.get("relative_volume", 1.0),
                "macd_histogram": tf_15m.get("macd_histogram", 0),
            }
            # Calculate BB position
            bb_mid = tf_15m.get("bb_middle", 0)
            bb_upper = tf_15m.get("bb_upper", 0)
            bb_lower = tf_15m.get("bb_lower", 0)
            ltp_approx = tf_15m.get("ema_9", bb_mid)
            if bb_upper > bb_lower and bb_upper > 0:
                features["bb_position"] = ((ltp_approx - bb_lower) / (bb_upper - bb_lower)) * 100

            # EMA cross strength
            ema9 = tf_15m.get("ema_9", 0)
            ema21 = tf_15m.get("ema_21", 0)
            if ema21 > 0:
                features["ema_cross_strength"] = (ema9 - ema21) / ema21 * 100

            return await self.predict_agent.predict(features)
        except Exception as e:
            logger.debug(f"Prediction error: {e}")
            return None

    # ─── Weighted Voting (reference-repo DecisionCoreAgent) ───

    def _weighted_vote(self, quant: Dict, predict_result, regime: Dict) -> Dict:
        """Weighted voting across all signal sources."""
        w = self.weights
        scores = {
            "trend_5m": quant.get("trend_5m", 0),
            "trend_15m": quant.get("trend_15m", 0),
            "trend_1h": quant.get("trend_1h", 0),
            "osc_5m": quant.get("osc_5m", 0),
            "osc_15m": quant.get("osc_15m", 0),
            "osc_1h": quant.get("osc_1h", 0),
            "prophet": 0,
        }

        if predict_result:
            scores["prophet"] = (predict_result.probability_up - 0.5) * 200

        weighted = (
            scores["trend_5m"] * w.trend_5m +
            scores["trend_15m"] * w.trend_15m +
            scores["trend_1h"] * w.trend_1h +
            scores["osc_5m"] * w.oscillator_5m +
            scores["osc_15m"] * w.oscillator_15m +
            scores["osc_1h"] * w.oscillator_1h +
            scores["prophet"] * w.prophet
        )

        details = {k: scores[k] for k in scores}
        details["weighted_score"] = weighted

        return {"weighted_score": weighted, "details": details, "scores": scores}

    # ─── Multi-period Alignment ───

    def _check_alignment(self, quant: Dict) -> Tuple[bool, str]:
        s1h = quant.get("trend_1h", 0)
        s15m = quant.get("trend_15m", 0)
        s5m = quant.get("trend_5m", 0)

        signs = [
            1 if s1h >= 25 else (-1 if s1h <= -25 else 0),
            1 if s15m >= 18 else (-1 if s15m <= -18 else 0),
            1 if s5m >= 12 else (-1 if s5m <= -12 else 0),
        ]

        if signs[0] == signs[1] == signs[2] and signs[0] != 0:
            d = "bullish" if signs[0] > 0 else "bearish"
            return True, f"3-period {d} alignment"
        if signs[0] == signs[1] and signs[0] != 0:
            d = "bullish" if signs[0] > 0 else "bearish"
            return True, f"1h+15m {d} alignment"
        return False, f"Divergence (1h:{signs[0]}, 15m:{signs[1]}, 5m:{signs[2]})"

    # ─── Score to Action ───

    def _score_to_action(self, score: float, aligned: bool, regime: Dict) -> Tuple[str, float]:
        long_th = 20
        short_th = 18
        regime_type = regime.get("regime", "").lower()

        if regime_type == "trending_down":
            short_th, long_th = 18, 32
        elif regime_type == "trending_up":
            long_th, short_th = 22, 32
        elif regime_type in ("choppy", "volatile_directionless"):
            long_th = short_th = 30

        if aligned:
            long_th = max(12, long_th - 2)
            short_th = max(12, short_th - 2)

        if score > long_th + 15 and aligned:
            return "BUY", 0.85
        if score < -(short_th + 15) and aligned:
            return "SELL", 0.85
        if score > long_th:
            return "BUY", min(0.55 + (score - long_th) * 0.01, 0.75)
        if score < -short_th:
            return "SELL", min(0.55 + (abs(score) - short_th) * 0.01, 0.75)
        return "HOLD", abs(score) / 100

    # ─── Choppy Market Strategy ───

    def _choppy_strategy(self, quant: Dict, regime: Dict, base_conf: float, reason: str) -> Tuple[str, float, str]:
        """Mean reversion strategy for choppy markets."""
        rsi_15m = 50
        for tf in ("15m", "5m"):
            # Get RSI from quant oscillator scores indirectly
            osc = quant.get(f"osc_{tf}", 0)
            if osc != 0:
                # Approximate RSI from oscillator score
                if osc > 30:
                    rsi_15m = 30  # oversold signal
                elif osc < -30:
                    rsi_15m = 70  # overbought signal
                break

        pos_pct = regime.get("position", {}).get("position_pct", 50)

        if rsi_15m < 35 and pos_pct < 40:
            return "BUY", 0.65, f"Choppy mean-reversion BUY (RSI~{rsi_15m}, pos={pos_pct:.0f}%)"
        if rsi_15m > 65 and pos_pct > 60:
            return "SELL", 0.65, f"Choppy mean-reversion SELL (RSI~{rsi_15m}, pos={pos_pct:.0f}%)"
        return "HOLD", 0.3, f"Choppy - no edge (pos={pos_pct:.0f}%)"

    # ─── Confidence Calibration ───

    def _calibrate_confidence(self, conf: float, regime: Dict, position: Dict, aligned: bool) -> float:
        if aligned:
            conf += 15
        r = regime.get("regime", "")
        if r in ("trending_up", "trending_down"):
            conf += 10
        if r == "choppy":
            conf -= 25
        if r == "volatile":
            conf -= 20
        loc = position.get("location", "middle")
        if loc == "middle":
            conf -= 15
        return max(5.0, min(100.0, conf))

    # ─── Dynamic Trade Parameters ───

    def _dynamic_trade_params(self, regime: Dict, position: Dict, conf: float,
                              action: str, ltp: float, indicators: Dict) -> Dict:
        """Calculate SL/TP dynamically based on regime and ATR."""
        atr = indicators.get("5m", {}).get("atr_14", ltp * 0.015)
        if not atr or atr <= 0:
            atr = ltp * 0.015

        sl_mult = 1.5
        tp_mult = 3.0

        r = regime.get("regime", "")
        if "volatile" in r:
            sl_mult = 2.0
            tp_mult = 3.5
        elif r in ("trending_up", "trending_down"):
            tp_mult = 4.0
        elif r in ("choppy", "volatile_directionless"):
            sl_mult = 1.0
            tp_mult = 1.5

        if action == "BUY":
            sl = ltp - sl_mult * atr
            tp = ltp + tp_mult * atr
        elif action == "SELL":
            sl = ltp + sl_mult * atr
            tp = ltp - tp_mult * atr
        else:
            sl = ltp * 0.98
            tp = ltp * 1.04

        return {"stop_loss": round(sl, 2), "take_profit": round(tp, 2)}
