"""
LLM Factory
Creates appropriate LLM client based on configuration.
Supports: OpenAI, DeepSeek, Gemini, Claude (Anthropic), Groq, Ollama.
"""

from typing import Optional
from loguru import logger

from ..config.settings import settings, LLMProvider
from .base import BaseLLMClient
from .openai_client import OpenAIClient


class LLMFactory:
    """Factory for creating LLM client instances."""

    _instance: Optional[BaseLLMClient] = None

    @classmethod
    def create(
        cls,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> BaseLLMClient:
        """Create an LLM client instance."""
        provider = provider or settings.llm_provider
        model = model or settings.llm_model

        if provider == LLMProvider.OPENAI:
            api_key = api_key or settings.openai_api_key
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            client = OpenAIClient(api_key=api_key, model=model, **kwargs)
            logger.info(f"Created OpenAI client: {model}")

        elif provider == LLMProvider.DEEPSEEK:
            from .deepseek_client import DeepSeekClient
            api_key = api_key or settings.deepseek_api_key or settings.openai_api_key
            if not api_key:
                raise ValueError("DeepSeek API key not configured")
            client = DeepSeekClient(api_key=api_key, model=model if model != "gpt-4-turbo-preview" else None, **kwargs)
            logger.info(f"Created DeepSeek client: {client.model}")

        elif provider == LLMProvider.GEMINI:
            from .gemini_client import GeminiClient
            api_key = api_key or settings.gemini_api_key
            if not api_key:
                raise ValueError("Gemini API key not configured")
            client = GeminiClient(api_key=api_key, model=model if model != "gpt-4-turbo-preview" else None, **kwargs)
            logger.info(f"Created Gemini client: {client.model}")

        elif provider == LLMProvider.ANTHROPIC:
            from .claude_client import ClaudeClient
            api_key = api_key or settings.anthropic_api_key
            if not api_key:
                raise ValueError("Anthropic API key not configured")
            client = ClaudeClient(api_key=api_key, model=model if model != "gpt-4-turbo-preview" else None, **kwargs)
            logger.info(f"Created Claude client: {client.model}")

        elif provider == LLMProvider.GROQ:
            api_key = api_key or settings.groq_api_key
            if not api_key:
                raise ValueError("Groq API key not configured")
            client = OpenAIClient(
                api_key=api_key,
                model=model or "mixtral-8x7b-32768",
                base_url="https://api.groq.com/openai/v1",
                provider_name="groq",
                **kwargs
            )
            logger.info(f"Created Groq client: {model}")

        elif provider == LLMProvider.OLLAMA:
            # Ollama uses OpenAI-compatible API
            client = OpenAIClient(
                api_key="ollama",
                model=model or "llama3",
                base_url=settings.ollama_base_url + "/v1",
                provider_name="ollama",
                **kwargs
            )
            logger.info(f"Created Ollama client: {model}")

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

    @classmethod
    def reset(cls):
        """Reset the singleton instance (forces re-creation on next call)."""
        cls._instance = None
