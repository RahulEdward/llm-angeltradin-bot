"""
Strategy Agent
Generates trading signals using multi-layer strategy filter and LLM reasoning
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from loguru import logger

from .base import BaseAgent, AgentType, AgentMessage, MessageType
from ..llm import LLMFactory, BaseLLMClient, TradingDecision


class StrategyAgent(BaseAgent):
    """Strategy Agent - The Strategist with 4-layer filter."""
    
    def __init__(self, name: str = "StrategyAgent", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, AgentType.STRATEGY, config or {})
        self.use_llm = self.config.get("use_llm", True)
        self.min_confidence = self.config.get("min_confidence", 0.6)
        self._llm: Optional[BaseLLMClient] = None
        self._current_data: Dict[str, Any] = {}
    
    async def initialize(self) -> bool:
        if self.use_llm:
            try:
                self._llm = LLMFactory.get_or_create()
            except:
                self.use_llm = False
        logger.info(f"StrategyAgent initialized (LLM: {self.use_llm})")
        return True
    
    async def process_cycle(self) -> List[AgentMessage]:
        messages = []
        for msg in self.get_pending_messages():
            if msg.type == MessageType.MARKET_UPDATE:
                self._current_data = msg.payload
        
        if not self._current_data:
            return messages
        
        quotes = self._current_data.get("quotes", {})
        indicators = self._current_data.get("indicators", {})
        
        for symbol_key, quote in quotes.items():
            layer_results = self._run_strategy_filter(quote, indicators.get(symbol_key, {}))
            
            if layer_results["all_passed"]:
                decision = await self._get_decision(quote, indicators.get(symbol_key, {}), layer_results)
                if decision.confidence >= self.min_confidence:
                    messages.append(AgentMessage(
                        type=MessageType.SIGNAL,
                        source_agent=self.name,
                        payload={"action": decision.action, "symbol": decision.symbol,
                                 "confidence": decision.confidence, "reasoning": decision.reasoning,
                                 "entry_price": decision.entry_price, "stop_loss": decision.stop_loss,
                                 "take_profit": decision.take_profit, "layers": layer_results},
                        priority=2
                    ))
        return messages
    
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.type == MessageType.MARKET_UPDATE:
            self._current_data = message.payload
        return None
    
    async def shutdown(self) -> None:
        logger.info("StrategyAgent shutdown")
    
    def _run_strategy_filter(self, quote: Dict, indicators: Dict) -> Dict:
        """4-Layer Strategy Filter: Trend → AI → Setup → Trigger"""
        results = {"layer1_trend": False, "layer2_ai": False, "layer3_setup": False,
                   "layer4_trigger": False, "all_passed": False, "direction": "NEUTRAL"}
        
        tf_1h = indicators.get("1h", {})
        tf_15m = indicators.get("15m", {})
        tf_5m = indicators.get("5m", {})
        ltp = quote.get("ltp", 0)
        
        # Layer 1: Trend (1h EMA)
        if tf_1h:
            ema_21 = tf_1h.get("ema_21", ltp)
            results["layer1_trend"] = True
            results["direction"] = "BULLISH" if ltp > ema_21 else "BEARISH"
        
        # Layer 2: AI Filter (RSI alignment)
        if tf_15m and results["layer1_trend"]:
            rsi = tf_15m.get("rsi_14", 50)
            if results["direction"] == "BULLISH":
                results["layer2_ai"] = rsi > 40
            else:
                results["layer2_ai"] = rsi < 60
        
        # Layer 3: Setup (Bollinger entry zone)
        if tf_15m and results["layer2_ai"]:
            bb_mid = tf_15m.get("bb_middle", ltp)
            bb_low = tf_15m.get("bb_lower", ltp * 0.98)
            bb_up = tf_15m.get("bb_upper", ltp * 1.02)
            results["layer3_setup"] = bb_low <= ltp <= bb_up
        
        # Layer 4: Trigger (5m confirmation)
        if tf_5m and results["layer3_setup"]:
            rel_vol = tf_5m.get("relative_volume", 1.0)
            results["layer4_trigger"] = rel_vol > 0.8
        
        results["all_passed"] = all([results["layer1_trend"], results["layer2_ai"],
                                      results["layer3_setup"], results["layer4_trigger"]])
        return results
    
    async def _get_decision(self, quote: Dict, indicators: Dict, layers: Dict) -> TradingDecision:
        if self.use_llm and self._llm:
            try:
                return await self._llm.analyze_market(quote, indicators)
            except Exception as e:
                logger.warning(f"LLM error: {e}")
        
        ltp = quote.get("ltp", 0)
        atr = indicators.get("5m", {}).get("atr_14", ltp * 0.02)
        action = "BUY" if layers["direction"] == "BULLISH" else "SELL"
        
        return TradingDecision(
            action=action, symbol=quote.get("symbol", ""), confidence=0.7,
            reasoning=f"4-layer filter: {layers['direction']}", entry_price=ltp,
            stop_loss=ltp - 1.5*atr if action == "BUY" else ltp + 1.5*atr,
            take_profit=ltp + 2.5*atr if action == "BUY" else ltp - 2.5*atr
        )
