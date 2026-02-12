"""
Semantic Converter — Converts technical indicator values to natural language.
Used for LLM context input and dashboard display.
Adapted for Indian equity markets (removed crypto-specific OI logic).
"""

from typing import Dict, Optional


class SemanticConverter:
    """
    Converts numeric technical indicator values to human-readable semantic labels.
    Used by LLM prompts and frontend dashboard.
    """

    @staticmethod
    def get_rsi_semantic(rsi: Optional[float]) -> str:
        """RSI semantic conversion."""
        if rsi is None:
            return "N/A (No Data)"
        if rsi >= 80:
            return "Extremely Overbought (Bearish Exhaustion)"
        elif rsi >= 70:
            return "Overbought (Bearish Warning)"
        elif rsi >= 60:
            return "Strong Bullish Momentum"
        elif rsi >= 45:
            return "Neutral (Weak Bullish)"
        elif rsi >= 30:
            return "Bearish Momentum"
        elif rsi >= 20:
            return "Oversold (Bullish Warning)"
        else:
            return "Extremely Oversold (Bullish Exhaustion)"

    @staticmethod
    def get_trend_semantic(score: Optional[float]) -> str:
        """Trend score semantic (-100 to +100)."""
        if score is None:
            return "N/A (No Data)"
        if score >= 60:
            return "Strong Uptrend (Strong Buy)"
        elif score >= 25:
            return "Uptrend (Buy)"
        elif score >= 10:
            return "Weak Uptrend (Accumulation)"
        elif score >= -10:
            return "Sideways (Consolidation)"
        elif score >= -25:
            return "Weak Downtrend (Distribution)"
        elif score >= -60:
            return "Downtrend (Sell)"
        else:
            return "Strong Downtrend (Strong Sell)"

    @staticmethod
    def get_oscillator_semantic(score: Optional[float]) -> str:
        """Oscillator score semantic (-100 to +100)."""
        if score is None:
            return "N/A (No Data)"
        if score >= 80:
            return "Strong Reversal (Buy)"
        elif score >= 40:
            return "Reversal Likely (Buy)"
        elif score >= 10:
            return "Weak Reversal (Watch Buy)"
        elif score >= -10:
            return "Neutral"
        elif score >= -40:
            return "Weak Reversal (Watch Sell)"
        elif score >= -80:
            return "Reversal Likely (Sell)"
        else:
            return "Strong Reversal Signal (Sell)"

    @staticmethod
    def get_sentiment_score_semantic(score: Optional[float]) -> str:
        """Sentiment score semantic (0-100 or -100 to +100)."""
        if score is None:
            return "N/A (No Data)"
        if score >= 60:
            return "Very Bullish"
        elif score >= 20:
            return "Bullish"
        elif score >= -20:
            return "Neutral"
        elif score >= -60:
            return "Bearish"
        else:
            return "Very Bearish"

    @staticmethod
    def get_macd_semantic(value: Optional[float]) -> str:
        """MACD histogram semantic."""
        if value is None:
            return "N/A (No Data)"
        if value > 0.5:
            return "Bullish Divergence (Positive)"
        elif value > 0:
            return "Weak Bullish (Positive)"
        elif value < -0.5:
            return "Bearish Divergence (Negative)"
        elif value < 0:
            return "Weak Bearish (Negative)"
        else:
            return "Neutral (Zero)"

    @staticmethod
    def get_prophet_semantic(probability: Optional[float]) -> str:
        """Prophet prediction probability semantic (0-1 or 0-100)."""
        if probability is None:
            return "N/A (No Data)"
        prob = probability if probability <= 1.0 else probability / 100.0
        if prob >= 0.70:
            return "Strong Bullish"
        elif prob >= 0.55:
            return "Bullish"
        elif prob >= 0.45:
            return "Neutral"
        elif prob >= 0.30:
            return "Bearish"
        else:
            return "Strong Bearish"

    @staticmethod
    def convert_analysis_map(vote_details: Dict[str, float]) -> Dict[str, str]:
        """Convert full vote_details numeric dict to semantic dict."""
        semantic_map = {}

        # Trend scores
        for tf in ("1h", "15m", "5m"):
            key = f"trend_{tf}"
            if key in vote_details:
                semantic_map[key] = SemanticConverter.get_trend_semantic(vote_details[key])

        # Oscillator scores
        for tf in ("1h", "15m", "5m"):
            key = f"oscillator_{tf}"
            if key in vote_details:
                semantic_map[key] = SemanticConverter.get_oscillator_semantic(vote_details[key])

        # Sentiment
        if "sentiment" in vote_details:
            semantic_map["sentiment"] = SemanticConverter.get_sentiment_score_semantic(vote_details["sentiment"])

        # Strategist total
        if "strategist_total" in vote_details:
            score = vote_details["strategist_total"]
            if score > 50:
                semantic_map["strategist_total"] = "Bullish Setup"
            elif score > 20:
                semantic_map["strategist_total"] = "Weak Bullish"
            elif score > -20:
                semantic_map["strategist_total"] = "Neutral"
            elif score > -50:
                semantic_map["strategist_total"] = "Weak Bearish"
            else:
                semantic_map["strategist_total"] = "Bearish Setup"

        # Prophet
        if "prophet" in vote_details:
            semantic_map["prophet"] = SemanticConverter.get_prophet_semantic(vote_details["prophet"])

        return semantic_map
