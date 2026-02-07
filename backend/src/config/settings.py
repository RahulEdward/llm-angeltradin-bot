"""
Application Configuration Settings
Centralized configuration management using Pydantic Settings
"""

from enum import Enum
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(str, Enum):
    """Trading mode enumeration"""
    LIVE = "live"
    PAPER = "paper"
    BACKTEST = "backtest"


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    GROQ = "groq"


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Platform Mode
    trading_mode: TradingMode = Field(default=TradingMode.PAPER)
    
    # Angel One SmartAPI
    angel_api_key: str = Field(default="")
    angel_client_id: str = Field(default="")
    angel_password: str = Field(default="")
    angel_totp_secret: str = Field(default="")
    
    # LLM Configuration
    llm_provider: LLMProvider = Field(default=LLMProvider.OPENAI)
    llm_model: str = Field(default="gpt-4-turbo-preview")
    openai_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)
    ollama_base_url: str = Field(default="http://localhost:11434")
    groq_api_key: Optional[str] = Field(default=None)
    
    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/trading.db"
    )
    
    # Security
    secret_key: str = Field(default="change-this-secret-key")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=1440)
    
    # Risk Management
    max_position_size: float = Field(default=100000.0)
    max_daily_loss: float = Field(default=10000.0)
    max_trades_per_day: int = Field(default=20)
    default_stop_loss_pct: float = Field(default=2.0)
    default_take_profit_pct: float = Field(default=4.0)
    kill_switch_enabled: bool = Field(default=True)
    
    # Agent Configuration
    agent_market_data: bool = Field(default=True)
    agent_strategy: bool = Field(default=True)
    agent_risk_manager: bool = Field(default=True)
    agent_execution: bool = Field(default=True)
    agent_memory: bool = Field(default=True)
    agent_backtest: bool = Field(default=True)
    agent_supervisor: bool = Field(default=True)
    
    # Server Configuration
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000"
    )
    
    # Logging
    log_level: str = Field(default="INFO")
    log_to_file: bool = Field(default=True)
    log_retention_days: int = Field(default=30)
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def is_live_mode(self) -> bool:
        """Check if running in live trading mode"""
        return self.trading_mode == TradingMode.LIVE
    
    @property
    def is_paper_mode(self) -> bool:
        """Check if running in paper trading mode"""
        return self.trading_mode == TradingMode.PAPER
    
    @property
    def is_backtest_mode(self) -> bool:
        """Check if running in backtest mode"""
        return self.trading_mode == TradingMode.BACKTEST


# Global settings instance
settings = Settings()
