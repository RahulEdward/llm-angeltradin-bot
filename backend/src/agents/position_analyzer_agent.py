"""
Position Analyzer Agent
========================
Calculates current price position within recent range.
Filters low-quality trades based on price location.

Adapted for Indian equity markets (delivery-based, long-only focus).
"""

import pandas as pd
from typing import Dict, Tuple
from enum import Enum


class PriceLocation(Enum):
    """Price location classification"""
    SUPPORT = "support"        # Near support (0-20%)
    LOWER = "lower"            # Lower zone (20-40%)
    MIDDLE = "middle"          # Mid range (40-60%)
    UPPER = "upper"            # Upper zone (60-80%)
    RESISTANCE = "resistance"  # Near resistance (80-100%)


class PositionQuality(Enum):
    """Position quality rating"""
    EXCELLENT = "excellent"    # At support/resistance
    GOOD = "good"              # Near support/resistance
    POOR = "poor"              # Near middle
    TERRIBLE = "terrible"      # Dead center


class PositionAnalyzer:
    """
    Price Position Analyzer
    
    Core functions:
    1. Calculate price position percentage within recent range
    2. Classify position quality
    3. Provide entry suggestions (allow buy/sell)
    
    For Indian equities (delivery-only):
    - Buy signals: prefer lower positions (0-40%)
    - Sell signals (exit): prefer upper positions (60-100%)
    - Middle zone (40-60%): avoid new positions
    """
    
    def __init__(self, 
                 lookback_4h: int = 48,    # 4h range (48 x 5min candles)
                 lookback_1d: int = 288):  # 1d range (288 x 5min candles)
        self.lookback_4h = lookback_4h
        self.lookback_1d = lookback_1d
        
    def analyze_position(self, 
                        df: pd.DataFrame, 
                        current_price: float,
                        timeframe: str = '5m') -> Dict:
        """
        Analyze price position within recent range.
        
        Args:
            df: K-line data (must contain 'high' and 'low' columns)
            current_price: Current price
            timeframe: Timeframe for lookback determination
            
        Returns:
            Dict with range_high, range_low, position_pct, location,
            quality, allow_long, allow_short, reason
        """
        # Determine lookback
        if timeframe == '5m':
            lookback = self.lookback_4h
        elif timeframe == '15m':
            lookback = self.lookback_4h // 3
        elif timeframe == '1h':
            lookback = self.lookback_4h // 12
        else:
            lookback = self.lookback_4h
        
        lookback = min(lookback, len(df))
        
        recent_data = df.tail(lookback)
        range_high = recent_data['high'].max()
        range_low = recent_data['low'].min()
        range_size = range_high - range_low
        
        if range_size == 0:
            position_pct = 50.0
        else:
            position_pct = ((current_price - range_low) / range_size) * 100
            position_pct = max(0, min(100, position_pct))
        
        location = self._classify_location(position_pct)
        quality = self._classify_quality(position_pct)
        allow_long, allow_short = self._check_allow_trade(position_pct, location)
        reason = self._generate_reason(position_pct, location, quality, range_high, range_low)
        
        return {
            'range_high': range_high,
            'range_low': range_low,
            'range_size': range_size,
            'position_pct': position_pct,
            'location': location.value,
            'quality': quality.value,
            'allow_long': allow_long,
            'allow_short': allow_short,
            'reason': reason
        }
    
    def _classify_location(self, position_pct: float) -> PriceLocation:
        if position_pct <= 20:
            return PriceLocation.SUPPORT
        elif position_pct <= 40:
            return PriceLocation.LOWER
        elif position_pct <= 60:
            return PriceLocation.MIDDLE
        elif position_pct <= 80:
            return PriceLocation.UPPER
        else:
            return PriceLocation.RESISTANCE
    
    def _classify_quality(self, position_pct: float) -> PositionQuality:
        if position_pct <= 15 or position_pct >= 85:
            return PositionQuality.EXCELLENT
        elif position_pct <= 30 or position_pct >= 70:
            return PositionQuality.GOOD
        elif 45 <= position_pct <= 55:
            return PositionQuality.TERRIBLE
        else:
            return PositionQuality.POOR
    
    def _check_allow_trade(self, 
                          position_pct: float, 
                          location: PriceLocation) -> Tuple[bool, bool]:
        """
        Check if trade is allowed.
        
        For Indian equities (delivery-only):
        - Buy: only in lower zone (0-40%)
        - Sell (exit): only in upper zone (60-100%)
        - Middle (40-60%): avoid
        """
        if 40 <= position_pct <= 60:
            return False, False
        
        allow_long = position_pct < 60
        allow_short = position_pct > 40  # For exit signals
        
        return allow_long, allow_short
    
    def _generate_reason(self, 
                        position_pct: float,
                        location: PriceLocation,
                        quality: PositionQuality,
                        range_high: float,
                        range_low: float) -> str:
        location_desc = {
            PriceLocation.SUPPORT: "near support",
            PriceLocation.LOWER: "lower zone",
            PriceLocation.MIDDLE: "mid range",
            PriceLocation.UPPER: "upper zone",
            PriceLocation.RESISTANCE: "near resistance"
        }
        
        quality_desc = {
            PositionQuality.EXCELLENT: "excellent",
            PositionQuality.GOOD: "good",
            PositionQuality.POOR: "poor",
            PositionQuality.TERRIBLE: "terrible"
        }
        
        reason = f"Price position: {position_pct:.1f}% ({location_desc[location]}), "
        reason += f"Quality: {quality_desc[quality]}, "
        reason += f"Range: ₹{range_low:.2f} - ₹{range_high:.2f}"
        
        return reason
