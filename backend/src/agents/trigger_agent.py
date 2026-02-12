"""
Trigger Agent - 5m Trigger Analysis
=====================================

Analyzes 5m timeframe data and produces semantic analysis:
- Candlestick patterns (engulfing, etc.)
- Volume analysis (RVOL)
- Entry trigger assessment

Provides both LLM-based and rule-based analysis modes.
Adapted for the current app's architecture (loguru, app LLM module).
"""

from typing import Dict, Optional
from loguru import logger


def _compute_trigger_signals(data: Dict) -> Dict[str, Optional[float]]:
    """Compute trigger signals from input data."""
    pattern = data.get('pattern') or data.get('trigger_pattern')
    rvol = data.get('rvol') or data.get('trigger_rvol', 1.0)
    volume_breakout = data.get('volume_breakout', False)

    if pattern and pattern != 'None':
        stance = 'CONFIRMED'
        status = 'PATTERN_DETECTED'
    elif volume_breakout or rvol > 1.0:
        stance = 'VOLUME_SIGNAL'
        status = 'BREAKOUT'
    else:
        stance = 'WAITING'
        status = 'NO_SIGNAL'

    return {
        'stance': stance,
        'status': status,
        'pattern': pattern if pattern and pattern != 'None' else 'NONE',
        'rvol': rvol,
        'volume_breakout': volume_breakout
    }


class TriggerAgentLLM:
    """
    5m Trigger Analysis Agent (LLM-based)
    
    Input: Pattern detection, RVOL, candle data
    Output: Semantic analysis paragraph
    """
    
    def __init__(self):
        """Initialize TriggerAgentLLM with LLM client"""
        try:
            from src.llm.factory import LLMFactory
            self.client = LLMFactory.get_or_create()
            logger.info("⚡ Trigger Agent LLM initialized")
        except Exception as e:
            logger.warning(f"⚡ TriggerAgentLLM: Failed to init LLM client: {e}")
            self.client = None
    
    def analyze(self, data: Dict) -> Dict:
        """
        Analyze 5m trigger data and return semantic analysis with stance.
        
        Args:
            data: Dict with symbol, pattern, rvol, volume_breakout, trend_direction
        Returns:
            Dict with 'analysis', 'stance', and 'metadata'
        """
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

            
            signals = _compute_trigger_signals(data)
            
            result = {
                'analysis': analysis,
                'stance': signals['stance'],
                'metadata': {
                    'status': signals['status'],
                    'pattern': signals['pattern'],
                    'rvol': round(signals['rvol'], 1),
                    'volume_breakout': signals['volume_breakout']
                }
            }
            
            logger.info(f"⚡ Trigger Agent LLM [{signals['stance']}] "
                       f"(Pattern: {result['metadata']['pattern']}, RVOL: {signals['rvol']:.1f}x) "
                       f"for {data.get('symbol', 'UNKNOWN')}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Trigger Agent error: {e}")
            fallback = self._get_fallback_analysis(data)
            return {
                'analysis': fallback,
                'stance': 'ERROR',
                'metadata': {'error': str(e)}
            }
    
    def _get_system_prompt(self) -> str:
        return """You are a professional market trigger analyst. Analyze 5m timeframe data and assess entry triggers using candlestick patterns and volume.

Output format: 2-3 sentences covering:
1. Pattern detection status (engulfing, volume breakout, or none)
2. Volume analysis (RVOL status)
3. Trigger confirmation (confirmed or waiting)
4. Specific action recommendation

Be concise, professional, and objective. Use trading terminology.
Do NOT use markdown formatting. Output plain text only."""

    def _build_prompt(self, data: Dict) -> str:
        symbol = data.get('symbol', 'UNKNOWN')
        pattern = data.get('pattern') or data.get('trigger_pattern')
        pattern_type = data.get('pattern_type', '')
        rvol = data.get('rvol') or data.get('trigger_rvol', 1.0)
        volume_breakout = data.get('volume_breakout', False)
        trend = data.get('trend_direction', 'neutral')
        
        if pattern and pattern != 'None':
            pattern_status = f"DETECTED: {pattern_type or pattern}"
        else:
            pattern_status = "NO PATTERN DETECTED"
        
        if rvol > 1.8:
            rvol_status = f"VERY HIGH VOLUME ({rvol:.1f}x average)"
        elif rvol > 1.2:
            rvol_status = f"HIGH VOLUME ({rvol:.1f}x average)"
        elif rvol >= 1.0:
            rvol_status = f"NORMAL VOLUME ({rvol:.1f}x average)"
        else:
            rvol_status = f"LOW VOLUME ({rvol:.1f}x average)"
        
        breakout_status = "YES - Price broke recent highs/lows with volume" if volume_breakout else "NO"
        
        return f"""Analyze the following 5m trigger data for {symbol}:

Trend Direction (from Layer 1): {trend.upper()}

Candlestick Pattern:
- Pattern: {pattern_status}
- For LONG: Looking for bullish engulfing
- For EXIT: Looking for bearish engulfing

Volume Analysis:
- RVOL: {rvol:.1f}x
- Status: {rvol_status}
- Volume Breakout: {breakout_status}

Trigger Requirement:
- Need engulfing pattern OR volume breakout (RVOL > 1.5x + price breakout)

Provide a 2-3 sentence semantic analysis of the trigger situation."""

    def _get_fallback_analysis(self, data: Dict) -> str:
        pattern = data.get('pattern') or data.get('trigger_pattern')
        rvol = data.get('rvol') or data.get('trigger_rvol', 1.0)
        trend = data.get('trend_direction', 'neutral')
        
        if pattern and pattern != 'None':
            return f"5m trigger CONFIRMED: {pattern} pattern detected with RVOL={rvol:.1f}x. Entry signal is valid for {trend} position."
        elif rvol > 1.5:
            return f"5m shows high volume activity (RVOL={rvol:.1f}x) but no clear pattern. Monitor for pattern formation."
        else:
            return f"5m shows no trigger pattern. RVOL={rvol:.1f}x is normal. Wait for engulfing pattern or volume breakout before entry."


class TriggerAgent:
    """
    5m Trigger Analysis Agent (no LLM)
    Uses rule-based heuristics only.
    """

    def __init__(self):
        logger.info("⚡ Trigger Agent (no LLM) initialized")

    def analyze(self, data: Dict) -> Dict:
        signals = _compute_trigger_signals(data)
        analysis = self._get_fallback_analysis(data)
        result = {
            'analysis': analysis,
            'stance': signals['stance'],
            'metadata': {
                'status': signals['status'],
                'pattern': signals['pattern'],
                'rvol': round(signals['rvol'], 1),
                'volume_breakout': signals['volume_breakout']
            }
        }
        logger.info(f"⚡ Trigger Agent (no LLM) [{signals['stance']}] "
                    f"(Pattern: {signals['pattern']}, RVOL: {signals['rvol']:.1f}x) "
                    f"for {data.get('symbol', 'UNKNOWN')}")
        return result

    def _get_fallback_analysis(self, data: Dict) -> str:
        pattern = data.get('pattern') or data.get('trigger_pattern')
        rvol = data.get('rvol') or data.get('trigger_rvol', 1.0)
        trend = data.get('trend_direction', 'neutral')
        
        if pattern and pattern != 'None':
            return f"5m trigger CONFIRMED: {pattern} pattern detected with RVOL={rvol:.1f}x. Entry signal is valid for {trend} position."
        elif rvol > 1.5:
            return f"5m shows high volume activity (RVOL={rvol:.1f}x) but no clear pattern. Monitor for pattern formation."
        else:
            return f"5m shows no trigger pattern. RVOL={rvol:.1f}x is normal. Wait for engulfing pattern or volume breakout before entry."
