"""
Angel One Exchange Mapping and Capabilities

Maps exchange codes to Angel-specific types and defines broker capabilities.
"""

import logging
from loguru import logger


class AngelExchangeMapper:
    """Maps OpenAlgo exchange codes to Angel-specific exchange types"""

    # Exchange type mapping for Angel broker
    EXCHANGE_TYPES = {
        "NSE": 1,  # NSE Cash Market
        "NFO": 2,  # NSE Futures & Options
        "BSE": 3,  # BSE Cash Market
        "BFO": 4,  # BSE F&O
        "MCX": 5,  # MCX
        "NCX": 7,  # NCDEX
        "CDS": 13,  # Currency derivatives
        "NSE_INDEX": 1,  # NSE Index
        "BSE_INDEX": 3,  # BSE Index
    }

    @staticmethod
    def get_exchange_type(exchange: str) -> int:
        """
        Convert exchange code to Angel-specific exchange type

        Args:
            exchange (str): Exchange code (e.g., 'NSE', 'BSE')

        Returns:
            int: Angel-specific exchange type
        """
        return AngelExchangeMapper.EXCHANGE_TYPES.get(exchange.upper(), 1)  # Default to NSE
    
    @staticmethod
    def get_exchange_name(exchange_type: int) -> str:
        """
        Convert Angel exchange type to exchange code
        
        Args:
            exchange_type (int): Angel-specific exchange type
            
        Returns:
            str: Exchange code (e.g., 'NSE', 'BSE')
        """
        for name, code in AngelExchangeMapper.EXCHANGE_TYPES.items():
            if code == exchange_type:
                return name
        return "NSE"  # Default


class AngelCapabilityRegistry:
    """
    Registry of Angel broker's capabilities including supported exchanges,
    subscription modes, and market depth levels
    """

    # Angel broker capabilities
    exchanges = ["NSE", "BSE", "BFO", "NFO", "MCX", "CDS"]
    
    # Subscription modes: 1: LTP, 2: Quote, 3: Snap Quote (Depth), 4: Depth 20
    subscription_modes = [1, 2, 3, 4]
    
    depth_support = {
        "NSE": [5, 20],  # NSE supports 5 and 20 levels
        "BSE": [5],  # BSE supports only 5 levels
        "BFO": [5],  # BFO supports only 5 levels
        "NFO": [5, 20],  # NFO supports 5 and 20 levels
        "MCX": [5],  # MCX supports only 5 levels
        "CDS": [5],  # CDS supports only 5 levels
    }

    @classmethod
    def get_supported_depth_levels(cls, exchange: str) -> list:
        """
        Get supported depth levels for an exchange

        Args:
            exchange (str): Exchange code (e.g., 'NSE', 'BSE')

        Returns:
            list: List of supported depth levels (e.g., [5, 20])
        """
        return cls.depth_support.get(exchange.upper(), [5])

    @classmethod
    def is_depth_level_supported(cls, exchange: str, depth_level: int) -> bool:
        """
        Check if a depth level is supported for the given exchange

        Args:
            exchange (str): Exchange code
            depth_level (int): Requested depth level

        Returns:
            bool: True if supported, False otherwise
        """
        supported_depths = cls.get_supported_depth_levels(exchange)
        return depth_level in supported_depths

    @classmethod
    def get_fallback_depth_level(cls, exchange: str, requested_depth: int) -> int:
        """
        Get the best available depth level as a fallback

        Args:
            exchange (str): Exchange code
            requested_depth (int): Requested depth level

        Returns:
            int: Highest supported depth level that is ≤ requested depth
        """
        supported_depths = cls.get_supported_depth_levels(exchange)
        # Find the highest supported depth that's less than or equal to requested depth
        fallbacks = [d for d in supported_depths if d <= requested_depth]
        if fallbacks:
            return max(fallbacks)
        return 5  # Default to basic depth
    
    @classmethod
    def get_mode_name(cls, mode: int) -> str:
        """
        Get human-readable name for subscription mode
        
        Args:
            mode (int): Subscription mode number
            
        Returns:
            str: Mode name
        """
        mode_names = {1: "LTP", 2: "QUOTE", 3: "SNAP_QUOTE", 4: "DEPTH_20"}
        return mode_names.get(mode, "UNKNOWN")
