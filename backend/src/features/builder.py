"""
Feature Builder — Market Context Constructor
=============================================

Converts multi-timeframe market data into structured context
for LLM consumption. Includes data quality validation.

Adapted for Indian equity markets:
- No funding rate or OI (these are crypto concepts)
- Delivery volume, VWAP, and price-volume analysis
- INR currency formatting
- Loguru logging
"""

from typing import Dict, Optional
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger


class FeatureBuilder:
    """Builds market context from multi-timeframe data for LLM input."""

    def __init__(self):
        pass

    def build_market_context(
        self,
        symbol: str,
        multi_timeframe_states: Dict[str, Dict],
        snapshot: Dict,
        position_info: Optional[Dict] = None
    ) -> Dict:
        """
        Build complete market context.
        
        Args:
            symbol: Trading symbol (e.g., 'RELIANCE')
            multi_timeframe_states: Multi-TF market states
            snapshot: Current market snapshot
            position_info: Current position info
            
        Returns:
            Structured market context dict
        """
        # Data quality validation
        price_check = self._validate_multiframe_prices(multi_timeframe_states)
        if not price_check['consistent']:
            logger.debug(f"[{symbol}] Price consistency: {', '.join(price_check['warnings'])}")

        alignment_check = self._validate_multiframe_alignment(multi_timeframe_states)
        if not alignment_check['aligned']:
            logger.debug(f"[{symbol}] Time alignment: {', '.join(alignment_check['warnings'])}")

        # Indicator completeness
        indicator_completeness = {}
        for tf, state in multi_timeframe_states.items():
            if 'indicator_completeness' in state:
                indicator_completeness[tf] = state['indicator_completeness']
            else:
                indicator_completeness[tf] = {
                    'is_complete': None,
                    'issues': ['Indicator completeness not provided'],
                    'overall_coverage': None
                }

        current_price = snapshot.get('price', {}).get('price', 0)

        context = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,

            'market_overview': {
                'current_price': current_price,
                'day_change_pct': snapshot.get('day_change_pct', 0),
                'day_volume': snapshot.get('day_volume', 0),
            },

            'multi_timeframe': multi_timeframe_states,

            'position_context': self._build_position_context(
                position_info,
                current_price,
                snapshot.get('account', {})
            ),

            'risk_constraints': self._get_risk_constraints(),

            'data_quality': {
                'price_consistency': price_check,
                'time_alignment': alignment_check,
                'indicator_completeness': indicator_completeness,
                'overall_score': self._calculate_quality_score(
                    price_check, alignment_check, indicator_completeness
                )
            }
        }

        return context

    def _build_position_context(
        self,
        position: Optional[Dict],
        current_price: float,
        account: Optional[Dict]
    ) -> Dict:
        """Build position context for LLM."""
        if not account:
            return {
                'has_position': False,
                'side': 'NONE',
                'size': None,
                'entry_price': None,
                'current_pnl_pct': None,
                'unrealized_pnl': None,
                'account_balance': None,
                'warning': '⚠️ Account info missing'
            }

        if not position:
            return {
                'has_position': False,
                'side': 'NONE',
                'size': 0,
                'entry_price': 0,
                'current_pnl_pct': 0,
                'unrealized_pnl': 0,
                'account_balance': account.get('available_balance', 0),
                'total_balance': account.get('total_balance', 0),
            }

        qty = position.get('quantity', 0)
        entry_price = position.get('entry_price', 0)
        unrealized_pnl = position.get('unrealized_pnl', 0)

        pnl_pct = 0
        if entry_price > 0 and qty > 0:
            pnl_pct = (current_price - entry_price) / entry_price * 100

        return {
            'has_position': qty > 0,
            'side': 'LONG' if qty > 0 else 'NONE',
            'size': abs(qty),
            'entry_price': entry_price,
            'current_price': current_price,
            'current_pnl_pct': round(pnl_pct, 2),
            'unrealized_pnl': unrealized_pnl,
            'account_balance': account.get('available_balance', 0),
            'total_balance': account.get('total_balance', 0),
        }

    def _get_risk_constraints(self) -> Dict:
        """Get risk constraints from settings."""
        try:
            from src.config.settings import settings
            return {
                'max_risk_per_trade_pct': getattr(settings, 'max_risk_per_trade_pct', 2.0),
                'max_total_position_pct': getattr(settings, 'max_total_position_pct', 30.0),
                'max_consecutive_losses': getattr(settings, 'max_consecutive_losses', 3)
            }
        except Exception:
            return {
                'max_risk_per_trade_pct': 2.0,
                'max_total_position_pct': 30.0,
                'max_consecutive_losses': 3
            }

    def format_for_llm(self, context: Dict) -> str:
        """Format context as human-readable text for LLM input."""
        market = context['market_overview']
        position = context['position_context']
        mtf = context['multi_timeframe']
        constraints = context['risk_constraints']

        text = f"""
## Market Snapshot ({context['timestamp']})

**Symbol**: {context['symbol']}
**Current Price**: ₹{market['current_price']:,.2f}
**Day Change**: {market.get('day_change_pct', 0):.2f}%

### Multi-Timeframe Analysis
"""

        timeframe_order = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        sorted_tfs = sorted(
            mtf.keys(),
            key=lambda x: timeframe_order.index(x) if x in timeframe_order else 999
        )

        for tf in sorted_tfs:
            state = mtf[tf]
            text += f"\n**{tf}**:\n"
            text += f"  - Trend: {state.get('trend', 'N/A')}\n"
            text += f"  - Volatility: {state.get('volatility', 'N/A')} (ATR: {state.get('atr_pct', 'N/A')}%)\n"
            text += f"  - Momentum: {state.get('momentum', 'N/A')}\n"
            text += f"  - RSI: {state.get('rsi', 'N/A')}\n"
            text += f"  - MACD Signal: {state.get('macd_signal', 'N/A')}\n"
            text += f"  - Volume Ratio: {state.get('volume_ratio', 'N/A')}\n"
            text += f"  - Price: ₹{state.get('price', 'N/A')}\n"

            levels = state.get('key_levels', {})
            if levels.get('support'):
                text += f"  - Support: {levels['support']}\n"
            if levels.get('resistance'):
                text += f"  - Resistance: {levels['resistance']}\n"

        # Position
        text += "\n### Current Position\n"
        if position.get('has_position'):
            text += f"- Direction: {position['side']}\n"
            text += f"- Quantity: {position['size']}\n"
            text += f"- Entry Price: ₹{position['entry_price']:,.2f}\n"
            text += f"- Unrealized P&L: {position['current_pnl_pct']:.2f}%\n"
        else:
            text += "- No position\n"

        # Account
        text += "\n### Account Info\n"
        balance = position.get('account_balance')
        total = position.get('total_balance', 0)
        if balance is not None:
            text += f"- Available Balance: ₹{balance:,.2f}\n"
            text += f"- Total Balance: ₹{total:,.2f}\n"
        else:
            text += "- Balance: **Unknown**\n"

        # Risk
        text += "\n### Risk Constraints\n"
        text += f"- Max Risk Per Trade: {constraints['max_risk_per_trade_pct']}%\n"
        text += f"- Max Total Position: {constraints['max_total_position_pct']}%\n"
        text += f"- Max Consecutive Losses: {constraints['max_consecutive_losses']}\n"

        return text

    def _validate_multiframe_prices(self, multi_timeframe_states: Dict[str, Dict]) -> Dict:
        """Validate price consistency across timeframes."""
        all_prices = []
        warnings = []
        for tf, state in multi_timeframe_states.items():
            if 'close' in state:
                all_prices.append(state['close'])
            else:
                warnings.append(f"{tf} missing close price")

        if len(set(all_prices)) > 1:
            warnings.append("Inconsistent close prices across timeframes")

        return {
            'consistent': len(warnings) == 0,
            'warnings': warnings
        }

    def _validate_multiframe_alignment(self, multi_timeframe_states: Dict[str, Dict]) -> Dict:
        """Validate time alignment across timeframes."""
        warnings = []
        for tf, state in multi_timeframe_states.items():
            if 'timestamp' not in state:
                warnings.append(f"{tf} missing timestamp")
        return {
            'aligned': len(warnings) == 0,
            'warnings': warnings
        }

    def _calculate_quality_score(
        self,
        price_check: Dict,
        alignment_check: Dict,
        indicator_completeness: Dict
    ) -> float:
        """Calculate data quality score (0-100)."""
        score = 100.0

        if not price_check.get('consistent', True):
            score -= 30
        elif len(price_check.get('warnings', [])) > 0:
            score -= 15

        if not alignment_check.get('aligned', True):
            score -= 20

        completeness_scores = []
        for tf, comp in indicator_completeness.items():
            if comp.get('is_complete') is True:
                completeness_scores.append(100.0)
            elif comp.get('overall_coverage') is not None:
                completeness_scores.append(comp['overall_coverage'] * 100)
            else:
                completeness_scores.append(0.0)

        if completeness_scores:
            avg = sum(completeness_scores) / len(completeness_scores)
            score -= (100 - avg) * 0.5
        else:
            score -= 50

        return max(score, 0.0)
