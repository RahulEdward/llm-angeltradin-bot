"""
Reflection Agent - The Philosopher
===================================
Trading retrospection every N trades.
Supports both rule-based and LLM-based reflection.
Adapted for Indian equity markets (INR currency, delivery focus).

Two classes:
  - ReflectionAgent: Rule-based analysis (no external dependency)
  - ReflectionAgentLLM: LLM-powered deep analysis via LLMFactory
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
import json
import os
from loguru import logger


@dataclass
class ReflectionResult:
    """Result of a reflection analysis."""
    reflection_id: str = ""
    trades_analyzed: int = 0
    timestamp: str = ""
    summary: str = ""
    patterns: Dict[str, List[str]] = field(
        default_factory=lambda: {"winning_conditions": [], "losing_conditions": []}
    )
    recommendations: List[str] = field(default_factory=list)
    confidence_calibration: str = ""
    market_insights: str = ""
    raw_response: str = ""            # Raw LLM response (for debugging)
    source: str = "rule_based"        # "rule_based" or "llm"

    def to_prompt_text(self) -> str:
        """Format reflection for use as LLM context in future prompts."""
        lines = [f"**Summary**: {self.summary}", ""]
        lines.append("**Winning Patterns**:")
        for p in self.patterns.get("winning_conditions", [])[:3]:
            lines.append(f"  - {p}")
        lines.append("")
        lines.append("**Losing Patterns**:")
        for p in self.patterns.get("losing_conditions", [])[:3]:
            lines.append(f"  - {p}")
        lines.append("")
        lines.append("**Recommendations**:")
        for r in self.recommendations[:3]:
            lines.append(f"  - {r}")
        lines.append("")
        lines.append(f"**Confidence Calibration**: {self.confidence_calibration}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reflection_id": self.reflection_id,
            "trades_analyzed": self.trades_analyzed,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "patterns": self.patterns,
            "recommendations": self.recommendations,
            "confidence_calibration": self.confidence_calibration,
            "market_insights": self.market_insights,
            "source": self.source,
        }


# ============================================
# Rule-Based Reflection Agent
# ============================================
class ReflectionAgent:
    """
    The Philosopher — Rule-based trade retrospection agent.
    Analyzes completed trades every N trades and provides insights.
    No LLM dependency; pure statistics and heuristics.
    """

    TRIGGER_COUNT = 10

    def __init__(self):
        self.reflection_count = 0
        self.last_reflected_count = 0
        self.last_reflection: Optional[ReflectionResult] = None
        logger.info("ReflectionAgent (The Philosopher) initialized — rule-based mode")

    def should_reflect(self, total_trades: int) -> bool:
        return (total_trades - self.last_reflected_count) >= self.TRIGGER_COUNT

    async def generate_reflection(self, trades: List[Dict]) -> Optional[ReflectionResult]:
        """Generate reflection from trade history (rule-based)."""
        if not trades or len(trades) < 3:
            return None
        return self._rule_based_reflection(trades)

    def _rule_based_reflection(self, trades: List[Dict]) -> ReflectionResult:
        """Pure rule-based trade analysis."""
        wins, losses = 0, 0
        win_pnls, loss_pnls = [], []
        pnls = []

        for t in trades:
            pnl = self._extract_pnl(t)
            pnls.append(pnl)
            if pnl > 0:
                wins += 1
                win_pnls.append(pnl)
            elif pnl < 0:
                losses += 1
                loss_pnls.append(abs(pnl))

        total = wins + losses if (wins + losses) > 0 else len(trades)
        win_rate = (wins / total * 100) if total > 0 else 0
        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
        avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0
        total_pnl = sum(pnls)

        # Profit factor
        gross_profit = sum(win_pnls)
        gross_loss = sum(loss_pnls)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Max drawdown
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnls:
            cumulative += p
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        # Consecutive losses
        max_consec_loss = 0
        consec = 0
        for p in pnls:
            if p < 0:
                consec += 1
                max_consec_loss = max(max_consec_loss, consec)
            else:
                consec = 0

        winning = []
        losing = []
        recommendations = []

        if win_rate >= 55:
            winning.append("Win rate above 55% — current filters are effective")
        if avg_win > avg_loss and avg_win > 0:
            winning.append(f"Average win (₹{avg_win:.2f}) exceeds average loss (₹{avg_loss:.2f}) — healthy risk-reward")
        if profit_factor > 1.5:
            winning.append(f"Profit factor {profit_factor:.2f} — strong edge")

        if win_rate <= 45:
            losing.append("Win rate below 45% — edge is weak")
        if avg_loss > avg_win:
            losing.append("Average loss exceeds average win — tighten stops")
        if total_pnl < 0:
            losing.append(f"Net negative PnL (₹{total_pnl:.2f}) in recent trades")
        if max_consec_loss >= 3:
            losing.append(f"Max {max_consec_loss} consecutive losses — emotional discipline needed")
        if max_dd > 0:
            losing.append(f"Max drawdown ₹{max_dd:.2f} in this batch")

        if win_rate < 50:
            recommendations.append("Tighten entry filters, reduce low-confidence trades")
        if avg_loss > avg_win:
            recommendations.append("Improve risk-reward: trim size or wait for cleaner setups")
        if max_consec_loss >= 3:
            recommendations.append("Consider adding a cooldown after 2 consecutive losses")
        if profit_factor < 1.0:
            recommendations.append("Review losing trade patterns — are you fighting the trend?")
        if not recommendations:
            recommendations.append("Maintain discipline; prioritize high-conviction setups")

        summary = (
            f"{total} trades: win rate {win_rate:.1f}%, "
            f"avg win ₹{avg_win:.2f}, avg loss ₹{avg_loss:.2f}, "
            f"total PnL ₹{total_pnl:.2f}, profit factor {profit_factor:.2f}"
        )

        # Confidence calibration
        if total < 10:
            cal = "Insufficient data for calibration (< 10 trades)"
        elif win_rate > 60:
            cal = "Overly bullish — verify signals are not curve-fitted"
        elif win_rate > 50:
            cal = "Confidence aligned with positive expectancy"
        elif win_rate > 40:
            cal = "Edge is marginal — increase selectivity"
        else:
            cal = "Confidence needs significant recalibration — review entry criteria"

        result = ReflectionResult(
            reflection_id=f"ref_{self.reflection_count + 1:03d}",
            trades_analyzed=len(trades),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            summary=summary,
            patterns={"winning_conditions": winning, "losing_conditions": losing},
            recommendations=recommendations,
            confidence_calibration=cal,
            market_insights="Reinforce trend-aligned entries" if total >= 5 else "Limited sample",
            source="rule_based",
        )

        self.reflection_count += 1
        self.last_reflected_count += len(trades)
        self.last_reflection = result
        logger.info(f"Reflection #{self.reflection_count}: {summary}")
        return result

    def get_latest_reflection(self) -> Optional[str]:
        if self.last_reflection:
            return self.last_reflection.to_prompt_text()
        return None

    @staticmethod
    def _extract_pnl(trade: Dict) -> float:
        for key in ("pnl", "pnl_pct", "realized_pnl", "profit"):
            val = trade.get(key)
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass
        return 0.0


# ============================================
# LLM-Based Reflection Agent
# ============================================
class ReflectionAgentLLM:
    """
    The Philosopher (LLM) — Deep trade analysis using LLMFactory.
    
    Uses structured markdown table prompts and returns JSON analysis.
    Falls back to rule-based ReflectionAgent on failure.
    """

    TRIGGER_COUNT = 10

    def __init__(self):
        self._llm = None
        self.reflection_count = 0
        self.last_reflected_count = 0
        self.last_reflection: Optional[ReflectionResult] = None
        self._fallback = ReflectionAgent()
        self._log_dir = os.path.join("data", "reflections")
        logger.info("ReflectionAgentLLM (The Philosopher) initialized — LLM mode")

    def _get_llm(self):
        """Lazy init LLM client via LLMFactory."""
        if self._llm is None:
            try:
                from ..llm.factory import LLMFactory
                self._llm = LLMFactory.get_or_create()
                logger.info("ReflectionAgentLLM: LLM client acquired")
            except Exception as e:
                logger.warning(f"Failed to get LLM client: {e}")
        return self._llm

    def should_reflect(self, total_trades: int) -> bool:
        return (total_trades - self.last_reflected_count) >= self.TRIGGER_COUNT

    async def generate_reflection(self, trades: List[Dict]) -> Optional[ReflectionResult]:
        """Generate LLM-powered reflection from trade history."""
        if not trades or len(trades) < 3:
            return None

        llm = self._get_llm()
        if llm is None:
            logger.warning("No LLM available, using rule-based reflection")
            return await self._fallback.generate_reflection(trades)

        try:
            return await self._llm_reflection(trades, llm)
        except Exception as e:
            logger.warning(f"LLM reflection failed: {e}, falling back to rule-based")
            return self._fallback._rule_based_reflection(trades)

    async def _llm_reflection(self, trades: List[Dict], llm) -> ReflectionResult:
        """Build structured prompt, call LLM, parse JSON response."""
        from ..llm.base import Message, MessageRole

        system_prompt = (
            "You are a professional trading performance analyst for Indian equity markets. "
            "Analyze the trade history below and return a JSON object with these fields:\n"
            "- summary: 1-2 sentence performance overview\n"
            "- patterns: {winning_conditions: [...], losing_conditions: [...]}\n"
            "- recommendations: [...] actionable improvements\n"
            "- confidence_calibration: assessment of whether confidence levels match actual outcomes\n"
            "- market_insights: observations about market conditions during these trades\n\n"
            "Return ONLY valid JSON wrapped in ```json``` code block. Use INR (₹) for amounts."
        )

        user_prompt = self._build_user_prompt(trades)

        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_prompt),
        ]

        response = await llm.chat(messages, temperature=0.3, max_tokens=1500)
        raw_text = response.content.strip()

        result = self._parse_response(raw_text, trades)

        # Save log
        self._save_log(result, raw_text)

        return result

    def _build_user_prompt(self, trades: List[Dict]) -> str:
        """Build structured markdown table of trades for the LLM."""
        lines = [
            f"## Trade History — Last {len(trades)} Trades\n",
            "| # | Symbol | Action | Entry | Exit | PnL (₹) | Confidence | Duration |",
            "|---|--------|--------|-------|------|----------|------------|----------|",
        ]

        for i, t in enumerate(trades, 1):
            symbol = t.get("symbol", "?")
            action = t.get("action", t.get("side", "?"))
            entry = t.get("entry_price", t.get("price", "-"))
            exit_p = t.get("exit_price", "-")
            pnl = self._extract_pnl(t)
            conf = t.get("confidence", "-")
            duration = t.get("duration", "-")
            lines.append(
                f"| {i} | {symbol} | {action} | {entry} | {exit_p} | "
                f"₹{pnl:.2f} | {conf} | {duration} |"
            )

        # Add summary stats
        pnls = [self._extract_pnl(t) for t in trades]
        wins = sum(1 for p in pnls if p > 0)
        total = len(pnls)
        win_rate = (wins / total * 100) if total > 0 else 0
        total_pnl = sum(pnls)

        lines.extend([
            "",
            f"**Quick Stats**: {total} trades, win rate {win_rate:.1f}%, total PnL ₹{total_pnl:.2f}",
            "",
            "Please analyze these trades and return your analysis in JSON format.",
        ])

        return "\n".join(lines)

    def _parse_response(self, raw_text: str, trades: List[Dict]) -> ReflectionResult:
        """Parse JSON from LLM response, with robust fallback."""
        data = None

        # Try extracting from markdown code block
        if "```json" in raw_text:
            try:
                json_str = raw_text.split("```json")[1].split("```")[0].strip()
                data = json.loads(json_str)
            except (IndexError, json.JSONDecodeError):
                pass

        if data is None and "```" in raw_text:
            try:
                json_str = raw_text.split("```")[1].split("```")[0].strip()
                data = json.loads(json_str)
            except (IndexError, json.JSONDecodeError):
                pass

        # Try raw JSON
        if data is None:
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                pass

        # Try finding JSON object in text
        if data is None:
            import re
            match = re.search(r'\{[\s\S]*\}', raw_text)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        if data is None:
            logger.warning("Could not parse LLM reflection response, using rule-based")
            return self._fallback._rule_based_reflection(trades)

        result = ReflectionResult(
            reflection_id=f"ref_{self.reflection_count + 1:03d}",
            trades_analyzed=len(trades),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            summary=data.get("summary", "LLM analysis complete"),
            patterns=data.get("patterns", {"winning_conditions": [], "losing_conditions": []}),
            recommendations=data.get("recommendations", []),
            confidence_calibration=data.get("confidence_calibration", ""),
            market_insights=data.get("market_insights", ""),
            raw_response=raw_text,
            source="llm",
        )

        self.reflection_count += 1
        self.last_reflected_count += len(trades)
        self.last_reflection = result
        logger.info(f"LLM Reflection #{self.reflection_count}: {result.summary}")
        return result

    def _save_log(self, result: ReflectionResult, raw_text: str):
        """Save reflection log to file for audit trail."""
        try:
            os.makedirs(self._log_dir, exist_ok=True)
            filename = f"reflection_{result.reflection_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(self._log_dir, filename)

            log_data = {
                "result": result.to_dict(),
                "raw_response": raw_text,
                "saved_at": datetime.now().isoformat(),
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Reflection log saved: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to save reflection log: {e}")

    def get_latest_reflection(self) -> Optional[str]:
        if self.last_reflection:
            return self.last_reflection.to_prompt_text()
        return None

    @staticmethod
    def _extract_pnl(trade: Dict) -> float:
        for key in ("pnl", "pnl_pct", "realized_pnl", "profit"):
            val = trade.get(key)
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass
        return 0.0
