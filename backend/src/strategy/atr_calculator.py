"""
ATR-based Dynamic TP/SL Calculator
===================================

Calculates dynamic take profit and stop loss multipliers based on
Average True Range (ATR) to adapt to market volatility.

Mapping for Indian equities:
- Low volatility (ATR < 0.5%): 1.0x (conservative)
- Normal (0.5-2.0%): linear scale 1.0x-2.0x
- High volatility (ATR > 2.0%): 2.0x (aggressive)
"""

import pandas as pd
from typing import Dict


class ATRCalculator:
    """
    ATR-based calculator for dynamic TP/SL adjustment.
    Works with any DataFrame that has 'high', 'low', 'close' columns.
    """

    def __init__(self, period: int = 14):
        self.period = period

    def calculate_atr(self, df: pd.DataFrame) -> float:
        """Calculate Average True Range."""
        if len(df) < self.period:
            return 0.0

        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(self.period).mean().iloc[-1]
        return atr

    def calculate_atr_percentage(self, df: pd.DataFrame) -> float:
        """Calculate ATR as percentage of current price."""
        if len(df) < self.period:
            return 1.0

        atr = self.calculate_atr(df)
        current_price = df['close'].iloc[-1]

        if current_price == 0:
            return 1.0

        return (atr / current_price) * 100

    def calculate_multiplier(self, df: pd.DataFrame) -> float:
        """
        Calculate TP/SL multiplier based on ATR.
        
        ATR < 0.5%: 1.0x
        ATR 0.5-2.0%: linear 1.0x-2.0x
        ATR > 2.0%: 2.0x
        """
        atr_pct = self.calculate_atr_percentage(df)

        if atr_pct < 0.5:
            return 1.0
        elif atr_pct > 2.0:
            return 2.0
        else:
            return 1.0 + (atr_pct - 0.5) / 1.5

    def get_analysis(self, df: pd.DataFrame) -> Dict:
        """Get comprehensive ATR analysis."""
        if len(df) < self.period:
            return {
                'atr': 0.0,
                'atr_pct': 0.0,
                'multiplier': 1.0,
                'volatility': 'insufficient_data'
            }

        atr = self.calculate_atr(df)
        atr_pct = self.calculate_atr_percentage(df)
        multiplier = self.calculate_multiplier(df)

        if atr_pct < 0.5:
            volatility = 'low'
        elif atr_pct < 1.0:
            volatility = 'normal'
        elif atr_pct < 2.0:
            volatility = 'elevated'
        else:
            volatility = 'high'

        return {
            'atr': round(atr, 2),
            'atr_pct': round(atr_pct, 2),
            'multiplier': round(multiplier, 2),
            'volatility': volatility
        }
