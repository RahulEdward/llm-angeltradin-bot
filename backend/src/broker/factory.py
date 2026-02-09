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
    
    Paper mode uses real market data from connected broker but simulates order execution.
    Live mode uses the connected broker for both data and execution.
    """
    
    _instance: Optional[BaseBroker] = None
    _data_broker: Optional[AngelOneBroker] = None
    _connected_broker: Optional[AngelOneBroker] = None  # Broker from Settings connection
    
    @classmethod
    def set_connected_broker(cls, broker: AngelOneBroker) -> None:
        """Set the connected broker instance (from Settings TOTP connection)."""
        cls._connected_broker = broker
        cls._data_broker = broker  # Use for data too
        logger.info("Connected broker set in factory")
    
    @classmethod
    def create(
        cls,
        mode: Optional[TradingMode] = None,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        password: Optional[str] = None,
        totp_secret: Optional[str] = None
    ) -> Optional[BaseBroker]:
        """
        Create a broker instance based on trading mode.
        Reuses existing instance if same mode and already created.
        """
        mode = mode or settings.trading_mode
        
        # ALWAYS reuse existing instance for paper mode
        if cls._instance is not None:
            from .paper_broker import PaperBroker
            if mode == TradingMode.PAPER and isinstance(cls._instance, PaperBroker):
                logger.debug(f"Reusing existing PaperBroker id={id(cls._instance)}")
                return cls._instance
            if mode == TradingMode.LIVE and isinstance(cls._instance, AngelOneBroker):
                return cls._instance
            if mode == TradingMode.BACKTEST and isinstance(cls._instance, PaperBroker):
                return cls._instance
        
        if mode == TradingMode.LIVE:
            logger.info("Creating LIVE trading broker")
            # For live mode, we need a connected broker
            if cls._connected_broker:
                broker = cls._connected_broker
            else:
                # Try to create from settings
                api_key = api_key or settings.angel_api_key
                client_id = client_id or settings.angel_client_id
                password = password or settings.angel_password
                totp_secret = totp_secret or settings.angel_totp_secret
                
                if api_key and client_id:
                    if cls._data_broker is None:
                        cls._data_broker = AngelOneBroker(
                            api_key=api_key,
                            client_id=client_id,
                            password=password,
                            totp_secret=totp_secret
                        )
                    broker = cls._data_broker
                else:
                    logger.warning("No broker credentials available for LIVE mode")
                    broker = None
            
        elif mode == TradingMode.PAPER:
            logger.info("Creating PAPER trading broker")
            # Paper mode uses real data broker for market data, simulates orders
            if cls._connected_broker:
                broker = PaperBroker(
                    data_broker=cls._connected_broker,
                    initial_capital=settings.max_position_size * 10
                )
            elif cls._data_broker:
                broker = PaperBroker(
                    data_broker=cls._data_broker,
                    initial_capital=settings.max_position_size * 10
                )
            else:
                # No broker connected - standalone paper mode with simulated data
                logger.info("No broker connected - creating standalone paper broker (simulated data)")
                broker = PaperBroker(
                    data_broker=None,
                    initial_capital=settings.max_position_size * 10
                )
            
        else:  # BACKTEST mode
            logger.info("Creating BACKTEST broker")
            # Backtest uses paper broker with data broker for historical data
            if cls._connected_broker:
                broker = PaperBroker(
                    data_broker=cls._connected_broker,
                    initial_capital=settings.max_position_size * 10
                )
            elif cls._data_broker:
                broker = PaperBroker(
                    data_broker=cls._data_broker,
                    initial_capital=settings.max_position_size * 10
                )
            else:
                logger.warning("No broker connected - backtest mode will have limited functionality")
                broker = None
        
        cls._instance = broker
        return broker
    
    @classmethod
    def get_instance(cls) -> Optional[BaseBroker]:
        """Get the current broker instance, creating if needed."""
        if cls._instance is None:
            cls.create()
        return cls._instance
    
    @classmethod
    def get_data_broker(cls) -> Optional[AngelOneBroker]:
        """Get the data broker for market data access."""
        return cls._connected_broker or cls._data_broker
    
    @classmethod
    def get_connected_broker(cls) -> Optional[AngelOneBroker]:
        """Get the connected broker instance."""
        return cls._connected_broker
    
    @classmethod
    async def shutdown(cls) -> None:
        """Shutdown all broker connections."""
        if cls._instance:
            await cls._instance.disconnect()
            cls._instance = None
        
        if cls._data_broker and cls._data_broker != cls._connected_broker:
            await cls._data_broker.disconnect()
            cls._data_broker = None
        
        if cls._connected_broker:
            await cls._connected_broker.disconnect()
            cls._connected_broker = None
        
        logger.info("All broker connections closed")
