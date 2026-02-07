"""
Broker Factory
Creates appropriate broker instance based on trading mode
"""

from typing import Optional
from loguru import logger

from ..config.settings import settings, TradingMode
from .base import BaseBroker
from .angel_one import AngelOneBroker
from .paper_broker import PaperBroker


class BrokerFactory:
    """
    Factory for creating broker instances based on trading mode.
    Ensures execution layer doesn't know whether it's live or paper.
    """
    
    _instance: Optional[BaseBroker] = None
    _data_broker: Optional[AngelOneBroker] = None
    
    @classmethod
    def create(
        cls,
        mode: Optional[TradingMode] = None,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        password: Optional[str] = None,
        totp_secret: Optional[str] = None
    ) -> BaseBroker:
        """
        Create a broker instance based on trading mode.
        
        Args:
            mode: Trading mode (live/paper/backtest)
            api_key: Angel One API key (optional, uses settings if not provided)
            client_id: Trading client ID
            password: Trading password
            totp_secret: TOTP secret for 2FA
            
        Returns:
            Appropriate broker implementation
        """
        # Use provided values or fall back to settings
        mode = mode or settings.trading_mode
        api_key = api_key or settings.angel_api_key
        client_id = client_id or settings.angel_client_id
        password = password or settings.angel_password
        totp_secret = totp_secret or settings.angel_totp_secret
        
        # Create data broker for market data (shared across modes)
        if cls._data_broker is None:
            cls._data_broker = AngelOneBroker(
                api_key=api_key,
                client_id=client_id,
                password=password,
                totp_secret=totp_secret
            )
        
        if mode == TradingMode.LIVE:
            logger.info("Creating LIVE trading broker")
            broker = cls._data_broker
            
        elif mode == TradingMode.PAPER:
            logger.info("Creating PAPER trading broker")
            broker = PaperBroker(
                data_broker=cls._data_broker,
                initial_capital=settings.max_position_size * 10
            )
            
        else:  # BACKTEST mode
            logger.info("Creating BACKTEST broker (paper mode with historical data)")
            broker = PaperBroker(
                data_broker=cls._data_broker,
                initial_capital=settings.max_position_size * 10
            )
        
        cls._instance = broker
        return broker
    
    @classmethod
    def get_instance(cls) -> Optional[BaseBroker]:
        """Get the current broker instance."""
        return cls._instance
    
    @classmethod
    def get_data_broker(cls) -> Optional[AngelOneBroker]:
        """Get the data broker for market data access."""
        return cls._data_broker
    
    @classmethod
    async def shutdown(cls) -> None:
        """Shutdown all broker connections."""
        if cls._instance:
            await cls._instance.disconnect()
            cls._instance = None
        
        if cls._data_broker:
            await cls._data_broker.disconnect()
            cls._data_broker = None
        
        logger.info("All broker connections closed")
