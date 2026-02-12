"""
Strategy Composer — Four-Layer Strategy Filter
================================================

Centralizes the "Four-Layer Strategy" analysis and LLM context building.
Ensures consistency between live trading and backtesting.

Four Layers:
1. Trend & Fuel (1h) — directional bias + volume confirmation
2. AI Resonance — AI prediction alignment filter
3. Setup (15m) — entry pattern recognition
4. Trigger (5m) — precise entry signal

Adapted for Indian equity markets:
- No short-selling
- Delivery-based trading only
- Uses loguru for logging
"""

import asyncio
from typing import Dict, Optional
from loguru import logger


class StrategyComposer:
    """
    Orchestrates the four-layer strategy analysis.
    
    Initializes and runs trend, setup, trigger, and AI filter analysis,
    then builds context for the decision LLM.
    """

    def __init__(self, use_llm: bool = False):
        """
        Args:
            use_llm: If True, use LLM-based agents; otherwise use rule-based.
        """
        self.use_llm = use_llm

        # Lazy agent references
        self._regime_detector = None
        self._trigger_detector = None
        self._trend_agent = None
        self._setup_agent = None
        self._trigger_agent = None
        self._ai_filter = None
        self._position_analyzer = None
        self._multi_period_parser = None
        self._atr_calculator = None

        self._initialized = False

    def _initialize_agents(self):
        """Lazy-init all agents on first use."""
        if self._initialized:
            return

        try:
            from src.agents.regime_detector import RegimeDetector
            self._regime_detector = RegimeDetector()
        except Exception as e:
            logger.warning(f"RegimeDetector not available: {e}")

        try:
            from src.agents.trigger_detector_agent import TriggerDetectorAgent
            self._trigger_detector = TriggerDetectorAgent()
        except Exception as e:
            logger.warning(f"TriggerDetector not available: {e}")

        try:
            from src.agents.position_analyzer_agent import PositionAnalyzerAgent
            self._position_analyzer = PositionAnalyzerAgent()
        except Exception as e:
            logger.warning(f"PositionAnalyzer not available: {e}")

        try:
            from src.agents.ai_prediction_filter_agent import AIPredictionFilterAgent
            self._ai_filter = AIPredictionFilterAgent()
        except Exception as e:
            logger.warning(f"AIPredictionFilter not available: {e}")

        try:
            from src.agents.multi_period_agent import MultiPeriodParserAgent
            self._multi_period_parser = MultiPeriodParserAgent()
        except Exception as e:
            logger.warning(f"MultiPeriodParser not available: {e}")

        try:
            from src.strategy.atr_calculator import ATRCalculator
            self._atr_calculator = ATRCalculator(period=14)
        except Exception as e:
            logger.warning(f"ATRCalculator not available: {e}")

        # LLM or rule-based agents
        if self.use_llm:
            self._init_llm_agents()
        else:
            self._init_rule_agents()

        self._initialized = True
        logger.info(f"StrategyComposer initialized (LLM={self.use_llm})")

    def _init_llm_agents(self):
        """Initialize LLM-based agents for trend/setup/trigger."""
        try:
            from src.agents.trend_agent import TrendAgentLLM
            self._trend_agent = TrendAgentLLM()
        except Exception as e:
            logger.warning(f"TrendAgentLLM not available, falling back to rule-based: {e}")
            self._init_rule_trend()

        try:
            from src.agents.setup_agent import SetupAgentLLM
            self._setup_agent = SetupAgentLLM()
        except Exception as e:
            logger.warning(f"SetupAgentLLM not available, falling back to rule-based: {e}")
            self._init_rule_setup()

        try:
            from src.agents.trigger_agent import TriggerAgentLLM
            self._trigger_agent = TriggerAgentLLM()
        except Exception as e:
            logger.warning(f"TriggerAgentLLM not available, falling back to rule-based: {e}")
            self._init_rule_trigger()

    def _init_rule_agents(self):
        """Initialize rule-based agents for trend/setup/trigger."""
        self._init_rule_trend()
        self._init_rule_setup()
        self._init_rule_trigger()

    def _init_rule_trend(self):
        try:
            from src.agents.trend_agent import TrendAgentRuleBased
            self._trend_agent = TrendAgentRuleBased()
        except Exception as e:
            logger.warning(f"TrendAgentRuleBased not available: {e}")

    def _init_rule_setup(self):
        try:
            from src.agents.setup_agent import SetupAgentRuleBased
            self._setup_agent = SetupAgentRuleBased()
        except Exception as e:
            logger.warning(f"SetupAgentRuleBased not available: {e}")

    def _init_rule_trigger(self):
        try:
            from src.agents.trigger_agent import TriggerAgentRuleBased
            self._trigger_agent = TriggerAgentRuleBased()
        except Exception as e:
            logger.warning(f"TriggerAgentRuleBased not available: {e}")

    def run_four_layer_analysis(
        self,
        symbol: str,
        df_1h: 'pd.DataFrame' = None,
        df_15m: 'pd.DataFrame' = None,
        df_5m: 'pd.DataFrame' = None,
        ai_prediction: Optional[Dict] = None,
        position_info: Optional[Dict] = None,
    ) -> Dict:
        """
        Run the Four-Layer Strategy analysis.
        
        Args:
            symbol: Trading symbol (e.g., 'RELIANCE')
            df_1h: 1-hour OHLCV DataFrame
            df_15m: 15-minute OHLCV DataFrame
            df_5m: 5-minute OHLCV DataFrame
            ai_prediction: Optional AI prediction results
            position_info: Optional current position info
            
        Returns:
            Analysis dict with all four layers' results
        """
        self._initialize_agents()

        analysis = {
            'symbol': symbol,
            'layers': {},
            'regime': None,
            'atr_analysis': None,
            'position_analysis': None,
            'trigger_patterns': None,
            'multi_period_summary': None,
            'overall_bias': 'neutral',
            'trade_allowed': True,
        }

        # Regime Detection
        if self._regime_detector and df_1h is not None:
            try:
                regime = self._regime_detector.detect(df_1h)
                analysis['regime'] = regime
                logger.debug(f"[{symbol}] Regime: {regime}")
            except Exception as e:
                logger.warning(f"Regime detection failed: {e}")

        # ATR Analysis
        if self._atr_calculator and df_1h is not None:
            try:
                analysis['atr_analysis'] = self._atr_calculator.get_analysis(df_1h)
            except Exception as e:
                logger.warning(f"ATR analysis failed: {e}")

        # Layer 1: Trend & Fuel (1h)
        if self._trend_agent and df_1h is not None:
            try:
                if hasattr(self._trend_agent, 'analyze'):
                    trend_result = self._trend_agent.analyze(df_1h, symbol)
                    if asyncio.iscoroutine(trend_result):
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                import concurrent.futures
                                with concurrent.futures.ThreadPoolExecutor() as pool:
                                    trend_result = pool.submit(
                                        lambda: asyncio.run(trend_result)
                                    ).result()
                            else:
                                trend_result = loop.run_until_complete(trend_result)
                        except RuntimeError:
                            trend_result = asyncio.run(trend_result)
                    analysis['layers']['trend'] = trend_result
                    logger.debug(f"[{symbol}] Layer 1 (Trend): {trend_result.get('bias', 'N/A')}")
            except Exception as e:
                logger.warning(f"Trend analysis failed: {e}")

        # Layer 2: AI Resonance Filter
        if self._ai_filter and ai_prediction:
            try:
                ai_filter_result = self._ai_filter.analyze(
                    prediction=ai_prediction,
                    trend_bias=analysis['layers'].get('trend', {}).get('bias', 'neutral')
                )
                analysis['layers']['ai_filter'] = ai_filter_result
                if ai_filter_result.get('veto'):
                    analysis['trade_allowed'] = False
                    logger.info(f"[{symbol}] AI Filter VETO: {ai_filter_result.get('reason')}")
            except Exception as e:
                logger.warning(f"AI filter failed: {e}")

        # Layer 3: Setup (15m)
        if self._setup_agent and df_15m is not None:
            try:
                if hasattr(self._setup_agent, 'analyze'):
                    setup_result = self._setup_agent.analyze(df_15m, symbol)
                    if asyncio.iscoroutine(setup_result):
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                import concurrent.futures
                                with concurrent.futures.ThreadPoolExecutor() as pool:
                                    setup_result = pool.submit(
                                        lambda: asyncio.run(setup_result)
                                    ).result()
                            else:
                                setup_result = loop.run_until_complete(setup_result)
                        except RuntimeError:
                            setup_result = asyncio.run(setup_result)
                    analysis['layers']['setup'] = setup_result
                    logger.debug(f"[{symbol}] Layer 3 (Setup): {setup_result.get('pattern', 'N/A')}")
            except Exception as e:
                logger.warning(f"Setup analysis failed: {e}")

        # Layer 4: Trigger (5m)
        if self._trigger_agent and df_5m is not None:
            try:
                if hasattr(self._trigger_agent, 'analyze'):
                    trigger_result = self._trigger_agent.analyze(df_5m, symbol)
                    if asyncio.iscoroutine(trigger_result):
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                import concurrent.futures
                                with concurrent.futures.ThreadPoolExecutor() as pool:
                                    trigger_result = pool.submit(
                                        lambda: asyncio.run(trigger_result)
                                    ).result()
                            else:
                                trigger_result = loop.run_until_complete(trigger_result)
                        except RuntimeError:
                            trigger_result = asyncio.run(trigger_result)
                    analysis['layers']['trigger'] = trigger_result
                    logger.debug(f"[{symbol}] Layer 4 (Trigger): {trigger_result.get('signal', 'N/A')}")
            except Exception as e:
                logger.warning(f"Trigger analysis failed: {e}")

        # Trigger Detector (5m patterns)
        if self._trigger_detector and df_5m is not None:
            try:
                patterns = self._trigger_detector.detect(df_5m)
                analysis['trigger_patterns'] = patterns
            except Exception as e:
                logger.warning(f"Trigger detector failed: {e}")

        # Position Analyzer
        if self._position_analyzer and position_info:
            try:
                price = df_5m['close'].iloc[-1] if df_5m is not None and len(df_5m) > 0 else 0
                pos_analysis = self._position_analyzer.analyze(
                    current_price=price,
                    entry_price=position_info.get('entry_price', 0),
                    stop_loss=position_info.get('stop_loss', 0),
                    take_profit=position_info.get('take_profit', 0),
                )
                analysis['position_analysis'] = pos_analysis
            except Exception as e:
                logger.warning(f"Position analysis failed: {e}")

        # Determine overall bias
        analysis['overall_bias'] = self._determine_overall_bias(analysis)

        return analysis

    def _determine_overall_bias(self, analysis: Dict) -> str:
        """Determine overall market bias from all layers."""
        trend = analysis['layers'].get('trend', {})
        setup = analysis['layers'].get('setup', {})
        trigger = analysis['layers'].get('trigger', {})

        biases = []
        if trend.get('bias'):
            biases.append(trend['bias'])
        if setup.get('bias'):
            biases.append(setup['bias'])
        if trigger.get('bias'):
            biases.append(trigger['bias'])

        if not biases:
            return 'neutral'

        bullish = sum(1 for b in biases if b in ('bullish', 'long'))
        bearish = sum(1 for b in biases if b in ('bearish', 'short'))

        if bullish > bearish:
            return 'bullish'
        elif bearish > bullish:
            return 'bearish'
        return 'neutral'

    def build_market_context(self, analysis: Dict) -> str:
        """
        Build a human-readable market context string from analysis.
        This becomes the input to the decision LLM.
        """
        symbol = analysis.get('symbol', 'UNKNOWN')
        regime = analysis.get('regime')
        atr = analysis.get('atr_analysis', {})
        layers = analysis.get('layers', {})

        lines = [
            f"## Four-Layer Strategy Analysis — {symbol}",
            f"**Overall Bias**: {analysis.get('overall_bias', 'neutral').upper()}",
            f"**Trade Allowed**: {'Yes' if analysis.get('trade_allowed', True) else 'No (AI Veto)'}",
            "",
        ]

        if regime:
            lines.append(f"### Market Regime")
            lines.append(f"- Regime: {regime.get('regime', 'N/A')}")
            lines.append(f"- Confidence: {regime.get('confidence', 'N/A')}%")
            lines.append("")

        if atr:
            lines.append(f"### ATR Analysis")
            lines.append(f"- ATR: ₹{atr.get('atr', 0):.2f} ({atr.get('atr_pct', 0):.2f}%)")
            lines.append(f"- Volatility: {atr.get('volatility', 'N/A')}")
            lines.append(f"- TP/SL Multiplier: {atr.get('multiplier', 1.0):.2f}x")
            lines.append("")

        # Layer 1: Trend
        trend = layers.get('trend', {})
        if trend:
            lines.append("### Layer 1: Trend & Fuel (1h)")
            lines.append(f"- Bias: {trend.get('bias', 'N/A')}")
            lines.append(f"- Strength: {trend.get('strength', 'N/A')}")
            lines.append(f"- Volume Confirmation: {trend.get('volume_confirmed', 'N/A')}")
            if trend.get('reasoning'):
                lines.append(f"- Detail: {trend['reasoning'][:200]}")
            lines.append("")

        # Layer 2: AI Filter
        ai_filter = layers.get('ai_filter', {})
        if ai_filter:
            lines.append("### Layer 2: AI Resonance")
            lines.append(f"- Aligned: {ai_filter.get('aligned', 'N/A')}")
            lines.append(f"- Veto: {ai_filter.get('veto', False)}")
            if ai_filter.get('reason'):
                lines.append(f"- Reason: {ai_filter['reason']}")
            lines.append("")

        # Layer 3: Setup
        setup = layers.get('setup', {})
        if setup:
            lines.append("### Layer 3: Setup (15m)")
            lines.append(f"- Pattern: {setup.get('pattern', 'N/A')}")
            lines.append(f"- Bias: {setup.get('bias', 'N/A')}")
            lines.append(f"- Quality: {setup.get('quality', 'N/A')}")
            if setup.get('reasoning'):
                lines.append(f"- Detail: {setup['reasoning'][:200]}")
            lines.append("")

        # Layer 4: Trigger
        trigger = layers.get('trigger', {})
        if trigger:
            lines.append("### Layer 4: Trigger (5m)")
            lines.append(f"- Signal: {trigger.get('signal', 'N/A')}")
            lines.append(f"- Bias: {trigger.get('bias', 'N/A')}")
            lines.append(f"- Confidence: {trigger.get('confidence', 'N/A')}%")
            if trigger.get('reasoning'):
                lines.append(f"- Detail: {trigger['reasoning'][:200]}")
            lines.append("")

        # Trigger patterns
        patterns = analysis.get('trigger_patterns')
        if patterns:
            lines.append("### 5m Pattern Detections")
            for p in (patterns if isinstance(patterns, list) else [patterns]):
                lines.append(f"- {p.get('pattern', 'N/A')} "
                           f"(strength: {p.get('strength', 'N/A')})")
            lines.append("")

        # Position analysis
        pos = analysis.get('position_analysis')
        if pos:
            lines.append("### Position Analysis")
            lines.append(f"- Location: {pos.get('location', 'N/A')}")
            lines.append(f"- Quality: {pos.get('quality', 'N/A')}")
            lines.append("")

        return "\n".join(lines)
