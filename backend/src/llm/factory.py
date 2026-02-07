"""
LLM Factory
Creates appropriate LLM client based on configuration
"""

from typing import Optional
from loguru import logger

from ..config.settings import settings, LLMProvider
from .base import BaseLLMClient
from .openai_client import OpenAIClient


class LLMFactory:
    """
    Factory for creating LLM client instances.
    Supports multiple providers with consistent interface.
    """
    
    _instance: Optional[BaseLLMClient] = None
    
    @classmethod
    def create(
        cls,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> BaseLLMClient:
        """
        Create an LLM client instance.
        
        Args:
            provider: LLM provider (openai/anthropic/ollama/groq)
            model: Model name override
            api_key: API key override
            **kwargs: Additional provider-specific options
            
        Returns:
            LLM client instance
        """
        provider = provider or settings.llm_provider
        model = model or settings.llm_model
        
        if provider == LLMProvider.OPENAI:
            api_key = api_key or settings.openai_api_key
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            
            client = OpenAIClient(
                api_key=api_key,
                model=model,
                **kwargs
            )
            logger.info(f"Created OpenAI client with model: {model}")
            
        elif provider == LLMProvider.ANTHROPIC:
            # Import dynamically to avoid errors if not installed
            try:
                from .anthropic_client import AnthropicClient
                api_key = api_key or settings.anthropic_api_key
                client = AnthropicClient(api_key=api_key, model=model, **kwargs)
                logger.info(f"Created Anthropic client with model: {model}")
            except ImportError:
                raise ImportError("Anthropic client not available")
            
        elif provider == LLMProvider.OLLAMA:
            try:
                from .ollama_client import OllamaClient
                base_url = kwargs.get("base_url", settings.ollama_base_url)
                client = OllamaClient(model=model, base_url=base_url, **kwargs)
                logger.info(f"Created Ollama client with model: {model}")
            except ImportError:
                raise ImportError("Ollama client not available")
            
        elif provider == LLMProvider.GROQ:
            # Groq uses OpenAI-compatible API
            api_key = api_key or settings.groq_api_key
            if not api_key:
                raise ValueError("Groq API key not configured")
            
            client = OpenAIClient(
                api_key=api_key,
                model=model or "mixtral-8x7b-32768",
                base_url="https://api.groq.com/openai/v1",
                **kwargs
            )
            logger.info(f"Created Groq client with model: {model}")
            
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
        
        cls._instance = client
        return client
    
    @classmethod
    def get_instance(cls) -> Optional[BaseLLMClient]:
        """Get the current LLM client instance."""
        return cls._instance
    
    @classmethod
    def get_or_create(cls, **kwargs) -> BaseLLMClient:
        """Get existing instance or create new one."""
        if cls._instance is None:
            return cls.create(**kwargs)
        return cls._instance
