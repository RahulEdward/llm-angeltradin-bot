"""
Trend Agent - 1h Trend Analysis
=================================

Analyzes 1h timeframe data and produces semantic analysis:
- EMA20/60 trend direction
- OI fuel status (adapted: volume-based for equities)
- ADX trend strength
- Market regime

Provides both LLM-based and rule-based analysis modes.
"""

from typing import Dict, Optional
from loguru import logger


def _compute_trend_signals(data: Dict) -> Dict[str, Optional[float]]:
    """Compute trend signals from input data."""
    close = data.get('close_1h', 0)
    ema20 = data.get('ema20_1h', 0)
    ema60 = data.get('ema60_1h', 0)
    adx = data.get('adx', 0)
    # For equities: use volume change instead of OI change
    volume_change = data.get('oi_change', data.get('volume_change', 0))

    if close > ema20 > ema60:
        stance = 'UPTREND'
    elif close < ema20 < ema60:
        stance = 'DOWNTREND'
    else:
        stance = 'NEUTRAL'

    if adx > 25:
        strength = 'STRONG'
    elif adx >= 20:
        strength = 'MODERATE'
    else:
        strength = 'WEAK'

    if abs(volume_change) > 3:
        fuel = 'STRONG'
    elif abs(volume_change) >= 1:
        fuel = 'MODERATE'
    else:
        fuel = 'WEAK'

    return {
        'stance': stance,
        'strength': strength,
        'fuel': fuel,
        'adx': adx,
        'volume_change': volume_change
    }


class TrendAgentLLM:
    """
    1h Trend Analysis Agent (LLM-based)
    
    Input: EMA, Volume, ADX, Regime data
    Output: Semantic analysis paragraph
    """
    
    def __init__(self):
        try:
            from src.llm.factory import LLMFactory
            self.client = LLMFactory.get_or_create()
            logger.info("📈 Trend Agent LLM initialized")
        except Exception as e:
            logger.warning(f"📈 TrendAgentLLM: Failed to init LLM client: {e}")
            self.client = None
    
    def analyze(self, data: Dict) -> Dict:
        """Analyze 1h trend data and return semantic analysis with stance."""
        try:
            if self.client:
                import asyncio
                from src.llm.base import Message, MessageRole
                prompt = self._build_prompt(data)
                messages = [
                    Message(role=MessageRole.SYSTEM, content=self._get_system_prompt()),
                    Message(role=MessageRole.USER, content=prompt)
                ]
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            response = pool.submit(lambda: asyncio.run(self.client.chat(messages))).result()
                    else:
                        response = loop.run_until_complete(self.client.chat(messages))
                except RuntimeError:
                    response = asyncio.run(self.client.chat(messages))
                analysis = response.content.strip()
            else:
                analysis = self._get_fallback_analysis(data)
            
            signals = _compute_trend_signals(data)

            result = {
                'analysis': analysis,
                'stance': signals['stance'],
                'metadata': {
                    'strength': signals['strength'],
                    'adx': round(signals['adx'], 1),
                    'volume_fuel': signals['fuel'],
                    'volume_change': round(signals['volume_change'], 1)
                }
            }
            
            logger.info(f"📈 Trend Agent LLM [{signals['stance']}] "
                       f"(Strength: {signals['strength']}, ADX: {signals['adx']:.1f}) "
                       f"for {data.get('symbol', 'UNKNOWN')}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Trend Agent error: {e}")
            fallback = self._get_fallback_analysis(data)
            return {
                'analysis': fallback,
                'stance': 'ERROR',
                'metadata': {'error': str(e)}
            }
    
    def _get_system_prompt(self) -> str:
        return """You are a professional market trend analyst. Analyze 1h timeframe data and provide a concise semantic analysis.

Output format: 2-3 sentences covering:
1. Trend direction (uptrend/downtrend/neutral) based on EMA alignment
2. Volume fuel status
3. Trend strength based on ADX
4. Trading recommendation (suitable for trend trading or not)

Be concise, professional, and objective. Use trading terminology.
Do NOT use markdown formatting. Output plain text only."""

    def _build_prompt(self, data: Dict) -> str:
        symbol = data.get('symbol', 'UNKNOWN')
        close = data.get('close_1h', 0)
        ema20 = data.get('ema20_1h', 0)
        ema60 = data.get('ema60_1h', 0)
        volume_change = data.get('oi_change', data.get('volume_change', 0))
        adx = data.get('adx', 20)
        regime = data.get('regime', 'unknown')
        
        if close > ema20 > ema60:
            ema_status = "UPTREND (Close > EMA20 > EMA60)"
        elif close < ema20 < ema60:
            ema_status = "DOWNTREND (Close < EMA20 < EMA60)"
        else:
            ema_status = "NEUTRAL (EMAs not aligned)"
        
        if abs(volume_change) > 3:
            fuel_status = "STRONG VOLUME FUEL"
        elif abs(volume_change) >= 1:
            fuel_status = "MODERATE VOLUME FUEL"
        else:
            fuel_status = "WEAK VOLUME FUEL"
        
        if adx > 20:
            adx_status = "STRONG TREND"
        elif adx >= 15:
            adx_status = "MODERATE TREND"
        else:
            adx_status = "WEAK/NO TREND"
        
        return f"""Analyze the following 1h trend data for {symbol}:

Price & EMA:
- 1h Close: ₹{close:,.2f}
- 1h EMA20: ₹{ema20:,.2f}
- 1h EMA60: ₹{ema60:,.2f}
- EMA Status: {ema_status}

Volume:
- Volume Change (24h): {volume_change:+.1f}%
- Fuel Status: {fuel_status}

Trend Strength:
- ADX: {adx:.0f}
- ADX Status: {adx_status}

Market Regime: {regime.upper()}

Provide a 2-3 sentence semantic analysis of the trend situation."""

    def _get_fallback_analysis(self, data: Dict) -> str:
        close = data.get('close_1h', 0)
        ema20 = data.get('ema20_1h', 0)
        ema60 = data.get('ema60_1h', 0)
        volume_change = data.get('oi_change', data.get('volume_change', 0))
        adx = data.get('adx', 20)
        
        if close > ema20 > ema60:
            trend = "uptrend"
        elif close < ema20 < ema60:
            trend = "downtrend"
        else:
            trend = "neutral"
        
        fuel = "strong" if abs(volume_change) > 3 else "moderate" if abs(volume_change) >= 1 else "weak"
        strength = "strong" if adx > 25 else "weak"
        
        return (f"1h shows {trend} with {fuel} volume fuel ({volume_change:+.1f}%). "
                f"ADX={adx:.0f} indicates {strength} trend strength. "
                f"{'Suitable for trend trading.' if adx >= 20 and abs(volume_change) >= 1 else 'Not suitable for trend trading.'}")


class TrendAgent:
    """
    1h Trend Analysis Agent (no LLM)
    Uses rule-based heuristics only.
    """

    def __init__(self):
        logger.info("📈 Trend Agent (no LLM) initialized")

    def analyze(self, data: Dict) -> Dict:
        signals = _compute_trend_signals(data)
        analysis = self._get_fallback_analysis(data)
        result = {
            'analysis': analysis,
            'stance': signals['stance'],
            'metadata': {
                'strength': signals['strength'],
                'adx': round(signals['adx'], 1),
                'volume_fuel': signals['fuel'],
                'volume_change': round(signals['volume_change'], 1)
            }
        }
        logger.info(f"📈 Trend Agent (no LLM) [{signals['stance']}] "
                    f"(Strength: {signals['strength']}, ADX: {signals['adx']:.1f}) "
                    f"for {data.get('symbol', 'UNKNOWN')}")
        return result

    def _get_fallback_analysis(self, data: Dict) -> str:
        close = data.get('close_1h', 0)
        ema20 = data.get('ema20_1h', 0)
        ema60 = data.get('ema60_1h', 0)
        volume_change = data.get('oi_change', data.get('volume_change', 0))
        adx = data.get('adx', 20)

        if close > ema20 > ema60:
            trend = "uptrend"
        elif close < ema20 < ema60:
            trend = "downtrend"
        else:
            trend = "neutral"

        fuel = "strong" if abs(volume_change) > 3 else "moderate" if abs(volume_change) >= 1 else "weak"
        strength = "strong" if adx > 25 else "weak"

        return (f"1h shows {trend} with {fuel} volume fuel ({volume_change:+.1f}%). "
                f"ADX={adx:.0f} indicates {strength} trend strength. "
                f"{'Suitable for trend trading.' if adx >= 20 and abs(volume_change) >= 1 else 'Not suitable for trend trading.'}")
