"""
OpenAI LLM Client Implementation
Supports OpenAI API and compatible endpoints (Azure, local proxies)
"""

import json
import time
from typing import List, Dict, Any, Optional
from loguru import logger

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None
    logger.warning("OpenAI library not installed")

from .base import (
    BaseLLMClient, Message, LLMResponse, TradingDecision, MessageRole
)
from . import metrics as llm_metrics


class OpenAIClient(BaseLLMClient):
    """
    OpenAI API client for trading analysis.
    Supports GPT-4, GPT-3.5, and compatible endpoints.
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        provider_name: str = "openai"
    ):
        super().__init__(model, temperature, max_tokens)
        
        if AsyncOpenAI is None:
            raise ImportError("OpenAI library not installed. Run: pip install openai")
        
        self.provider_name = provider_name
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
    
    async def chat(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Send chat messages to OpenAI."""
        provider = self.provider_name
        llm_metrics.record_request(provider, self.model)
        start_time = time.time()
        try:
            formatted_messages = [
                {"role": msg.role.value, "content": msg.content}
                for msg in messages
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            llm_metrics.record_success(provider, self.model, latency_ms, usage)
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                tokens_used=response.usage.total_tokens,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                finish_reason=response.choices[0].finish_reason,
                raw_response=response.model_dump()
            )
            
        except Exception as e:
            llm_metrics.record_error(provider, self.model, str(e))
            logger.error(f"OpenAI chat error: {str(e)}")
            raise
    
    async def analyze_market(
        self,
        market_data: Dict[str, Any],
        indicators: Dict[str, Any],
        context: Optional[str] = None
    ) -> TradingDecision:
        """Analyze market and return trading decision."""
        
        system_prompt = self._build_system_prompt("trader")
        
        user_content = f"""
Analyze the following market data for trading decision:

**Symbol**: {market_data.get('symbol', 'Unknown')}
**Exchange**: {market_data.get('exchange', 'NSE')}
**Timeframe**: {market_data.get('timeframe', '5m')}

**Current Price Data**:
- LTP: ₹{market_data.get('ltp', 0):.2f}
- Open: ₹{market_data.get('open', 0):.2f}
- High: ₹{market_data.get('high', 0):.2f}
- Low: ₹{market_data.get('low', 0):.2f}
- Close: ₹{market_data.get('close', 0):.2f}
- Volume: {market_data.get('volume', 0):,}

**Technical Indicators**:
{json.dumps(indicators, indent=2)}

{"**Context**: " + context if context else ""}

Provide your trading decision in the following JSON format:
{{
    "action": "BUY" | "SELL" | "HOLD",
    "symbol": "{market_data.get('symbol', '')}",
    "confidence": 0.0-1.0,
    "reasoning": "detailed explanation",
    "entry_price": price or null,
    "stop_loss": price or null,
    "take_profit": price or null,
    "position_size_pct": 0.0-1.0,
    "risk_level": "low" | "medium" | "high",
    "supporting_indicators": ["list of supporting signals"],
    "contra_indicators": ["list of contrary signals"]
}}
"""
        
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_content)
        ]
        
        response = await self.chat(messages, temperature=0.3)
        
        return self._parse_trading_decision(response.content, market_data)
    
    async def get_bull_perspective(
        self,
        market_data: Dict[str, Any],
        indicators: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get bullish analysis."""
        
        system_prompt = self._build_system_prompt("bull")
        
        user_content = f"""
Analyze the bullish case for {market_data.get('symbol', 'this instrument')}:

**Price Data**:
- Current: ₹{market_data.get('ltp', 0):.2f}
- Today's Range: ₹{market_data.get('low', 0):.2f} - ₹{market_data.get('high', 0):.2f}

**Indicators**:
{json.dumps(indicators, indent=2)}

Provide your bullish analysis in JSON:
{{
    "outlook": "bullish",
    "confidence": 0.0-1.0,
    "key_points": ["point1", "point2"],
    "entry_zone": {{"low": price, "high": price}},
    "targets": [price1, price2],
    "invalidation_level": price,
    "reasoning": "detailed bullish thesis"
}}
"""
        
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_content)
        ]
        
        response = await self.chat(messages, temperature=0.4)
        
        try:
            return json.loads(self._extract_json(response.content))
        except:
            return {
                "outlook": "bullish",
                "confidence": 0.5,
                "key_points": [],
                "reasoning": response.content
            }
    
    async def get_bear_perspective(
        self,
        market_data: Dict[str, Any],
        indicators: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get bearish analysis."""
        
        system_prompt = self._build_system_prompt("bear")
        
        user_content = f"""
Analyze the bearish case for {market_data.get('symbol', 'this instrument')}:

**Price Data**:
- Current: ₹{market_data.get('ltp', 0):.2f}
- Today's Range: ₹{market_data.get('low', 0):.2f} - ₹{market_data.get('high', 0):.2f}

**Indicators**:
{json.dumps(indicators, indent=2)}

Provide your bearish analysis in JSON:
{{
    "outlook": "bearish",
    "confidence": 0.0-1.0,
    "key_points": ["point1", "point2"],
    "resistance_zones": [price1, price2],
    "targets": [price1, price2],
    "invalidation_level": price,
    "reasoning": "detailed bearish thesis"
}}
"""
        
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_content)
        ]
        
        response = await self.chat(messages, temperature=0.4)
        
        try:
            return json.loads(self._extract_json(response.content))
        except:
            return {
                "outlook": "bearish",
                "confidence": 0.5,
                "key_points": [],
                "reasoning": response.content
            }
    
    async def synthesize_decision(
        self,
        bull_view: Dict[str, Any],
        bear_view: Dict[str, Any],
        quant_signals: Dict[str, Any]
    ) -> TradingDecision:
        """Synthesize perspectives into final decision."""
        
        system_prompt = """You are the Decision Core for a trading system.
Your role is to synthesize bull and bear perspectives into a final trading decision.
Be objective and weight evidence carefully.
Output your decision in valid JSON format."""
        
        user_content = f"""
Synthesize the following perspectives into a final trading decision:

**BULL PERSPECTIVE**:
{json.dumps(bull_view, indent=2)}

**BEAR PERSPECTIVE**:
{json.dumps(bear_view, indent=2)}

**QUANTITATIVE SIGNALS**:
{json.dumps(quant_signals, indent=2)}

Provide your synthesized decision in JSON:
{{
    "action": "BUY" | "SELL" | "HOLD",
    "symbol": "symbol",
    "confidence": 0.0-1.0,
    "reasoning": "detailed synthesis",
    "entry_price": price or null,
    "stop_loss": price or null,
    "take_profit": price or null,
    "risk_level": "low" | "medium" | "high",
    "bull_weight": 0.0-1.0,
    "bear_weight": 0.0-1.0,
    "key_factors": ["factor1", "factor2"]
}}
"""
        
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_content)
        ]
        
        response = await self.chat(messages, temperature=0.2)
        
        return self._parse_trading_decision(
            response.content,
            {"symbol": quant_signals.get("symbol", "")}
        )
    
    async def reflect_on_trades(
        self,
        trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Reflect on past trades for learning."""
        
        system_prompt = """You are a trading performance analyst.
Analyze past trades to identify patterns, mistakes, and improvements.
Be constructive and specific in your recommendations."""
        
        user_content = f"""
Analyze these recent trades and provide insights:

**Trade History**:
{json.dumps(trade_history, indent=2)}

Provide your analysis in JSON:
{{
    "total_trades": number,
    "win_rate": percentage,
    "avg_profit": amount,
    "avg_loss": amount,
    "patterns_identified": ["pattern1", "pattern2"],
    "mistakes_made": ["mistake1", "mistake2"],
    "recommendations": ["recommendation1", "recommendation2"],
    "confidence_calibration": "analysis of prediction accuracy",
    "risk_assessment": "overall risk management evaluation"
}}
"""
        
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_content)
        ]
        
        response = await self.chat(messages, temperature=0.5)
        
        try:
            return json.loads(self._extract_json(response.content))
        except:
            return {
                "analysis": response.content,
                "error": "Could not parse structured response"
            }
    
    def _extract_json(self, content: str) -> str:
        """Extract JSON from response content."""
        # Try to find JSON block
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            return content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            return content[start:end].strip()
        elif "{" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            return content[start:end]
        return content
    
    def _parse_trading_decision(
        self,
        content: str,
        market_data: Dict[str, Any]
    ) -> TradingDecision:
        """Parse LLM response into TradingDecision."""
        try:
            json_str = self._extract_json(content)
            data = json.loads(json_str)
            
            return TradingDecision(
                action=data.get("action", "HOLD").upper(),
                symbol=data.get("symbol", market_data.get("symbol", "")),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                entry_price=data.get("entry_price"),
                stop_loss=data.get("stop_loss"),
                take_profit=data.get("take_profit"),
                position_size_pct=float(data.get("position_size_pct", 1.0)),
                risk_level=data.get("risk_level", "medium"),
                supporting_indicators=data.get("supporting_indicators", []),
                contra_indicators=data.get("contra_indicators", [])
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse trading decision: {e}")
            return TradingDecision(
                action="HOLD",
                symbol=market_data.get("symbol", ""),
                confidence=0.0,
                reasoning=f"Parse error: {content[:200]}",
                risk_level="high"
            )
