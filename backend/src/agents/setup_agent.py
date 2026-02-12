"""
Setup Agent - 15m Setup Analysis
=================================

Analyzes 15m timeframe data and produces semantic analysis:
- KDJ oscillator position
- Bollinger Band position
- MACD momentum (15m)
- Entry zone assessment

Provides both LLM-based and rule-based analysis modes.
"""

from typing import Dict, Optional
from loguru import logger


def _compute_setup_signals(data: Dict) -> Dict[str, Optional[float]]:
    """Compute setup signals from input data."""
    kdj_j = data.get('kdj_j', 50)
    trend = data.get('trend_direction', 'neutral')
    close = data.get('close_15m', 0)
    bb_middle = data.get('bb_middle', 0)
    macd_diff = data.get('macd_diff', 0)

    if trend == 'long':
        if kdj_j < 40:
            stance = 'PULLBACK_ZONE'
            zone = 'GOOD_ENTRY'
        elif kdj_j > 80:
            stance = 'OVERBOUGHT'
            zone = 'WAIT'
        else:
            stance = 'NEUTRAL'
            zone = 'MONITOR'
    elif trend == 'short':
        if kdj_j > 60:
            stance = 'RALLY_ZONE'
            zone = 'GOOD_ENTRY'
        elif kdj_j < 20:
            stance = 'OVERSOLD'
            zone = 'WAIT'
        else:
            stance = 'NEUTRAL'
            zone = 'MONITOR'
    else:
        stance = 'NEUTRAL'
        zone = 'WAIT'

    if macd_diff > 0:
        macd_signal = 'BULLISH'
    elif macd_diff < 0:
        macd_signal = 'BEARISH'
    else:
        macd_signal = 'NEUTRAL'

    bb_position = 'ABOVE_MID' if close > bb_middle else 'BELOW_MID'

    return {
        'stance': stance,
        'zone': zone,
        'kdj_j': kdj_j,
        'trend': trend,
        'bb_position': bb_position,
        'macd_signal': macd_signal,
        'macd_diff': macd_diff
    }


class SetupAgentLLM:
    """
    15m Setup Analysis Agent (LLM-based)
    
    Input: KDJ, Bollinger Bands, MACD (15m), price position
    Output: Semantic analysis paragraph
    """
    
    def __init__(self):
        try:
            from src.llm.factory import LLMFactory
            self.client = LLMFactory.get_or_create()
            logger.info("📊 Setup Agent LLM initialized")
        except Exception as e:
            logger.warning(f"📊 SetupAgentLLM: Failed to init LLM client: {e}")
            self.client = None
    
    def analyze(self, data: Dict) -> Dict:
        """Analyze 15m setup data and return semantic analysis with stance."""
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
            
            signals = _compute_setup_signals(data)
            
            result = {
                'analysis': analysis,
                'stance': signals['stance'],
                'metadata': {
                    'zone': signals['zone'],
                    'kdj_j': round(signals['kdj_j'], 1),
                    'trend': signals['trend'].upper(),
                    'bb_position': signals['bb_position'],
                    'macd_signal': signals['macd_signal'],
                    'macd_diff': round(signals['macd_diff'], 2)
                }
            }
            
            logger.info(f"📊 Setup Agent LLM [{signals['stance']}] "
                       f"(Zone: {signals['zone']}, KDJ: {signals['kdj_j']:.1f}) "
                       f"for {data.get('symbol', 'UNKNOWN')}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Setup Agent error: {e}")
            fallback = self._get_fallback_analysis(data)
            return {
                'analysis': fallback,
                'stance': 'ERROR',
                'metadata': {'error': str(e)}
            }
    
    def _get_system_prompt(self) -> str:
        return """You are a professional market setup analyst. Analyze 15m timeframe data and assess entry positions using KDJ, Bollinger Bands, and MACD.

Output format: 2-3 sentences covering:
1. KDJ oscillator status (overbought/oversold/neutral)
2. MACD momentum direction and strength
3. Price position relative to Bollinger Bands
4. Entry zone assessment (good entry zone or wait)

Be concise, professional, and objective. Use trading terminology.
Do NOT use markdown formatting. Output plain text only."""

    def _build_prompt(self, data: Dict) -> str:
        symbol = data.get('symbol', 'UNKNOWN')
        close = data.get('close_15m', 0)
        kdj_j = data.get('kdj_j', 50)
        kdj_k = data.get('kdj_k', 50)
        bb_upper = data.get('bb_upper', 0)
        bb_middle = data.get('bb_middle', 0)
        bb_lower = data.get('bb_lower', 0)
        trend = data.get('trend_direction', 'neutral')
        macd_diff = data.get('macd_diff', 0)
        
        if kdj_j > 80:
            kdj_status = "OVERBOUGHT (J > 80)"
        elif kdj_j < 20:
            kdj_status = "OVERSOLD (J < 20)"
        elif kdj_j < 50:
            kdj_status = "PULLBACK ZONE (J < 50)"
        elif kdj_j > 50:
            kdj_status = "RALLY ZONE (J > 50)"
        else:
            kdj_status = "NEUTRAL (40 < J < 60)"
        
        if close > bb_upper:
            bb_status = "ABOVE UPPER BAND (extended)"
        elif close < bb_lower:
            bb_status = "BELOW LOWER BAND (extended)"
        elif close > bb_middle:
            bb_status = "ABOVE MIDDLE BAND"
        else:
            bb_status = "BELOW MIDDLE BAND"
        
        if macd_diff > 0:
            macd_status = f"BULLISH (Diff: {macd_diff:+.2f})"
        elif macd_diff < 0:
            macd_status = f"BEARISH (Diff: {macd_diff:+.2f})"
        else:
            macd_status = "NEUTRAL"
        
        return f"""Analyze the following 15m setup data for {symbol}:

1h Trend Direction: {trend.upper()}

KDJ Oscillator:
- KDJ_J: {kdj_j:.1f}
- KDJ_K: {kdj_k:.1f}
- Status: {kdj_status}

MACD (15m):
- Histogram Diff: {macd_diff:+.2f}
- Status: {macd_status}

Bollinger Bands:
- Upper: ₹{bb_upper:,.2f}
- Middle: ₹{bb_middle:,.2f}
- Lower: ₹{bb_lower:,.2f}
- 15m Close: ₹{close:,.2f}
- Position: {bb_status}

Provide a 2-3 sentence semantic analysis of the setup situation.
Consider: For LONG, we want pullback (KDJ<40 or near lower BB) + bullish MACD. For EXIT, we want rally (KDJ>60 or near upper BB) + bearish MACD."""

    def _get_fallback_analysis(self, data: Dict) -> str:
        kdj_j = data.get('kdj_j', 50)
        trend = data.get('trend_direction', 'neutral')
        close = data.get('close_15m', 0)
        bb_middle = data.get('bb_middle', 0)
        
        if trend == 'long':
            if kdj_j < 40:
                return f"15m setup shows pullback zone with KDJ_J={kdj_j:.0f}. Good entry area for long positions. Price is {'below' if close < bb_middle else 'above'} BB middle."
            elif kdj_j > 80:
                return f"15m is overbought with KDJ_J={kdj_j:.0f}. Wait for pullback before entering long positions."
            else:
                return f"15m is in neutral zone with KDJ_J={kdj_j:.0f}. Wait for clearer pullback signal."
        elif trend == 'short':
            if kdj_j > 60:
                return f"15m setup shows rally zone with KDJ_J={kdj_j:.0f}. Consider exiting long positions."
            elif kdj_j < 20:
                return f"15m is oversold with KDJ_J={kdj_j:.0f}. Wait for rally before considering exit."
            else:
                return f"15m is in neutral zone with KDJ_J={kdj_j:.0f}. Wait for clearer signal."
        else:
            return f"15m shows neutral setup with KDJ_J={kdj_j:.0f}. No clear entry signal."


class SetupAgent:
    """
    15m Setup Analysis Agent (no LLM)
    Uses rule-based heuristics only.
    """

    def __init__(self):
        logger.info("📊 Setup Agent (no LLM) initialized")

    def analyze(self, data: Dict) -> Dict:
        signals = _compute_setup_signals(data)
        analysis = self._get_fallback_analysis(data)
        result = {
            'analysis': analysis,
            'stance': signals['stance'],
            'metadata': {
                'zone': signals['zone'],
                'kdj_j': round(signals['kdj_j'], 1),
                'trend': signals['trend'].upper(),
                'bb_position': signals['bb_position'],
                'macd_signal': signals['macd_signal'],
                'macd_diff': round(signals['macd_diff'], 2)
            }
        }
        logger.info(f"📊 Setup Agent (no LLM) [{signals['stance']}] "
                    f"(Zone: {signals['zone']}, KDJ: {signals['kdj_j']:.1f}) "
                    f"for {data.get('symbol', 'UNKNOWN')}")
        return result

    def _get_fallback_analysis(self, data: Dict) -> str:
        kdj_j = data.get('kdj_j', 50)
        trend = data.get('trend_direction', 'neutral')
        close = data.get('close_15m', 0)
        bb_middle = data.get('bb_middle', 0)
        
        if trend == 'long':
            if kdj_j < 40:
                return f"15m setup shows pullback zone with KDJ_J={kdj_j:.0f}. Good entry area for long positions. Price is {'below' if close < bb_middle else 'above'} BB middle."
            elif kdj_j > 80:
                return f"15m is overbought with KDJ_J={kdj_j:.0f}. Wait for pullback before entering long positions."
            else:
                return f"15m is in neutral zone with KDJ_J={kdj_j:.0f}. Wait for clearer pullback signal."
        elif trend == 'short':
            if kdj_j > 60:
                return f"15m setup shows rally zone with KDJ_J={kdj_j:.0f}. Consider exiting long positions."
            elif kdj_j < 20:
                return f"15m is oversold with KDJ_J={kdj_j:.0f}. Wait for rally before considering exit."
            else:
                return f"15m is in neutral zone with KDJ_J={kdj_j:.0f}. Wait for clearer signal."
        else:
            return f"15m shows neutral setup with KDJ_J={kdj_j:.0f}. No clear entry signal."
