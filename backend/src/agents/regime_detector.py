"""
Regime Detector Agent - Market State Detection
Adapted from reference-repo for Indian markets (Angel One / NSE)

Detects: trending_up, trending_down, choppy, volatile, volatile_directionless
Uses: ADX (proxy), Bollinger Band width, ATR%, Trend Strength Score (TSS)
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
from enum import Enum
from loguru import logger


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    CHOPPY = "choppy"
    VOLATILE = "volatile"
    VOLATILE_DIRECTIONLESS = "volatile_directionless"
    UNKNOWN = "unknown"


class RegimeDetector:
    """
    Market Regime Detector adapted for Indian equity markets.
    
    Uses lightweight calculations (no ta library dependency):
    - ADX proxy via EMA divergence
    - Bollinger Band width %
    - ATR %
    - Trend Strength Score (TSS)
    """

    def __init__(
        self,
        adx_trend_threshold: float = 25.0,
        adx_choppy_threshold: float = 20.0,
        atr_high_threshold: float = 2.5,  # Indian stocks can be more volatile
    ):
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_choppy_threshold = adx_choppy_threshold
        self.atr_high_threshold = atr_high_threshold

    def detect_regime(self, df: pd.DataFrame) -> Dict:
        """Detect market regime from OHLCV DataFrame."""
        if df is None or len(df) < 20:
            return {
                "regime": MarketRegime.UNKNOWN.value,
                "confidence": 30.0,
                "adx": 20.0,
                "bb_width_pct": 2.0,
                "atr_pct": 0.5,
                "trend_direction": "neutral",
                "reason": "Insufficient data",
                "position": {"position_pct": 50.0, "location": "unknown"},
            }

        adx = self._calculate_adx_proxy(df)
        bb_width_pct = self._calculate_bb_width_pct(df)
        atr_pct = self._calculate_atr_pct(df)
        trend_direction = self._detect_trend_direction(df)

        regime, confidence, reason = self._classify_regime(
            adx, bb_width_pct, atr_pct, trend_direction, df
        )

        # Sanitize
        adx = self._safe_clip(adx, 0, 100, 20.0)
        bb_width_pct = self._safe_clip(bb_width_pct, 0, 50, 2.0)
        atr_pct = self._safe_clip(atr_pct, 0, 20, 0.5)
        confidence = self._safe_clip(confidence, 0, 100, 50.0)

        position = self._calculate_price_position(df)

        return {
            "regime": regime.value,
            "confidence": confidence,
            "adx": adx,
            "bb_width_pct": bb_width_pct,
            "atr_pct": atr_pct,
            "trend_direction": trend_direction,
            "reason": reason,
            "position": position,
        }

    def _safe_clip(self, val, min_val, max_val, default=0.0):
        if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
            return default
        return max(min_val, min(max_val, float(val)))

    def _calculate_adx_proxy(self, df: pd.DataFrame) -> float:
        """ADX proxy using EMA divergence (no ta library needed)."""
        if len(df) < 26:
            return 20.0
        close = df["close"]
        ema12 = close.ewm(span=12, adjust=False).mean().iloc[-1]
        ema26 = close.ewm(span=26, adjust=False).mean().iloc[-1]
        price = close.iloc[-1]
        if price <= 0:
            return 20.0
        adx_proxy = (abs(ema12 - ema26) / price) * 100 * 10
        return float(adx_proxy)

    def _calculate_bb_width_pct(self, df: pd.DataFrame) -> float:
        """Bollinger Band width as % of middle band."""
        if len(df) < 20:
            return 2.0
        close = df["close"]
        sma20 = close.rolling(20).mean().iloc[-1]
        std20 = close.rolling(20).std().iloc[-1]
        if sma20 <= 0 or pd.isna(std20):
            return 2.0
        upper = sma20 + 2 * std20
        lower = sma20 - 2 * std20
        return float(((upper - lower) / sma20) * 100)

    def _calculate_atr_pct(self, df: pd.DataFrame) -> float:
        """ATR as % of current price."""
        if len(df) < 15:
            return 0.5
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        price = df["close"].iloc[-1]
        if price <= 0 or pd.isna(atr):
            return 0.5
        return float((atr / price) * 100)

    def _detect_trend_direction(self, df: pd.DataFrame) -> str:
        if len(df) < 50:
            return "neutral"
        close = df["close"]
        sma20 = close.rolling(20).mean().iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1]
        price = close.iloc[-1]
        if price > sma20 > sma50:
            return "up"
        if price < sma20 < sma50:
            return "down"
        return "neutral"

    def _classify_regime(self, adx, bb_width_pct, atr_pct, trend_direction, df) -> tuple:
        # High volatility check (highest priority)
        if atr_pct > self.atr_high_threshold:
            return (MarketRegime.VOLATILE, 80.0, f"High volatility (ATR {atr_pct:.2f}%)")

        # TSS: Trend Strength Score
        tss = 0
        tss_parts = []

        if adx > 25:
            tss += 40
            tss_parts.append("ADX>25(+40)")
        elif adx > 20:
            tss += 20
            tss_parts.append("ADX>20(+20)")

        if trend_direction in ("up", "down"):
            tss += 30
            tss_parts.append("EMA_Aligned(+30)")

        # MACD momentum check
        if len(df) >= 26:
            close = df["close"]
            ema12 = close.ewm(span=12).mean().iloc[-1]
            ema26 = close.ewm(span=26).mean().iloc[-1]
            macd = ema12 - ema26
            signal = (close.ewm(span=12).mean() - close.ewm(span=26).mean()).ewm(span=9).mean().iloc[-1]
            if (trend_direction == "up" and macd > signal > 0) or \
               (trend_direction == "down" and macd < signal < 0):
                tss += 30
                tss_parts.append("MACD_Momentum(+30)")

        tss_str = ",".join(tss_parts)

        if tss >= 70:
            if trend_direction == "up":
                return (MarketRegime.TRENDING_UP, 85.0, f"Strong uptrend (TSS:{tss} - {tss_str})")
            if trend_direction == "down":
                return (MarketRegime.TRENDING_DOWN, 85.0, f"Strong downtrend (TSS:{tss} - {tss_str})")

        if tss >= 30:
            if trend_direction == "up":
                return (MarketRegime.TRENDING_UP, 60.0, f"Weak uptrend (TSS:{tss} - {tss_str})")
            if trend_direction == "down":
                return (MarketRegime.TRENDING_DOWN, 60.0, f"Weak downtrend (TSS:{tss} - {tss_str})")

        if adx < self.adx_choppy_threshold:
            return (MarketRegime.CHOPPY, 70.0, f"Choppy market (ADX {adx:.1f})")

        return (MarketRegime.VOLATILE_DIRECTIONLESS, 65.0, f"Directionless (ADX {adx:.1f} but no alignment)")

    def _calculate_price_position(self, df: pd.DataFrame, lookback: int = 50) -> Dict:
        """Price position in recent range (0-100%)."""
        try:
            lb = min(lookback, len(df))
            recent_high = df["high"].iloc[-lb:].max()
            recent_low = df["low"].iloc[-lb:].min()
            price = df["close"].iloc[-1]
            if recent_high == recent_low:
                return {"position_pct": 50.0, "location": "middle"}
            pct = ((price - recent_low) / (recent_high - recent_low)) * 100
            pct = max(0, min(100, pct))
            if pct <= 25:
                loc = "low"
            elif pct >= 75:
                loc = "high"
            else:
                loc = "middle"
            return {"position_pct": round(pct, 1), "location": loc}
        except Exception:
            return {"position_pct": 50.0, "location": "unknown"}
