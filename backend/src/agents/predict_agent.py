"""
Predict Agent - The Prophet
Rule-based probability prediction (0-1 scale) for Indian markets.
Adapted from reference-repo PredictAgent.

No ML model dependency - pure rule-based scoring with feature weights.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger
import numpy as np


@dataclass
class PredictResult:
    """Prediction result."""
    probability_up: float = 0.5
    probability_down: float = 0.5
    confidence: float = 0.0
    factors: Dict[str, float] = field(default_factory=dict)

    @property
    def signal(self) -> str:
        if self.probability_up > 0.65:
            return "strong_bullish"
        elif self.probability_up > 0.55:
            return "bullish"
        elif self.probability_down > 0.65:
            return "strong_bearish"
        elif self.probability_down > 0.55:
            return "bearish"
        return "neutral"

    def to_dict(self) -> Dict:
        return {
            "probability_up": self.probability_up,
            "probability_down": self.probability_down,
            "confidence": self.confidence,
            "signal": self.signal,
            "factors": self.factors,
        }


class PredictAgent:
    """
    The Prophet - Rule-based probability prediction.
    
    Scores features and outputs probability of price going up (0-1).
    Adapted for Indian equity markets (no leverage/futures concepts).
    """

    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70

    def __init__(self):
        self.history: List[PredictResult] = []
        logger.info("PredictAgent (The Prophet) initialized - rule-based mode")

    async def predict(self, features: Dict[str, float]) -> PredictResult:
        """Predict price direction from indicator features."""
        clean = self._preprocess(features)
        result = self._predict_rules(clean)
        self.history.append(result)
        if len(self.history) > 500:
            self.history = self.history[-500:]
        return result

    def _preprocess(self, features: Dict) -> Dict[str, float]:
        out = {}
        for k, v in features.items():
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                out[k] = self._default(k)
            else:
                try:
                    out[k] = float(v)
                except (TypeError, ValueError):
                    out[k] = 0.0
        return out

    def _default(self, key: str) -> float:
        defaults = {
            "rsi": 50.0, "bb_position": 50.0, "trend_score": 0.0,
            "ema_cross_strength": 0.0, "volume_ratio": 1.0,
        }
        return defaults.get(key, 0.0)

    def _predict_rules(self, f: Dict[str, float]) -> PredictResult:
        bullish = 0.0
        bearish = 0.0
        factors = {}

        # 1. Trend score (-100 to +100 from QuantAnalyst)
        trend = f.get("trend_score", 0)
        if trend >= 40:
            bullish += 0.15
            factors["trend_strong_bull"] = 0.15
        elif trend >= 20:
            bullish += 0.08
            factors["trend_bull"] = 0.08
        elif trend <= -40:
            bearish += 0.15
            factors["trend_strong_bear"] = -0.15
        elif trend <= -20:
            bearish += 0.08
            factors["trend_bear"] = -0.08

        # 2. RSI
        rsi = f.get("rsi", 50)
        if rsi < self.RSI_OVERSOLD:
            bullish += 0.12
            factors["rsi_oversold"] = 0.12
        elif rsi < 40:
            bullish += 0.06
            factors["rsi_low"] = 0.06
        elif rsi > self.RSI_OVERBOUGHT:
            bearish += 0.12
            factors["rsi_overbought"] = -0.12
        elif rsi > 60:
            bearish += 0.06
            factors["rsi_high"] = -0.06

        # 3. BB position (0-100)
        bb_pos = f.get("bb_position", 50)
        if bb_pos < 20:
            bullish += 0.10
            factors["bb_low"] = 0.10
        elif bb_pos > 80:
            bearish += 0.10
            factors["bb_high"] = -0.10

        # 4. EMA cross strength
        ema_str = f.get("ema_cross_strength", 0)
        if ema_str > 0.5:
            bullish += 0.08
            factors["ema_bull"] = 0.08
        elif ema_str < -0.5:
            bearish += 0.08
            factors["ema_bear"] = -0.08

        # 5. Volume ratio
        vol = f.get("volume_ratio", 1.0)
        if vol > 1.5:
            if bullish > bearish:
                bullish += 0.05
                factors["vol_confirm_up"] = 0.05
            elif bearish > bullish:
                bearish += 0.05
                factors["vol_confirm_down"] = -0.05

        # 6. MACD histogram
        macd_h = f.get("macd_histogram", 0)
        if macd_h > 0:
            bullish += 0.05
            factors["macd_bull"] = 0.05
        elif macd_h < 0:
            bearish += 0.05
            factors["macd_bear"] = -0.05

        # Calculate probability
        total = bullish + bearish
        if total == 0:
            prob_up = 0.5
        else:
            net = bullish - bearish
            prob_up = 0.5 + (net / 2)
            prob_up = max(0.0, min(1.0, prob_up))

        # Confidence capped at 70% for rule-based
        confidence = min(0.70, total / 0.5)

        return PredictResult(
            probability_up=round(prob_up, 4),
            probability_down=round(1.0 - prob_up, 4),
            confidence=round(confidence, 4),
            factors=factors,
        )
