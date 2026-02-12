"""
Technical Feature Engineering
==============================

Builds advanced features from base technical indicators for:
1. Rule-based strategy decisions
2. ML model training
3. LLM context enrichment

Design principles:
- Input: DataFrame with base technical indicators (SMA, EMA, RSI, MACD, BB, ATR, etc.)
- Output: DataFrame with 50+ engineered features
- All features have clear financial meaning
- No data leakage (no future data used)

Adapted for Indian equities:
- Uses loguru for logging
- English feature descriptions
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from loguru import logger


class TechnicalFeatureEngineer:
    """Technical feature engineering from base indicators."""

    FEATURE_VERSION = 'v1.0'

    def __init__(self):
        self.feature_count = 0
        self.feature_names = []

    def build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build advanced features from a DataFrame with base technical indicators.
        
        Assumes columns like: close, high, low, open, volume,
        sma_20, sma_50, ema_12, ema_26, rsi, macd, macd_signal,
        bb_upper, bb_lower, bb_width, atr, vwap, obv, volume_sma, etc.
        
        Features:
        1. Price position (8)
        2. Trend strength (10)
        3. Momentum (8)
        4. Volatility (8)
        5. Volume (8)
        6. Composite (8)
        """
        logger.info(f"Starting feature engineering: original columns={len(df.columns)}")

        df_features = df.copy()

        df_features = self._build_price_position_features(df_features)
        df_features = self._build_trend_strength_features(df_features)
        df_features = self._build_momentum_features(df_features)
        df_features = self._build_volatility_features(df_features)
        df_features = self._build_volume_features(df_features)
        df_features = self._build_composite_features(df_features)

        new_features = set(df_features.columns) - set(df.columns)
        self.feature_count = len(new_features)
        self.feature_names = sorted(list(new_features))

        logger.info(
            f"Feature engineering complete: new_features={self.feature_count}, "
            f"total_columns={len(df_features.columns)}"
        )

        df_features.attrs['feature_version'] = self.FEATURE_VERSION
        df_features.attrs['feature_count'] = self.feature_count
        df_features.attrs['feature_names'] = self.feature_names

        return df_features

    def _build_price_position_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Price position relative to moving averages, Bollinger Bands, VWAP."""
        if 'sma_20' in df.columns:
            df['price_to_sma20_pct'] = ((df['close'] - df['sma_20']) / df['sma_20'] * 100)
        if 'sma_50' in df.columns:
            df['price_to_sma50_pct'] = ((df['close'] - df['sma_50']) / df['sma_50'] * 100)
        if 'ema_12' in df.columns:
            df['price_to_ema12_pct'] = ((df['close'] - df['ema_12']) / df['ema_12'] * 100)
        if 'ema_26' in df.columns:
            df['price_to_ema26_pct'] = ((df['close'] - df['ema_26']) / df['ema_26'] * 100)

        if 'bb_upper' in df.columns and 'bb_lower' in df.columns:
            df['bb_position'] = np.where(
                (df['bb_upper'] - df['bb_lower']) > 0,
                (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower']) * 100,
                50
            )

        if 'vwap' in df.columns:
            df['price_to_vwap_pct'] = np.where(
                df['vwap'] > 0,
                (df['close'] - df['vwap']) / df['vwap'] * 100,
                0
            )

        df['price_to_recent_high_pct'] = (
            (df['close'] - df['high'].rolling(20).max()) /
            df['high'].rolling(20).max() * 100
        )
        df['price_to_recent_low_pct'] = (
            (df['close'] - df['low'].rolling(20).min()) /
            df['low'].rolling(20).min() * 100
        )

        return df

    def _build_trend_strength_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Trend strength: EMA/SMA cross strength, MACD momentum, slope."""
        if 'ema_12' in df.columns and 'ema_26' in df.columns:
            df['ema_cross_strength'] = (df['ema_12'] - df['ema_26']) / df['close'] * 100
        if 'sma_20' in df.columns and 'sma_50' in df.columns:
            df['sma_cross_strength'] = (df['sma_20'] - df['sma_50']) / df['close'] * 100

        if 'macd' in df.columns:
            df['macd_momentum_5'] = df['macd'] - df['macd'].shift(5)
            df['macd_momentum_10'] = df['macd'] - df['macd'].shift(10)

        if 'ema_cross_strength' in df.columns and 'sma_cross_strength' in df.columns:
            df['trend_alignment'] = np.where(
                (df['ema_cross_strength'] > 0) & (df['sma_cross_strength'] > 0), 1,
                np.where(
                    (df['ema_cross_strength'] < 0) & (df['sma_cross_strength'] < 0), -1, 0
                )
            )

        def calc_slope(series):
            if len(series) < 2:
                return 0
            x = np.arange(len(series))
            try:
                slope = np.polyfit(x, series, 1)[0]
                return slope / series.iloc[-1] * 100 if series.iloc[-1] != 0 else 0
            except Exception:
                return 0

        df['price_slope_5'] = df['close'].rolling(5).apply(calc_slope, raw=False)
        df['price_slope_10'] = df['close'].rolling(10).apply(calc_slope, raw=False)
        df['price_slope_20'] = df['close'].rolling(20).apply(calc_slope, raw=False)

        df['directional_strength'] = (
            df['close'].diff().rolling(14).apply(
                lambda x: (x > 0).sum() / len(x) * 100 if len(x) > 0 else 50,
                raw=False
            )
        )

        return df

    def _build_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Momentum: RSI momentum, multi-period returns, acceleration."""
        if 'rsi' in df.columns:
            df['rsi_momentum_5'] = df['rsi'] - df['rsi'].shift(5)
            df['rsi_momentum_10'] = df['rsi'] - df['rsi'].shift(10)

            df['rsi_zone'] = pd.cut(
                df['rsi'],
                bins=[0, 30, 40, 60, 70, 100],
                labels=['oversold', 'weak', 'neutral', 'strong', 'overbought']
            )
            df['rsi_zone_numeric'] = pd.cut(
                df['rsi'],
                bins=[0, 30, 40, 60, 70, 100],
                labels=[-2, -1, 0, 1, 2]
            ).astype(float)

        df['return_1'] = df['close'].pct_change(1) * 100
        df['return_5'] = df['close'].pct_change(5) * 100
        df['return_10'] = df['close'].pct_change(10) * 100
        df['return_20'] = df['close'].pct_change(20) * 100

        df['momentum_acceleration'] = df['return_5'] - df['return_5'].shift(5)

        return df

    def _build_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Volatility: ATR normalized, BB width change, historical vol."""
        if 'atr' in df.columns:
            df['atr_normalized'] = df['atr'] / df['close'] * 100

        if 'bb_width' in df.columns:
            df['bb_width_change'] = df['bb_width'] - df['bb_width'].shift(5)
            df['bb_width_pct_change'] = df['bb_width'].pct_change(5) * 100

        df['volatility_5'] = df['close'].pct_change().rolling(5).std() * 100 * np.sqrt(5)
        df['volatility_10'] = df['close'].pct_change().rolling(10).std() * 100 * np.sqrt(10)
        df['volatility_20'] = df['close'].pct_change().rolling(20).std() * 100 * np.sqrt(20)

        if 'high_low_range' in df.columns:
            df['hl_range_ma5'] = df['high_low_range'].rolling(5).mean()
            df['hl_range_expansion'] = df['high_low_range'] / df['hl_range_ma5']

        return df

    def _build_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Volume: trends, acceleration, price-volume relationship."""
        if 'volume_sma' in df.columns:
            df['volume_trend_5'] = df['volume'].rolling(5).mean() / df['volume_sma']
            df['volume_trend_10'] = df['volume'].rolling(10).mean() / df['volume_sma']

        df['volume_change_pct'] = df['volume'].pct_change() * 100
        df['volume_acceleration'] = df['volume_change_pct'] - df['volume_change_pct'].shift(5)

        df['price_volume_trend'] = (
            (df['volume'] * np.sign(df['close'].diff())).rolling(20).sum()
        )

        if 'obv' in df.columns:
            df['obv_ma20'] = df['obv'].rolling(20).mean()
            df['obv_trend'] = np.where(
                df['obv_ma20'] != 0,
                (df['obv'] - df['obv_ma20']) / abs(df['obv_ma20']) * 100,
                0
            )

        if 'price_to_vwap_pct' in df.columns:
            df['vwap_deviation_ma5'] = df['price_to_vwap_pct'].rolling(5).mean()

        return df

    def _build_composite_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Composite: trend confirmation, overbought/oversold, market strength."""
        if all(c in df.columns for c in ['ema_cross_strength', 'sma_cross_strength', 'macd']):
            df['trend_confirmation_score'] = (
                np.sign(df['ema_cross_strength']) +
                np.sign(df['sma_cross_strength']) +
                np.sign(df['macd'])
            )

        if all(c in df.columns for c in ['rsi', 'bb_position', 'price_to_sma20_pct']):
            df['overbought_score'] = (
                (df['rsi'] > 70).astype(int) +
                (df['bb_position'] > 80).astype(int) +
                (df['price_to_sma20_pct'] > 5).astype(int)
            )
            df['oversold_score'] = (
                (df['rsi'] < 30).astype(int) +
                (df['bb_position'] < 20).astype(int) +
                (df['price_to_sma20_pct'] < -5).astype(int)
            )

        if all(c in df.columns for c in ['ema_cross_strength', 'volume_ratio', 'atr_normalized']):
            df['market_strength'] = (
                abs(df['ema_cross_strength']) *
                df['volume_ratio'] *
                (1 + df['atr_normalized'] / 100)
            )

        if all(c in df.columns for c in ['volatility_20', 'volume_ratio']):
            df['risk_signal'] = (
                df['volatility_20'] *
                (1 / df['volume_ratio'].replace(0, 1))
            )

        if all(c in df.columns for c in ['rsi', 'bb_position', 'macd_momentum_5', 'macd']):
            df['reversal_probability'] = (
                ((df['rsi'] > 80) | (df['rsi'] < 20)).astype(int) * 2 +
                ((df['bb_position'] > 95) | (df['bb_position'] < 5)).astype(int) * 2 +
                (df['macd_momentum_5'] * df['macd'] < 0).astype(int)
            )

        if all(c in df.columns for c in ['trend_confirmation_score', 'volume_ratio', 'volatility_20']):
            df['trend_sustainability'] = (
                abs(df['trend_confirmation_score']) *
                np.clip(df['volume_ratio'], 0.5, 2) *
                (1 - np.clip(df['volatility_20'] / 10, 0, 1))
            )

        return df

    def get_feature_importance_groups(self) -> Dict[str, List[str]]:
        """Return features grouped by importance level."""
        return {
            'critical': [
                'price_to_sma20_pct', 'ema_cross_strength', 'macd', 'rsi',
                'bb_position', 'trend_confirmation_score', 'volume_ratio',
                'atr_normalized'
            ],
            'important': [
                'price_to_sma50_pct', 'sma_cross_strength', 'macd_momentum_5',
                'rsi_momentum_5', 'volatility_20', 'obv_trend',
                'trend_sustainability', 'market_strength'
            ],
            'supplementary': [
                'price_slope_20', 'directional_strength', 'return_10',
                'bb_width_change', 'price_volume_trend', 'overbought_score',
                'oversold_score', 'reversal_probability'
            ]
        }

    def get_feature_descriptions(self) -> Dict[str, str]:
        """Return feature descriptions (English)."""
        return {
            'price_to_sma20_pct': 'Price deviation from 20-day SMA (%)',
            'price_to_sma50_pct': 'Price deviation from 50-day SMA (%)',
            'bb_position': 'Price position in Bollinger Bands (0-100)',
            'price_to_vwap_pct': 'Price deviation from VWAP (%)',
            'ema_cross_strength': 'EMA12 vs EMA26 cross strength',
            'sma_cross_strength': 'SMA20 vs SMA50 cross strength',
            'trend_confirmation_score': 'Multi-indicator trend score (-3 to +3)',
            'trend_sustainability': 'Trend sustainability rating',
            'rsi_momentum_5': 'RSI 5-period momentum',
            'return_10': '10-period return (%)',
            'momentum_acceleration': 'Momentum acceleration',
            'atr_normalized': 'ATR normalized by price (%)',
            'volatility_20': '20-period historical volatility',
            'bb_width_change': 'Bollinger Band width change',
            'volume_ratio': 'Current volume vs average',
            'obv_trend': 'OBV trend indicator',
            'price_volume_trend': 'Price-volume trend',
            'market_strength': 'Composite market strength',
            'overbought_score': 'Overbought composite (0-3)',
            'oversold_score': 'Oversold composite (0-3)',
            'reversal_probability': 'Reversal probability score',
            'risk_signal': 'Risk signal (volatility × 1/volume)',
        }
