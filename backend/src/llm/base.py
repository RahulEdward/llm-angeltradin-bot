"""
Base LLM Client Interface
Abstract base class for LLM provider implementations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """Chat message structure"""
    role: MessageRole
    content: str


@dataclass
class LLMResponse:
    """LLM response structure"""
    content: str
    model: str
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = "stop"
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class TradingDecision:
    """Structured trading decision from LLM"""
    action: str  # BUY, SELL, HOLD
    symbol: str
    confidence: float  # 0-1
    reasoning: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size_pct: float = 1.0
    timeframe: str = "5m"
    risk_level: str = "medium"
    supporting_indicators: List[str] = field(default_factory=list)
    contra_indicators: List[str] = field(default_factory=list)


class BaseLLMClient(ABC):
    """
    Abstract base class for LLM clients.
    Provides consistent interface across different LLM providers.
    """
    
    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Send chat messages and get response.
        
        Args:
            messages: List of messages in the conversation
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            LLMResponse with content and metadata
        """
        pass
    
    @abstractmethod
    async def analyze_market(
        self,
        market_data: Dict[str, Any],
        indicators: Dict[str, Any],
        context: Optional[str] = None
    ) -> TradingDecision:
        """
        Analyze market data and return trading decision.
        
        Args:
            market_data: OHLCV data and current prices
            indicators: Technical indicators
            context: Additional context (news, events, etc.)
            
        Returns:
            Structured TradingDecision
        """
        pass
    
    @abstractmethod
    async def get_bull_perspective(
        self,
        market_data: Dict[str, Any],
        indicators: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get bullish perspective on the market."""
        pass
    
    @abstractmethod
    async def get_bear_perspective(
        self,
        market_data: Dict[str, Any],
        indicators: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get bearish perspective on the market."""
        pass
    
    @abstractmethod
    async def synthesize_decision(
        self,
        bull_view: Dict[str, Any],
        bear_view: Dict[str, Any],
        quant_signals: Dict[str, Any]
    ) -> TradingDecision:
        """
        Synthesize bull/bear perspectives into final decision.
        
        Args:
            bull_view: Bullish analysis
            bear_view: Bearish analysis
            quant_signals: Quantitative signals
            
        Returns:
            Final TradingDecision
        """
        pass
    
    @abstractmethod
    async def reflect_on_trades(
        self,
        trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Reflect on past trades for learning.
        
        Args:
            trade_history: Recent trade history
            
        Returns:
            Reflection insights and recommendations
        """
        pass
    
    def _build_system_prompt(self, role: str = "trader") -> str:
        """Build system prompt for trading analysis."""
        prompts = {
            "trader": """You are an expert algorithmic trader specializing in Indian markets.
Your role is to analyze market data and provide actionable trading decisions.

IMPORTANT RULES:
1. Always output decisions in valid JSON format
2. Never recommend trades without clear reasoning
3. Consider risk management in every decision
4. Use technical and quantitative analysis
5. Acknowledge uncertainty when present

Your decisions must include:
- action: "BUY", "SELL", or "HOLD"
- confidence: 0.0 to 1.0
- reasoning: Clear explanation
- risk_level: "low", "medium", or "high"
""",
            "bull": """You are a bullish market analyst for Indian markets.
Your role is to find reasons WHY the market or stock should go UP.
Focus on:
- Positive technical patterns
- Strong momentum indicators
- Supportive price action
- Favorable market conditions

Always present the strongest bullish case possible while remaining objective.
Output your analysis in JSON format.
""",
            "bear": """You are a bearish market analyst for Indian markets.
Your role is to find reasons WHY the market or stock should go DOWN.
Focus on:
- Negative technical patterns
- Weakening momentum
- Resistance levels
- Risk factors

Always present the strongest bearish case possible while remaining objective.
Output your analysis in JSON format.
""",
            "risk": """You are a risk management expert for trading systems.
Your role is to evaluate trade proposals and identify risks.
Consider:
- Position sizing
- Stop loss placement
- Market volatility
- Portfolio exposure
- Correlation risks

You have VETO power over trades that exceed risk parameters.
Output your assessment in JSON format.
"""
        }
        return prompts.get(role, prompts["trader"])
