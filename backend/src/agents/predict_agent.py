"""
Predict Agent - The Prophet
===========================
Rule-based probability prediction (0-1 scale) for Indian equity markets.
Supports future ML model integration (LightGBM / sklearn).

Scoring approach:
  1. Weighted feature scoring — 13 configurable feature weights
  2. Momentum acceleration — detects acceleration/deceleration in price movement
  3. Trend sustainability — evaluates whether the current trend can continue
  4. ML model stub — placeholder for trained model inference

Confidence is capped at 70% for rule-based, 90% for ML-based predictions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger
import numpy as np


# ============================================
# Feature Weights — configurable scoring
# ============================================
FEATURE_WEIGHTS: Dict[str, float] = {
    # Trend indicators (total ~0.35)
    "trend_score":        0.15,
    "ema_cross_strength": 0.10,
    "macd_histogram":     0.10,

    # Oscillators (total ~0.25)
    "rsi":                0.12,
    "bb_position":        0.08,
    "stoch_k":            0.05,

    # Volume (total ~0.15)
    "volume_ratio":       0.10,
    "volume_trend":       0.05,

    # Momentum (total ~0.15)
    "momentum_accel":     0.08,
    "price_roc":          0.07,

    # Sustainability (total ~0.10)
    "trend_sustain":      0.05,
    "atr_ratio":          0.03,
    "candle_strength":    0.02,
}


@dataclass
class PredictResult:
    """Prediction result with rich metadata."""
    probability_up: float = 0.5
    probability_down: float = 0.5
    confidence: float = 0.0
    factors: Dict[str, float] = field(default_factory=dict)
    model_type: str = "rule_based"       # "rule_based" or "ml_lightgbm"
    horizon: str = "5m"                  # prediction horizon
    timestamp: str = ""
    feature_importance: Dict[str, float] = field(default_factory=dict)

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
            "model_type": self.model_type,
            "horizon": self.horizon,
            "feature_importance": self.feature_importance,
        }


class PredictAgent:
    """
    The Prophet — Rule-based + ML-ready probability prediction.

    Scores features using configurable weights and outputs probability
    of price going up (0-1). Adapted for Indian equity markets.
    """

    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    MAX_RULE_CONFIDENCE = 0.70   # Cap for rule-based predictions
    MAX_ML_CONFIDENCE = 0.90     # Cap for ML predictions

    def __init__(self, model_path: Optional[str] = None):
        self.history: List[PredictResult] = []
        self.model = None
        self.model_path = model_path
        self.weights = FEATURE_WEIGHTS.copy()

        # Statistics tracking
        self._stats = {
            "total_predictions": 0,
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "avg_confidence": 0.0,
            "high_confidence_count": 0,   # confidence > 0.6
        }

        # Try loading ML model
        if model_path:
            self._load_model(model_path)

        mode = "ML" if self.model else "rule-based"
        logger.info(f"PredictAgent (The Prophet) initialized — {mode} mode")

    # ===================== Public API =====================

    async def predict(
        self,
        features: Dict[str, float],
        horizon: str = "5m",
    ) -> PredictResult:
        """Predict price direction from indicator features."""
        clean = self._preprocess(features)

        # Try ML first, fallback to rules
        if self.model is not None:
            result = self._predict_with_ml(clean)
        else:
            result = self._predict_rules(clean)

        result.horizon = horizon
        result.timestamp = datetime.now().isoformat()

        # Update history
        self.history.append(result)
        if len(self.history) > 500:
            self.history = self.history[-500:]

        # Update statistics
        self._update_stats(result)

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """Return prediction statistics summary."""
        return {
            **self._stats,
            "history_length": len(self.history),
            "model_loaded": self.model is not None,
            "recent_bias": self._calc_recent_bias(),
        }

    # ===================== Preprocessing =====================

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
            "macd_histogram": 0.0, "stoch_k": 50.0, "volume_trend": 0.0,
            "momentum_accel": 0.0, "price_roc": 0.0,
            "trend_sustain": 0.0, "atr_ratio": 1.0, "candle_strength": 0.0,
        }
        return defaults.get(key, 0.0)

    # ===================== Rule-based prediction =====================

    def _predict_rules(self, f: Dict[str, float]) -> PredictResult:
        bullish = 0.0
        bearish = 0.0
        factors = {}
        importance = {}

        # 1. Trend score (-100 to +100)
        trend = f.get("trend_score", 0)
        w = self.weights.get("trend_score", 0.15)
        if trend >= 40:
            bullish += w
            factors["trend_strong_bull"] = w
        elif trend >= 20:
            bullish += w * 0.5
            factors["trend_bull"] = w * 0.5
        elif trend <= -40:
            bearish += w
            factors["trend_strong_bear"] = -w
        elif trend <= -20:
            bearish += w * 0.5
            factors["trend_bear"] = -w * 0.5
        importance["trend_score"] = w

        # 2. RSI
        rsi = f.get("rsi", 50)
        w = self.weights.get("rsi", 0.12)
        if rsi < self.RSI_OVERSOLD:
            bullish += w
            factors["rsi_oversold"] = w
        elif rsi < 40:
            bullish += w * 0.5
            factors["rsi_low"] = w * 0.5
        elif rsi > self.RSI_OVERBOUGHT:
            bearish += w
            factors["rsi_overbought"] = -w
        elif rsi > 60:
            bearish += w * 0.5
            factors["rsi_high"] = -w * 0.5
        importance["rsi"] = w

        # 3. BB position (0-100)
        bb_pos = f.get("bb_position", 50)
        w = self.weights.get("bb_position", 0.08)
        if bb_pos < 20:
            bullish += w
            factors["bb_low"] = w
        elif bb_pos > 80:
            bearish += w
            factors["bb_high"] = -w
        importance["bb_position"] = w

        # 4. EMA cross strength
        ema_str = f.get("ema_cross_strength", 0)
        w = self.weights.get("ema_cross_strength", 0.10)
        if ema_str > 0.5:
            bullish += w
            factors["ema_bull"] = w
        elif ema_str < -0.5:
            bearish += w
            factors["ema_bear"] = -w
        importance["ema_cross"] = w

        # 5. Volume ratio — confirms existing direction
        vol = f.get("volume_ratio", 1.0)
        w = self.weights.get("volume_ratio", 0.10)
        if vol > 1.5:
            if bullish > bearish:
                bullish += w * 0.5
                factors["vol_confirm_up"] = w * 0.5
            elif bearish > bullish:
                bearish += w * 0.5
                factors["vol_confirm_down"] = -w * 0.5
        importance["volume_ratio"] = w

        # 6. MACD histogram
        macd_h = f.get("macd_histogram", 0)
        w = self.weights.get("macd_histogram", 0.10)
        if macd_h > 0:
            bullish += w * 0.5
            factors["macd_bull"] = w * 0.5
        elif macd_h < 0:
            bearish += w * 0.5
            factors["macd_bear"] = -w * 0.5
        importance["macd_histogram"] = w

        # 7. Stochastic K
        stoch = f.get("stoch_k", 50)
        w = self.weights.get("stoch_k", 0.05)
        if stoch < 20:
            bullish += w
            factors["stoch_oversold"] = w
        elif stoch > 80:
            bearish += w
            factors["stoch_overbought"] = -w
        importance["stoch_k"] = w

        # 8. Momentum acceleration
        mom_accel = f.get("momentum_accel", 0)
        w = self.weights.get("momentum_accel", 0.08)
        if mom_accel > 0.3:
            bullish += w
            factors["momentum_accelerating_up"] = w
        elif mom_accel < -0.3:
            bearish += w
            factors["momentum_accelerating_down"] = -w
        importance["momentum_accel"] = w

        # 9. Price rate of change
        roc = f.get("price_roc", 0)
        w = self.weights.get("price_roc", 0.07)
        if roc > 1.0:
            bullish += w * 0.7
            factors["price_rising"] = w * 0.7
        elif roc < -1.0:
            bearish += w * 0.7
            factors["price_falling"] = -w * 0.7
        importance["price_roc"] = w

        # 10. Trend sustainability
        sustain = f.get("trend_sustain", 0)
        w = self.weights.get("trend_sustain", 0.05)
        if sustain > 0.5:
            if bullish > bearish:
                bullish += w
                factors["trend_sustainable_up"] = w
            else:
                bearish += w
                factors["trend_sustainable_down"] = -w
        importance["trend_sustain"] = w

        # Calculate probability
        total = bullish + bearish
        if total == 0:
            prob_up = 0.5
        else:
            net = bullish - bearish
            prob_up = 0.5 + (net / 2)
            prob_up = max(0.0, min(1.0, prob_up))

        # Confidence capped at 70% for rule-based
        confidence = min(self.MAX_RULE_CONFIDENCE, total / 0.5)

        return PredictResult(
            probability_up=round(prob_up, 4),
            probability_down=round(1.0 - prob_up, 4),
            confidence=round(confidence, 4),
            factors=factors,
            model_type="rule_based",
            feature_importance=importance,
        )

    # ===================== ML prediction stub =====================

    def _load_model(self, path: str):
        """Load a trained ML model (LightGBM or sklearn)."""
        try:
            import joblib
            self.model = joblib.load(path)
            logger.info(f"ML model loaded from {path}")
        except ImportError:
            logger.warning("joblib not installed — ML model loading skipped")
            self.model = None
        except FileNotFoundError:
            logger.warning(f"Model file not found: {path} — using rule-based mode")
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            self.model = None

    def _predict_with_ml(self, f: Dict[str, float]) -> PredictResult:
        """Run ML model inference. Returns PredictResult."""
        try:
            # Build feature vector in consistent order
            feature_names = sorted(self.weights.keys())
            feature_vec = np.array([[f.get(name, 0.0) for name in feature_names]])

            # Predict probability
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(feature_vec)[0]
                prob_up = float(proba[1]) if len(proba) > 1 else float(proba[0])
            else:
                raw = float(self.model.predict(feature_vec)[0])
                prob_up = max(0.0, min(1.0, raw))

            # Feature importance from model
            importance = {}
            if hasattr(self.model, "feature_importances_"):
                for i, name in enumerate(feature_names):
                    importance[name] = float(self.model.feature_importances_[i])

            confidence = min(self.MAX_ML_CONFIDENCE, abs(prob_up - 0.5) * 2)

            return PredictResult(
                probability_up=round(prob_up, 4),
                probability_down=round(1.0 - prob_up, 4),
                confidence=round(confidence, 4),
                factors={"ml_prediction": prob_up},
                model_type="ml_lightgbm",
                feature_importance=importance,
            )
        except Exception as e:
            logger.error(f"ML prediction failed, falling back to rules: {e}")
            return self._predict_rules(f)

    # ===================== Statistics =====================

    def _update_stats(self, result: PredictResult):
        s = self._stats
        s["total_predictions"] += 1
        sig = result.signal
        if "bullish" in sig:
            s["bullish_count"] += 1
        elif "bearish" in sig:
            s["bearish_count"] += 1
        else:
            s["neutral_count"] += 1
        if result.confidence > 0.6:
            s["high_confidence_count"] += 1

        # Running average confidence
        n = s["total_predictions"]
        s["avg_confidence"] = round(
            s["avg_confidence"] * (n - 1) / n + result.confidence / n, 4
        )

    def _calc_recent_bias(self, window: int = 20) -> str:
        """Determine recent prediction bias from last N predictions."""
        if len(self.history) < 5:
            return "insufficient_data"
        recent = self.history[-window:]
        avg_up = sum(r.probability_up for r in recent) / len(recent)
        if avg_up > 0.6:
            return "bullish_bias"
        elif avg_up < 0.4:
            return "bearish_bias"
        return "neutral"
