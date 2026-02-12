"""
LLM Strategy Decision Engine
==============================

Uses the app's LLMFactory to make trading decisions.
Supports bull/bear adversarial perspectives and reflection.

Adapted for Indian equity markets:
- No short-selling
- INR currency references
- Uses LLMFactory.get_or_create() from src.llm.factory
"""

import json
import re
import os
from typing import Dict, Optional
from loguru import logger

from src.strategy.llm_parser import LLMOutputParser
from src.strategy.decision_validator import DecisionValidator


def _extract_json_robust(text: str) -> Optional[Dict]:
    """
    Robustly extract JSON from LLM response text.
    Tries markdown code blocks, then balanced-brace extraction.
    """
    if not text:
        return None

    # Pattern 1: Markdown code block
    md_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if md_match:
        try:
            return json.loads(md_match.group(1))
        except json.JSONDecodeError:
            pass

    # Pattern 2: Balanced JSON object
    start = text.find('{')
    if start != -1:
        depth = 0
        for i, char in enumerate(text[start:], start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


class StrategyEngine:
    """
    Multi-LLM strategy decision engine.
    
    Uses LLMFactory from the app's LLM module for provider-agnostic access.
    Includes bull/bear adversarial perspectives and decision validation.
    """

    def __init__(self):
        self.disable_llm = False
        self.client = None
        self.is_ready = False
        self.parser = LLMOutputParser()
        self.validator = DecisionValidator({
            'max_leverage': 1,
            'max_position_pct': 30.0,
            'min_risk_reward_ratio': 2.0
        })

        disable_env = os.getenv('LLM_DISABLED', '').lower() in ('1', 'true', 'yes', 'on')
        if disable_env:
            self.disable_llm = True
            logger.info("🚫 Strategy Engine LLM disabled by env")
            return

        self._init_client()

    def _init_client(self):
        """Initialize LLM client via LLMFactory."""
        try:
            from src.llm.factory import LLMFactory
            self.client = LLMFactory.get_or_create()
            self.is_ready = True
            logger.info(f"🤖 Strategy Engine initialized (LLMFactory)")
        except Exception as e:
            logger.warning(f"Strategy Engine: Failed to init LLM client: {e}")
            self.is_ready = False

    def make_decision(
        self,
        market_context_text: str,
        market_context_data: Dict,
        reflection: str = None,
        bull_perspective: Dict = None,
        bear_perspective: Dict = None
    ) -> Dict:
        """
        Make a trading decision based on market context.
        
        Args:
            market_context_text: Formatted market context for LLM
            market_context_data: Raw market data dict
            reflection: Optional reflection text from ReflectionAgent
            bull_perspective: Optional bull analysis
            bear_perspective: Optional bear analysis
        
        Returns:
            Decision dict with action, confidence, reasoning, etc.
        """
        if self.disable_llm:
            return self._get_fallback_decision(market_context_data)

        if not self.is_ready:
            self._init_client()
            if not self.is_ready:
                logger.warning("🚫 LLM Strategy Engine not ready. Returning fallback.")
                return self._get_fallback_decision(market_context_data)

        # Get adversarial perspectives if not provided
        if bull_perspective is None:
            logger.info("🐂 Gathering Bull perspective (on-demand)...")
            bull_perspective = self.get_bull_perspective(market_context_text)

        if bear_perspective is None:
            logger.info("🐻 Gathering Bear perspective (on-demand)...")
            bear_perspective = self.get_bear_perspective(market_context_text)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            market_context_text, bull_perspective, bear_perspective, reflection
        )

        try:
            import asyncio
            from src.llm.base import Message, MessageRole
            messages = [
                Message(role=MessageRole.SYSTEM, content=system_prompt),
                Message(role=MessageRole.USER, content=user_prompt)
            ]

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        response = pool.submit(
                            lambda: asyncio.run(self.client.chat(messages))
                        ).result()
                else:
                    response = loop.run_until_complete(self.client.chat(messages))
            except RuntimeError:
                response = asyncio.run(self.client.chat(messages))

            content = response.content

            # Parse structured output
            parsed = self.parser.parse(content)
            decision = parsed['decision']
            reasoning = parsed['reasoning']

            # Normalize action
            if 'action' in decision:
                decision['action'] = self.parser.normalize_action(decision['action'])

            # Validate
            is_valid, errors = self.validator.validate(decision)
            if not is_valid:
                logger.warning(f"LLM decision validation failed: {errors}")
                return self._get_fallback_decision(market_context_data)

            logger.info(f"🤖 LLM Decision: {decision.get('action', 'unknown')} "
                       f"(conf: {decision.get('confidence', 0)}%)")

            # Add metadata
            decision['timestamp'] = market_context_data.get('timestamp')
            decision['symbol'] = market_context_data.get('symbol', 'UNKNOWN')
            decision['raw_response'] = content
            decision['reasoning_detail'] = reasoning
            decision['validation_passed'] = True
            decision['bull_perspective'] = bull_perspective
            decision['bear_perspective'] = bear_perspective

            return decision

        except Exception as e:
            logger.error(f"LLM decision failed: {e}")
            return self._get_fallback_decision(market_context_data)

    def get_bull_perspective(self, market_context_text: str) -> Dict:
        """🐂 Bull Agent: Analyze from bullish perspective."""
        if not self.is_ready or not self.client:
            return {"bullish_reasons": "LLM not ready", "bull_confidence": 50}

        bull_prompt = """You are a BULLISH market analyst for Indian equities. Find reasons WHY the stock could go UP.

Analyze the provided market analysis and identify:
1. Bullish trend & volume signals
2. Bullish AI resonance
3. Bullish setup patterns

Output in this EXACT JSON format:
```json
{
  "stance": "STRONGLY_BULLISH",
  "bullish_reasons": "Key bullish observations separated by semicolons",
  "bull_confidence": 75
}
```

stance: STRONGLY_BULLISH, SLIGHTLY_BULLISH, NEUTRAL, or UNCERTAIN
bull_confidence: 0-100
Focus ONLY on bullish factors."""

        try:
            import asyncio
            from src.llm.base import Message, MessageRole
            messages = [
                Message(role=MessageRole.SYSTEM, content=bull_prompt),
                Message(role=MessageRole.USER, content=market_context_text)
            ]
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        response = pool.submit(
                            lambda: asyncio.run(self.client.chat(messages))
                        ).result()
                else:
                    response = loop.run_until_complete(self.client.chat(messages))
            except RuntimeError:
                response = asyncio.run(self.client.chat(messages))

            result = _extract_json_robust(response.content)
            if result:
                stance = result.get('stance', 'UNKNOWN')
                logger.info(f"🐂 Bull: [{stance}] (Conf: {result.get('bull_confidence', 0)}%)")
                return result

            return {"bullish_reasons": "Unable to analyze", "bull_confidence": 50}
        except Exception as e:
            logger.warning(f"Bull Agent failed: {e}")
            return {"bullish_reasons": "Analysis unavailable", "bull_confidence": 50}

    def get_bear_perspective(self, market_context_text: str) -> Dict:
        """🐻 Bear Agent: Analyze from bearish perspective."""
        if not self.is_ready or not self.client:
            return {"bearish_reasons": "LLM not ready", "bear_confidence": 50}

        bear_prompt = """You are a BEARISH market analyst for Indian equities. Find reasons WHY the stock could go DOWN.

Analyze the provided market analysis and identify:
1. Bearish trend & volume signals
2. Bearish AI divergence
3. Bearish setup patterns

Output in this EXACT JSON format:
```json
{
  "stance": "STRONGLY_BEARISH",
  "bearish_reasons": "Key bearish observations separated by semicolons",
  "bear_confidence": 60
}
```

stance: STRONGLY_BEARISH, SLIGHTLY_BEARISH, NEUTRAL, or UNCERTAIN
bear_confidence: 0-100
Focus ONLY on bearish factors."""

        try:
            import asyncio
            from src.llm.base import Message, MessageRole
            messages = [
                Message(role=MessageRole.SYSTEM, content=bear_prompt),
                Message(role=MessageRole.USER, content=market_context_text)
            ]
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        response = pool.submit(
                            lambda: asyncio.run(self.client.chat(messages))
                        ).result()
                else:
                    response = loop.run_until_complete(self.client.chat(messages))
            except RuntimeError:
                response = asyncio.run(self.client.chat(messages))

            result = _extract_json_robust(response.content)
            if result:
                stance = result.get('stance', 'UNKNOWN')
                logger.info(f"🐻 Bear: [{stance}] (Conf: {result.get('bear_confidence', 0)}%)")
                return result

            return {"bearish_reasons": "Unable to analyze", "bear_confidence": 50}
        except Exception as e:
            logger.warning(f"Bear Agent failed: {e}")
            return {"bearish_reasons": "Analysis unavailable", "bear_confidence": 50}

    def _build_system_prompt(self) -> str:
        """Build system prompt for the decision LLM."""
        # Check for custom prompt
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        custom_prompt_path = os.path.join(base_dir, 'config', 'custom_prompt.md')

        if os.path.exists(custom_prompt_path):
            try:
                with open(custom_prompt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        logger.info("📝 Loading Custom System Prompt")
                        return content
            except Exception as e:
                logger.error(f"Failed to load custom prompt: {e}")

        # Default prompt for Indian equity trading
        return """You are an expert algorithmic trader specializing in Indian equity markets (NSE/BSE).
Your role is to analyze market data and provide actionable trading decisions.

IMPORTANT RULES:
1. Output decisions in valid JSON format inside <decision> tags
2. Indian equities are DELIVERY ONLY — no short-selling, no leverage
3. Valid actions: open_long (buy), close_position (sell), hold, wait
4. Always include stop_loss and take_profit for open_long actions
5. Risk:Reward must be at least 2:1
6. Minimum confidence of 70% for opening positions

Include <reasoning> tags with your analysis before the <decision>.

Output format:
<reasoning>
Your analysis...
</reasoning>

<decision>
```json
[{
  "symbol": "RELIANCE",
  "action": "open_long",
  "confidence": 80,
  "stop_loss": 2400.0,
  "take_profit": 2600.0,
  "position_size_pct": 10,
  "reasoning": "Strong uptrend with volume confirmation"
}]
```
</decision>"""

    def _build_user_prompt(
        self,
        market_context: str,
        bull_perspective: Dict = None,
        bear_perspective: Dict = None,
        reflection: str = None
    ) -> str:
        """Build user prompt with market data and perspectives."""
        adversarial_section = ""
        if bull_perspective or bear_perspective:
            bull_reasons = bull_perspective.get('bullish_reasons', 'N/A') if bull_perspective else 'N/A'
            bull_conf = bull_perspective.get('bull_confidence', 50) if bull_perspective else 50
            bull_stance = bull_perspective.get('stance', 'UNKNOWN') if bull_perspective else 'UNKNOWN'
            bear_reasons = bear_perspective.get('bearish_reasons', 'N/A') if bear_perspective else 'N/A'
            bear_conf = bear_perspective.get('bear_confidence', 50) if bear_perspective else 50
            bear_stance = bear_perspective.get('stance', 'UNKNOWN') if bear_perspective else 'UNKNOWN'

            adversarial_section = f"""
---
## 🐂🐻 Adversarial Analysis

### 🐂 Bull Agent [{bull_stance}] (Confidence: {bull_conf}%)
{bull_reasons}

### 🐻 Bear Agent [{bear_stance}] (Confidence: {bear_conf}%)
{bear_reasons}
"""

        reflection_section = ""
        if reflection:
            reflection_section = f"""
---
## 🧠 Trading Reflection (Recent Trades)

{reflection}
"""

        return f"""# 📊 MARKET DATA INPUT

{market_context}
{adversarial_section}{reflection_section}
---

Analyze the above data following the strategy rules in system prompt. Output your decision."""

    def _get_fallback_decision(self, context: Dict) -> Dict:
        """Conservative fallback when LLM fails."""
        return {
            'action': 'wait',
            'symbol': context.get('symbol', 'UNKNOWN'),
            'confidence': 0,
            'position_size_pct': 0,
            'stop_loss_pct': 1.0,
            'take_profit_pct': 2.0,
            'reasoning': 'LLM decision failed, using conservative fallback strategy',
            'timestamp': context.get('timestamp'),
            'is_fallback': True
        }

    def validate_decision(self, decision: Dict) -> bool:
        """Validate decision format and apply confidence thresholds."""
        required_fields = [
            'action', 'symbol', 'confidence', 'reasoning'
        ]

        for field in required_fields:
            if field not in decision:
                logger.error(f"Decision missing required field: {field}")
                return False

        valid_actions = [
            'open_long', 'close_position', 'hold', 'wait'
        ]
        if decision['action'] not in valid_actions:
            logger.error(f"Invalid action: {decision['action']}")
            return False

        if not (0 <= decision['confidence'] <= 100):
            logger.error(f"Confidence out of range: {decision['confidence']}")
            return False

        # Dynamic confidence threshold
        action = decision['action']
        confidence = decision['confidence']
        regime_threshold = 70  # Default

        reasoning_lower = decision.get('reasoning', '').lower()
        if 'strong trend' in reasoning_lower:
            regime_threshold = 60
        elif 'choppy' in reasoning_lower:
            regime_threshold = 75

        if action == 'open_long' and confidence < regime_threshold:
            logger.warning(
                f"🚫 Confidence {confidence}% < Threshold {regime_threshold}%, "
                f"converting to 'wait'"
            )
            decision['action'] = 'wait'
            decision['reasoning'] = (
                f"Low confidence ({confidence}% < {regime_threshold}% threshold), "
                f"wait for better setup"
            )

        return True
