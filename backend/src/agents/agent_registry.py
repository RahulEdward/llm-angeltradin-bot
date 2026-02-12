"""
Agent Registry Module
======================

Centralized registry for agent management.
Provides lazy initialization, enable/disable control, and agent discovery.
"""

from typing import Dict, Optional, Type, Any, List
from loguru import logger
from src.agents.agent_config import AgentConfig


class AgentRegistry:
    """
    Centralized registry for agent management.
    
    Features:
    - Lazy agent initialization
    - Enable/disable control via AgentConfig
    - Agent discovery and listing
    - Dependency-aware initialization
    
    Usage:
        config = AgentConfig.from_dict(yaml_config)
        registry = AgentRegistry(config)
        
        # Register agent classes
        registry.register_class('predict_agent', PredictAgent)
        
        # Get initialized agent (returns None if disabled)
        agent = registry.get('predict_agent')
        if agent:
            result = agent.analyze(input_data)
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self._agent_classes: Dict[str, Type] = {}
        self._agent_instances: Dict[str, Any] = {}
        self._init_args: Dict[str, Dict[str, Any]] = {}
    
    def register_class(
        self, 
        name: str, 
        agent_class: Type,
        init_args: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register an agent class for lazy initialization."""
        self._agent_classes[name] = agent_class
        if init_args:
            self._init_args[name] = init_args
        logger.debug(f"Registered agent class: {name}")
    
    def register_instance(self, name: str, agent: Any) -> None:
        """Register an already-initialized agent instance."""
        self._agent_instances[name] = agent
        logger.debug(f"Registered agent instance: {name}")
    
    def is_enabled(self, name: str) -> bool:
        """Check if an agent is enabled in configuration."""
        return self.config.is_enabled(name)
    
    def get(self, name: str) -> Optional[Any]:
        """
        Get an agent by name. Returns None if disabled or not registered.
        """
        if not self.is_enabled(name):
            logger.debug(f"Agent '{name}' is disabled in config")
            return None
        
        if name in self._agent_instances:
            return self._agent_instances[name]
        
        if name in self._agent_classes:
            return self._initialize_agent(name)
        
        logger.warning(f"Agent '{name}' is not registered")
        return None
    
    def _initialize_agent(self, name: str) -> Optional[Any]:
        """Initialize an agent from registered class."""
        try:
            agent_class = self._agent_classes[name]
            init_args = self._init_args.get(name, {})
            agent = agent_class(**init_args)
            self._agent_instances[name] = agent
            logger.info(f"✅ Initialized agent: {name}")
            return agent
        except Exception as e:
            logger.error(f"Failed to initialize agent '{name}': {e}")
            return None
    
    def initialize_all(self) -> Dict[str, bool]:
        """Initialize all enabled agents."""
        results = {}
        for name in self._agent_classes:
            if self.is_enabled(name):
                agent = self._initialize_agent(name)
                results[name] = agent is not None
            else:
                results[name] = False
                logger.info(f"⏭️ Skipped disabled agent: {name}")
        return results
    
    def list_agents(self, enabled_only: bool = False) -> List[str]:
        """List registered agent names."""
        all_agents = list(set(self._agent_classes.keys()) | set(self._agent_instances.keys()))
        if enabled_only:
            return [name for name in all_agents if self.is_enabled(name)]
        return all_agents
    
    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered agents."""
        status = {}
        for name in self.list_agents():
            status[name] = {
                'enabled': self.is_enabled(name),
                'initialized': name in self._agent_instances,
                'class_registered': name in self._agent_classes,
            }
        return status
    
    def __contains__(self, name: str) -> bool:
        return name in self._agent_classes or name in self._agent_instances
    
    def __len__(self) -> int:
        return len(self.list_agents())
    
    def __repr__(self) -> str:
        enabled = len(self.list_agents(enabled_only=True))
        total = len(self)
        return f"<AgentRegistry(enabled={enabled}/{total})>"
