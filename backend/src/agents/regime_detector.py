"""
Regime Detector — Market State Identification
==============================================
Identifies market regimes: trending_up, trending_down, choppy, volatile,
volatile_directionless. All comments and labels in English.
Adapted for Indian equity markets.

Core capabilities:
  1. ADX-based trend strength (with ta library or EMA proxy fallback)
  2. Bollinger Band width for volatility detection
  3. ATR percentage for risk level
  4. Trend Strength Score (TSS) — composite ADX + EMA alignment + MACD
  5. Choppy market analysis — squeeze detection, S/R, breakout probability
  6. Price position within recent range
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from enum import Enum
from loguru import logger


class MarketRegime(Enum):
    """Market regime classification."""
    TRENDING_UP = "trending_up"                      # Clear uptrend
    TRENDING_DOWN = "trending_down"                  # Clear downtrend
    CHOPPY = "choppy"                                # Range-bound (sideways)
    VOLATILE = "volatile"                            # High volatility (dangerous)
    VOLATILE_DIRECTIONLESS = "volatile_directionless"  # ADX high but no clear direction
    UNKNOWN = "unknown"                              # Cannot determine


class RegimeDetector:
    """
    Market Regime Detector

    Uses ADX, Bollinger Bands, ATR, and TSS to classify market state.
    """

    def __init__(
        self,
        adx_trend_threshold: float = 25.0,
        adx_choppy_threshold: float = 20.0,
        bb_width_volatile_ratio: float = 1.5,
        atr_high_threshold: float = 2.0,
    ):
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_choppy_threshold = adx_choppy_threshold
        self.bb_width_volatile_ratio = bb_width_volatile_ratio
        self.atr_high_threshold = atr_high_threshold

        # Check if ta library is available for proper ADX/BB/ATR
        try:
            from ta.trend import ADXIndicator          # noqa: F401
            from ta.volatility import BollingerBands, AverageTrueRange  # noqa: F401
            self._has_ta = True
        except ImportError:
            self._has_ta = False
            logger.info("'ta' library not installed — using proxy calculations")

    def detect_regime(self, df: pd.DataFrame) -> Dict:
        """
        Detect market regime.

        Args:
            df: OHLCV DataFrame (must contain at least 'close', 'high', 'low')

        Returns:
            Dict with regime, confidence, adx, bb_width_pct, atr_pct,
            trend_direction, reason, position, choppy_analysis
        """
        if df is None or df.empty or len(df) < 10:
            return {
                "regime": MarketRegime.UNKNOWN.value,
                "confidence": 0.0,
                "adx": 20.0,
                "bb_width_pct": 2.0,
                "atr_pct": 0.5,
                "trend_direction": "neutral",
                "reason": "Insufficient data for regime detection",
                "position": {"position_pct": 50.0, "location": "unknown"},
                "choppy_analysis": None,
            }

        # 1. Calculate ADX
        adx = self._get_or_calculate_adx(df)

        # 2. Calculate Bollinger Band width %
        bb_width_pct = self._calculate_bb_width_pct(df)

        # 3. Calculate ATR %
        atr_pct = self._calculate_atr_pct(df)

        # 4. Detect trend direction
        trend_direction = self._detect_trend_direction(df)

        # 5. Classify regime
        regime, confidence, reason = self._classify_regime(
            adx, bb_width_pct, atr_pct, trend_direction, df
        )

        # Sanity check: clip values to valid ranges, handle NaN
        def safe_clip(val, min_val, max_val, default=0.0):
            if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
                return default
            return max(min_val, min(max_val, float(val)))

        confidence = safe_clip(confidence, 0, 100, 50.0)
        adx = safe_clip(adx, 0, 100, 20.0)
        bb_width_pct = safe_clip(bb_width_pct, 0, 50, 2.0)
        atr_pct = safe_clip(atr_pct, 0, 20, 0.5)

        # 6. Choppy-specific analysis
        choppy_analysis = None
        if regime == MarketRegime.CHOPPY:
            choppy_analysis = self._analyze_choppy_market(df, bb_width_pct)

        return {
            "regime": regime.value,
            "confidence": confidence,
            "adx": adx,
            "bb_width_pct": bb_width_pct,
            "atr_pct": atr_pct,
            "trend_direction": trend_direction,
            "reason": reason,
            "position": self._calculate_price_position(df),
            "choppy_analysis": choppy_analysis,
        }

    # ===================== ADX =====================

    def _get_or_calculate_adx(self, df: pd.DataFrame) -> float:
        """Get or calculate ADX (Average Directional Index)."""
        # Use pre-computed column
        if "adx" in df.columns:
            val = df["adx"].iloc[-1]
            if not (np.isnan(val) or np.isinf(val)):
                return float(val)

        # Calculate with ta library
        if self._has_ta and {"high", "low", "close"}.issubset(df.columns) and len(df) >= 20:
            try:
                from ta.trend import ADXIndicator
                tail = df[["high", "low", "close"]].tail(200)
                adx = ADXIndicator(
                    high=tail["high"], low=tail["low"], close=tail["close"], window=14
                ).adx().iloc[-1]
                return float(adx)
            except Exception:
                pass

        # Proxy: EMA difference scaled to ADX-like range
        if "close" in df.columns and len(df) >= 26:
            close = df["close"]
            ema12 = close.ewm(span=12, adjust=False).mean().iloc[-1]
            ema26 = close.ewm(span=26, adjust=False).mean().iloc[-1]
            ema_diff = abs(ema12 - ema26)
            price = close.iloc[-1]
            if price > 0:
                adx_proxy = (ema_diff / price) * 100 * 10
                return adx_proxy

        return 20.0

    # ===================== Bollinger Bands =====================

    def _calculate_bb_width_pct(self, df: pd.DataFrame) -> float:
        """Bollinger Band width as percentage of middle band."""
        if {"bb_upper", "bb_lower", "bb_middle"}.issubset(df.columns):
            upper = df["bb_upper"].iloc[-1]
            lower = df["bb_lower"].iloc[-1]
            middle = df["bb_middle"].iloc[-1]
            if middle > 0:
                return ((upper - lower) / middle) * 100

        # Compute with ta library
        if self._has_ta and "close" in df.columns and len(df) >= 20:
            try:
                from ta.volatility import BollingerBands
                close = df["close"].tail(200)
                bb = BollingerBands(close=close, window=20, window_dev=2)
                upper = bb.bollinger_hband().iloc[-1]
                lower = bb.bollinger_lband().iloc[-1]
                middle = bb.bollinger_mavg().iloc[-1]
                if middle > 0:
                    return ((upper - lower) / middle) * 100
            except Exception:
                pass

        # Fallback: manual 20-period std
        if "close" in df.columns and len(df) >= 20:
            close = df["close"].tail(20)
            sma = close.mean()
            std = close.std()
            if sma > 0:
                return (4 * std / sma) * 100  # upper - lower ≈ 4 * std

        return 2.0

    # ===================== ATR =====================

    def _calculate_atr_pct(self, df: pd.DataFrame) -> float:
        """ATR as percentage of current price."""
        if "atr" in df.columns and "close" in df.columns:
            atr = df["atr"].iloc[-1]
            price = df["close"].iloc[-1]
            if price > 0 and not np.isnan(atr):
                return (atr / price) * 100

        # Compute with ta library
        if self._has_ta and {"high", "low", "close"}.issubset(df.columns) and len(df) >= 20:
            try:
                from ta.volatility import AverageTrueRange
                tail = df[["high", "low", "close"]].tail(200)
                atr = AverageTrueRange(
                    high=tail["high"], low=tail["low"], close=tail["close"], window=14
                ).average_true_range().iloc[-1]
                price = tail["close"].iloc[-1]
                if price > 0:
                    return (float(atr) / price) * 100
            except Exception:
                pass

        # Fallback: simple range-based proxy
        if {"high", "low", "close"}.issubset(df.columns) and len(df) >= 14:
            ranges = (df["high"].tail(14) - df["low"].tail(14)).mean()
            price = df["close"].iloc[-1]
            if price > 0:
                return (ranges / price) * 100

        return 0.5

    # ===================== Trend Direction =====================

    def _detect_trend_direction(self, df: pd.DataFrame) -> str:
        """Detect trend direction using SMA20/SMA50 alignment."""
        if {"sma_20", "sma_50"}.issubset(df.columns) and "close" in df.columns:
            sma20 = df["sma_20"].iloc[-1]
            sma50 = df["sma_50"].iloc[-1]
            price = df["close"].iloc[-1]
            if price > sma20 > sma50:
                return "up"
            elif price < sma20 < sma50:
                return "down"

        # Compute from raw close
        if "close" in df.columns and len(df) >= 50:
            close = df["close"].tail(200)
            sma20 = close.rolling(window=20).mean().iloc[-1]
            sma50 = close.rolling(window=50).mean().iloc[-1]
            price = close.iloc[-1]
            if price > sma20 > sma50:
                return "up"
            if price < sma20 < sma50:
                return "down"

        return "neutral"

    # ===================== Classification =====================

    def _classify_regime(
        self,
        adx: float,
        bb_width_pct: float,
        atr_pct: float,
        trend_direction: str,
        df: Optional[pd.DataFrame] = None,
    ) -> tuple:
        """
        Classify market regime using Trend Strength Score (TSS).

        TSS components:
          - ADX (0-100): Weight 40%
          - EMA Alignment (bool): Weight 30%
          - MACD Momentum (bool): Weight 30%

        Returns: (regime, confidence, reason)
        """
        # 1. High volatility (highest priority)
        if atr_pct > self.atr_high_threshold:
            return (
                MarketRegime.VOLATILE,
                80.0,
                f"High volatility market (ATR {atr_pct:.2f}% > {self.atr_high_threshold}%)",
            )

        # 2. Calculate TSS
        tss = 0
        tss_details = []

        # Component A: ADX
        if adx > 25:
            tss += 40
            tss_details.append("ADX>25(+40)")
        elif adx > 20:
            tss += 20
            tss_details.append("ADX>20(+20)")

        # Component B: EMA Alignment
        if trend_direction in ("up", "down"):
            tss += 30
            tss_details.append("EMA_Aligned(+30)")

        # Component C: MACD Momentum
        if df is not None and {"macd", "macd_signal"}.issubset(df.columns):
            macd = df["macd"].iloc[-1]
            signal = df["macd_signal"].iloc[-1]
            if (trend_direction == "up" and macd > signal > 0) or \
               (trend_direction == "down" and macd < signal < 0):
                tss += 30
                tss_details.append("MACD_Momentum(+30)")

        # 3. Classify based on TSS
        tss_str = ",".join(tss_details)
        if tss >= 70:  # Strong trend
            if trend_direction == "up":
                return (MarketRegime.TRENDING_UP, 85.0, f"Strong uptrend (TSS:{tss} — {tss_str})")
            elif trend_direction == "down":
                return (MarketRegime.TRENDING_DOWN, 85.0, f"Strong downtrend (TSS:{tss} — {tss_str})")

        elif tss >= 30:  # Weak trend
            if trend_direction == "up":
                return (MarketRegime.TRENDING_UP, 60.0, f"Weak uptrend (TSS:{tss} — {tss_str})")
            elif trend_direction == "down":
                return (MarketRegime.TRENDING_DOWN, 60.0, f"Weak downtrend (TSS:{tss} — {tss_str})")

        # 4. Fallback: Choppy
        if adx < self.adx_choppy_threshold:
            return (
                MarketRegime.CHOPPY,
                70.0,
                f"Range-bound market (ADX {adx:.1f} < {self.adx_choppy_threshold})",
            )

        # 5. ADX high but no alignment → Volatile Directionless
        return (
            MarketRegime.VOLATILE_DIRECTIONLESS,
            65.0,
            f"Directionless volatility (ADX {adx:.1f} but trend not aligned)",
        )

    # ===================== Price Position =====================

    def _calculate_price_position(self, df: pd.DataFrame, lookback: int = 50) -> Dict:
        """Price position within recent range (0-100)."""
        try:
            if len(df) < lookback:
                lookback = len(df)

            recent_high = df["high"].iloc[-lookback:].max()
            recent_low = df["low"].iloc[-lookback:].min()
            current_price = df["close"].iloc[-1]

            if recent_high == recent_low:
                position_pct = 50.0
            else:
                position_pct = ((current_price - recent_low) / (recent_high - recent_low)) * 100

            position_pct = max(0, min(100, position_pct))

            if position_pct <= 25:
                location = "low"
            elif position_pct >= 75:
                location = "high"
            else:
                location = "middle"

            return {"position_pct": position_pct, "location": location}

        except Exception:
            return {"position_pct": 50.0, "location": "unknown"}

    # ===================== Choppy Market Analysis =====================

    def _analyze_choppy_market(
        self, df: pd.DataFrame, current_bb_width: float, lookback: int = 20
    ) -> Dict:
        """
        Choppy market deep analysis.

        Provides:
          1. Squeeze detection (BB narrowing)
          2. Support / Resistance identification
          3. Breakout probability assessment
          4. Mean reversion signal
          5. Consolidation bar count
          6. Strategy hint
        """
        try:
            # 1. Squeeze Detection
            squeeze_active = False
            squeeze_intensity = 0.0

            if {"bb_upper", "bb_lower", "bb_middle"}.issubset(df.columns):
                bb_widths = (
                    (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"] * 100
                ).iloc[-lookback:]
                avg_width = bb_widths.mean()
                if avg_width > 0:
                    width_ratio = current_bb_width / avg_width
                    if width_ratio < 0.7:
                        squeeze_active = True
                        squeeze_intensity = (1 - width_ratio) * 100

            # 2. Support / Resistance
            recent_high = df["high"].iloc[-lookback:].max()
            recent_low = df["low"].iloc[-lookback:].min()
            current_price = df["close"].iloc[-1]

            range_pct = (
                ((recent_high - recent_low) / current_price) * 100
                if current_price > 0
                else 0
            )

            # 3. Price position & mean reversion signal
            position_pct = (
                ((current_price - recent_low) / (recent_high - recent_low) * 100)
                if (recent_high - recent_low) > 0
                else 50
            )

            if position_pct <= 20:
                mean_reversion_signal = "buy_dip"
            elif position_pct >= 80:
                mean_reversion_signal = "sell_rally"
            else:
                mean_reversion_signal = "neutral"

            # 4. Breakout probability
            breakout_probability = 0.0
            breakout_direction = "unknown"

            if squeeze_active:
                breakout_probability += squeeze_intensity * 0.5

                if position_pct >= 85:
                    breakout_probability += 30
                    breakout_direction = "up"
                elif position_pct <= 15:
                    breakout_probability += 30
                    breakout_direction = "down"
                else:
                    breakout_probability += 10

            # Volume surge detection
            if "volume" in df.columns:
                recent_vol = df["volume"].iloc[-5:].mean()
                avg_vol = df["volume"].iloc[-lookback:].mean()
                if avg_vol > 0 and recent_vol > avg_vol * 1.5:
                    breakout_probability += 20

            breakout_probability = min(100, breakout_probability)

            # 5. Consolidation bar count
            consolidation_bars = 0
            for i in range(1, min(50, len(df))):
                idx = -i
                bar_range = (
                    (df["high"].iloc[idx] - df["low"].iloc[idx]) / df["close"].iloc[idx] * 100
                )
                if bar_range < 1.5:  # < 1.5% range = consolidation
                    consolidation_bars += 1
                else:
                    break

            # 6. Strategy hint
            if squeeze_active and breakout_probability >= 60:
                if breakout_direction == "up":
                    strategy_hint = "SQUEEZE_BREAKOUT_LONG: Prepare for upside breakout, set alerts at resistance"
                elif breakout_direction == "down":
                    strategy_hint = "SQUEEZE_BREAKOUT_SHORT: Prepare for downside breakout, set alerts at support"
                else:
                    strategy_hint = "SQUEEZE_IMMINENT: Volatility expansion expected, wait for direction confirmation"
            elif mean_reversion_signal == "buy_dip":
                strategy_hint = "MEAN_REVERSION_LONG: Price near support, consider long with tight stop below support"
            elif mean_reversion_signal == "sell_rally":
                strategy_hint = "MEAN_REVERSION_SHORT: Price near resistance — in Indian equity, consider booking profits"
            else:
                strategy_hint = "RANGE_WAIT: No clear edge, wait for price to reach range extremes"

            return {
                "squeeze_active": squeeze_active,
                "squeeze_intensity": min(100, max(0, squeeze_intensity)),
                "range": {
                    "support": float(recent_low),
                    "resistance": float(recent_high),
                    "range_pct": min(20, max(0, range_pct)),
                },
                "breakout_probability": breakout_probability,
                "breakout_direction": breakout_direction,
                "mean_reversion_signal": mean_reversion_signal,
                "consolidation_bars": consolidation_bars,
                "strategy_hint": strategy_hint,
            }

        except Exception as e:
            logger.warning(f"Choppy market analysis error: {e}")
            return {
                "squeeze_active": False,
                "squeeze_intensity": 0,
                "range": {"support": 0, "resistance": 0, "range_pct": 0},
                "breakout_probability": 0,
                "breakout_direction": "unknown",
                "mean_reversion_signal": "neutral",
                "consolidation_bars": 0,
                "strategy_hint": "ANALYSIS_ERROR: Unable to analyze choppy market",
            }
