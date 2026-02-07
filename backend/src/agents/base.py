"""
Base Agent Interface
Abstract base class for all trading agents
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid


class AgentType(str, Enum):
    MARKET_DATA = "market_data"
    STRATEGY = "strategy"
    RISK_MANAGER = "risk_manager"
    EXECUTION = "execution"
    MEMORY = "memory"
    BACKTEST = "backtest"
    SUPERVISOR = "supervisor"


class MessageType(str, Enum):
    MARKET_UPDATE = "market_update"
    SIGNAL = "signal"
    DECISION = "decision"
    ORDER = "order"
    EXECUTION = "execution"
    RISK_ALERT = "risk_alert"
    VETO = "veto"
    STATE_UPDATE = "state_update"
    ERROR = "error"


@dataclass
class AgentMessage:
    """
    Structured message for agent communication.
    All agents communicate via JSON-serializable messages.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType = MessageType.STATE_UPDATE
    source_agent: str = ""
    target_agent: Optional[str] = None  # None = broadcast
    timestamp: datetime = field(default_factory=datetime.now)
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1 = highest, 10 = lowest
    requires_response: bool = False
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "priority": self.priority,
            "requires_response": self.requires_response,
            "correlation_id": self.correlation_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=MessageType(data.get("type", "state_update")),
            source_agent=data.get("source_agent", ""),
            target_agent=data.get("target_agent"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            payload=data.get("payload", {}),
            priority=data.get("priority", 5),
            requires_response=data.get("requires_response", False),
            correlation_id=data.get("correlation_id")
        )


@dataclass
class AgentState:
    """Agent runtime state."""
    is_active: bool = True
    last_update: datetime = field(default_factory=datetime.now)
    messages_processed: int = 0
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Abstract base class for all trading agents.
    Each agent is an independent unit with specific responsibilities.
    """
    
    def __init__(
        self,
        name: str,
        agent_type: AgentType,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize base agent.
        
        Args:
            name: Unique agent name
            agent_type: Type of agent
            config: Agent-specific configuration
        """
        self.name = name
        self.agent_type = agent_type
        self.config = config or {}
        self.state = AgentState()
        
        # Message queue
        self._inbox: List[AgentMessage] = []
        self._outbox: List[AgentMessage] = []
        
        # Dependencies (other agents)
        self._dependencies: Dict[str, "BaseAgent"] = {}
        
        # Message handlers
        self._message_handlers: Dict[MessageType, callable] = {}
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the agent.
        Called once before the agent starts processing.
        
        Returns:
            True if initialization successful
        """
        pass
    
    @abstractmethod
    async def process_cycle(self) -> List[AgentMessage]:
        """
        Process one cycle of agent logic.
        Called repeatedly by the supervisor.
        
        Returns:
            List of output messages
        """
        pass
    
    @abstractmethod
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Handle an incoming message.
        
        Args:
            message: Incoming message to process
            
        Returns:
            Optional response message
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanup and shutdown the agent."""
        pass
    
    def register_handler(
        self,
        message_type: MessageType,
        handler: callable
    ) -> None:
        """Register a handler for a message type."""
        self._message_handlers[message_type] = handler
    
    async def receive_message(self, message: AgentMessage) -> None:
        """Add message to inbox."""
        self._inbox.append(message)
        self.state.messages_processed += 1
        self.state.last_update = datetime.now()
    
    def send_message(
        self,
        message_type: MessageType,
        payload: Dict[str, Any],
        target: Optional[str] = None,
        priority: int = 5,
        requires_response: bool = False
    ) -> AgentMessage:
        """Create and queue an outgoing message."""
        message = AgentMessage(
            type=message_type,
            source_agent=self.name,
            target_agent=target,
            payload=payload,
            priority=priority,
            requires_response=requires_response
        )
        self._outbox.append(message)
        return message
    
    def get_pending_messages(self) -> List[AgentMessage]:
        """Get and clear pending inbox messages."""
        messages = sorted(self._inbox, key=lambda m: m.priority)
        self._inbox = []
        return messages
    
    def get_outgoing_messages(self) -> List[AgentMessage]:
        """Get and clear outbox messages."""
        messages = self._outbox.copy()
        self._outbox = []
        return messages
    
    def add_dependency(self, name: str, agent: "BaseAgent") -> None:
        """Add another agent as dependency."""
        self._dependencies[name] = agent
    
    def get_dependency(self, name: str) -> Optional["BaseAgent"]:
        """Get a dependent agent."""
        return self._dependencies.get(name)
    
    def update_metrics(self, **kwargs) -> None:
        """Update agent metrics."""
        self.state.metrics.update(kwargs)
        self.state.last_update = datetime.now()
    
    def log_error(self, error: str) -> None:
        """Log an error."""
        self.state.errors.append(f"{datetime.now().isoformat()}: {error}")
        # Keep only last 100 errors
        if len(self.state.errors) > 100:
            self.state.errors = self.state.errors[-100:]
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status for monitoring."""
        return {
            "name": self.name,
            "type": self.agent_type.value,
            "is_active": self.state.is_active,
            "last_update": self.state.last_update.isoformat(),
            "messages_processed": self.state.messages_processed,
            "error_count": len(self.state.errors),
            "metrics": self.state.metrics
        }
