"""
DeepSeek LLM Client
Uses OpenAI-compatible API — just different base_url and default model.
"""

from .openai_client import OpenAIClient


class DeepSeekClient(OpenAIClient):
    """DeepSeek client — inherits OpenAI client with different defaults."""

    PROVIDER = "deepseek"
    DEFAULT_BASE_URL = "https://api.deepseek.com"
    DEFAULT_MODEL = "deepseek-chat"

    def __init__(self, api_key: str, model: str = None, **kwargs):
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=kwargs.pop("base_url", self.DEFAULT_BASE_URL),
            provider_name=self.PROVIDER,
            **kwargs
        )
