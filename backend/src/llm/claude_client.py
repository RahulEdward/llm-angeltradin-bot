"""
Anthropic Claude LLM Client
Uses Anthropic's Messages API (different format from OpenAI).
"""

import json
import time
from typing import List, Dict, Any, Optional
from loguru import logger

try:
    import httpx
except ImportError:
    httpx = None

from .base import (
    BaseLLMClient, Message, LLMResponse, TradingDecision, MessageRole
)
from . import metrics as llm_metrics


class ClaudeClient(BaseLLMClient):
    """Anthropic Claude API client for trading analysis."""

    PROVIDER = "claude"
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    BASE_URL = "https://api.anthropic.com/v1"
    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(
        self,
        api_key: str,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ):
        super().__init__(model or self.DEFAULT_MODEL, temperature, max_tokens)
        self.api_key = api_key
        if httpx is None:
            raise ImportError("httpx not installed. Run: pip install httpx")
        self._client = httpx.AsyncClient(timeout=60)

    async def chat(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Send chat to Anthropic Messages API."""
        llm_metrics.record_request(self.PROVIDER, self.model)
        start_time = time.time()

        try:
            # Separate system from user/assistant messages
            system_content = ""
            user_messages = []
            for msg in messages:
                if msg.role == MessageRole.SYSTEM:
                    system_content = msg.content
                else:
                    user_messages.append({
                        "role": msg.role.value,
                        "content": msg.content
                    })

            body: Dict[str, Any] = {
                "model": self.model,
                "messages": user_messages,
                "max_tokens": max_tokens or self.max_tokens,
            }
            if system_content:
                body["system"] = system_content

            temp = temperature or self.temperature
            if temp > 0:
                body["temperature"] = max(0.1, temp)  # Claude min is 0.1

            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": self.ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            }

            url = f"{self.BASE_URL}/messages"
            response = await self._client.post(url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()

            latency_ms = int((time.time() - start_time) * 1000)

            # Parse response
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content = block.get("text", "")
                    break

            usage_data = data.get("usage", {})
            prompt_tokens = usage_data.get("input_tokens", 0)
            completion_tokens = usage_data.get("output_tokens", 0)
            total_tokens = prompt_tokens + completion_tokens

            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
            llm_metrics.record_success(self.PROVIDER, self.model, latency_ms, usage)

            return LLMResponse(
                content=content,
                model=data.get("model", self.model),
                tokens_used=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                finish_reason=data.get("stop_reason", "end_turn"),
                raw_response=data,
            )

        except Exception as e:
            llm_metrics.record_error(self.PROVIDER, self.model, str(e))
            logger.error(f"Claude chat error: {e}")
            raise

    async def analyze_market(self, market_data, indicators, context=None):
        """Delegate to chat with a market analysis prompt."""
        import json as _json
        prompt = f"Analyze market data for {market_data.get('symbol', 'Unknown')}: Price={market_data.get('ltp', 0)}, Indicators={_json.dumps(indicators, default=str)[:500]}"
        messages = [
            Message(role=MessageRole.SYSTEM, content=self._build_system_prompt("trader")),
            Message(role=MessageRole.USER, content=prompt),
        ]
        response = await self.chat(messages, temperature=0.3)
        return self._parse_decision_from_content(response.content, market_data)

    def _parse_decision_from_content(self, content: str, market_data: Dict) -> TradingDecision:
        """Parse trading decision from LLM response."""
        try:
            json_str = content
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                json_str = content[start:end].strip()
            elif "{" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                json_str = content[start:end]
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
            )
        except Exception:
            return TradingDecision(
                action="HOLD", symbol=market_data.get("symbol", ""),
                confidence=0.0, reasoning=f"Parse error: {content[:200]}",
                risk_level="high",
            )
