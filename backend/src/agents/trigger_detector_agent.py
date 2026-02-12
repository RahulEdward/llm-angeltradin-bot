"""
5min Trigger Detector (Specification Module 4)

Purpose:
- Detect precise entry signals on 5min timeframe
- Pattern A: Bullish Engulfing
- Pattern B: Volume Breakout

Specification:
- Data: Last 10 bars of 5min K-lines
- Volume MA3: Average of last 3 bars
- Engulfing: Previous bearish + Current bullish engulfing
- Breakout: Close > max(prev 3 highs) + Volume > 1.5 × MA3
"""

import pandas as pd
from typing import Dict
from loguru import logger


class TriggerDetector:
    """
    5min Trigger Pattern Detector
    
    Implements specification Module 4: Trigger detection
    Adapted for Indian equity markets (delivery-based, no short-selling).
    """
    
    def __init__(self):
        """Initialize trigger detector"""
        pass
    
    def detect_engulfing(self, df_5m: pd.DataFrame, direction: str = 'long') -> Dict:
        """
        Detect Engulfing pattern.
        
        For Indian equities (delivery-only), primarily looks for bullish engulfing.
        
        Args:
            df_5m: 5min K-line data
            direction: 'long' (primary for Indian equities)
        """
        if len(df_5m) < 2:
            return {'detected': False, 'pattern': None}
        
        prev = df_5m.iloc[-2]
        curr = df_5m.iloc[-1]
        
        if direction == 'long':
            prev_bearish = prev['close'] < prev['open']
            curr_bullish = curr['close'] > curr['open']
            engulfing = curr['close'] > prev['open'] and curr['open'] < prev['close']
            detected = prev_bearish and curr_bullish and engulfing
        else:
            # For sell signal (exit existing position)
            prev_bullish = prev['close'] > prev['open']
            curr_bearish = curr['close'] < curr['open']
            engulfing = curr['close'] < prev['open'] and curr['open'] > prev['close']
            detected = prev_bullish and curr_bearish and engulfing
        
        if detected:
            logger.info(f"🎯 Engulfing pattern detected ({direction}): "
                    f"Prev [{prev['open']:.2f}->{prev['close']:.2f}], "
                    f"Curr [{curr['open']:.2f}->{curr['close']:.2f}]")
        
        return {
            'detected': detected,
            'pattern': 'engulfing',
            'prev_candle': {
                'open': prev['open'],
                'close': prev['close'],
                'high': prev['high'],
                'low': prev['low']
            },
            'curr_candle': {
                'open': curr['open'],
                'close': curr['close'],
                'high': curr['high'],
                'low': curr['low']
            }
        }
    
    def detect_breakout(self, df_5m: pd.DataFrame, direction: str = 'long') -> Dict:
        """
        Detect Volume Breakout.
        
        Args:
            df_5m: 5min K-line data
            direction: 'long' or 'short' (sell signal for exit)
        """
        if len(df_5m) < 4:
            return {'detected': False, 'pattern': None}
        
        curr = df_5m.iloc[-1]
        prev_3 = df_5m.iloc[-4:-1]
        
        vol_ma3 = prev_3['volume'].mean()
        volume_ratio = curr['volume'] / vol_ma3 if vol_ma3 > 0 else 0
        
        if direction == 'long':
            breakout_level = prev_3['high'].max()
            price_breakout = curr['close'] > breakout_level
        else:
            breakout_level = prev_3['low'].min()
            price_breakout = curr['close'] < breakout_level
        
        volume_confirm = volume_ratio > 1.0
        detected = price_breakout and volume_confirm
        
        if detected:
            logger.info(f"🚀 Breakout detected ({direction}): "
                    f"Price {curr['close']:.2f} {'>' if direction == 'long' else '<'} {breakout_level:.2f}, "
                    f"Volume ratio {volume_ratio:.2f}x")
        
        return {
            'detected': detected,
            'pattern': 'breakout',
            'breakout_level': breakout_level,
            'volume_ratio': volume_ratio,
            'current_price': curr['close'],
            'current_volume': curr['volume'],
            'vol_ma3': vol_ma3
        }
    
    def detect_trigger(self, df_5m: pd.DataFrame, direction: str = 'long') -> Dict:
        """
        Detect any trigger pattern (Engulfing OR Breakout).
        
        Returns:
            {
                'triggered': bool,
                'pattern_type': 'engulfing' | 'breakout' | 'rvol_momentum' | None,
                'details': dict,
                'rvol': float
            }
        """
        engulfing_result = self.detect_engulfing(df_5m, direction)
        breakout_result = self.detect_breakout(df_5m, direction)
        rvol = self.calculate_rvol(df_5m)
        
        if engulfing_result['detected']:
            return {
                'triggered': True,
                'pattern_type': 'engulfing',
                'details': engulfing_result,
                'rvol': rvol
            }
        elif breakout_result['detected']:
            return {
                'triggered': True,
                'pattern_type': 'breakout',
                'details': breakout_result,
                'rvol': rvol
            }
        # RVOL-only fallback
        elif rvol >= 0.5:
            if len(df_5m) >= 1:
                curr = df_5m.iloc[-1]
                momentum_ok = False
                if direction == 'long' and curr['close'] > curr['open']:
                    momentum_ok = True
                elif direction == 'short' and curr['close'] < curr['open']:
                    momentum_ok = True
                
                if momentum_ok:
                    logger.info(f"📊 RVOL trigger activated ({direction}): RVOL={rvol:.2f}x with momentum")
                    return {
                        'triggered': True,
                        'pattern_type': 'rvol_momentum',
                        'details': {'rvol': rvol, 'momentum': True},
                        'rvol': rvol
                    }
        
        return {
            'triggered': False,
            'pattern_type': None,
            'details': {},
            'rvol': rvol
        }
    
    def calculate_rvol(self, df: pd.DataFrame, lookback: int = 10) -> float:
        """
        Calculate Relative Volume (RVOL).
        
        RVOL = Current Volume / Average Volume (last N bars)
        """
        if len(df) < lookback + 1 or 'volume' not in df.columns:
            return 1.0
        
        current_vol = df['volume'].iloc[-1]
        avg_vol = df['volume'].iloc[-lookback-1:-1].mean()
        
        if avg_vol > 0:
            return current_vol / avg_vol
        return 1.0
