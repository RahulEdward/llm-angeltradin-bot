"""
Reflection Agent - The Philosopher
Trading retrospection every N trades.
Supports both LLM-based and rule-based reflection.
Adapted from reference-repo for Indian markets.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import json
from loguru import logger


@dataclass
class ReflectionResult:
    reflection_id: str = ""
    trades_analyzed: int = 0
    timestamp: str = ""
    summary: str = ""
    patterns: Dict[str, List[str]] = field(default_factory=lambda: {"winning_conditions": [], "losing_conditions": []})
    recommendations: List[str] = field(default_factory=list)
    confidence_calibration: str = ""
    market_insights: str = ""

    def to_prompt_text(self) -> str:
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


class ReflectionAgent:
    """
    The Philosopher - Trade retrospection agent.
    Analyzes completed trades every N trades and provides insights.
    Rule-based (no LLM required). LLM enhancement optional.
    """

    TRIGGER_COUNT = 10

    def __init__(self, use_llm: bool = False, llm_client=None):
        self.use_llm = use_llm
        self._llm = llm_client
        self.reflection_count = 0
        self.last_reflected_count = 0
        self.last_reflection: Optional[ReflectionResult] = None
        logger.info(f"ReflectionAgent (The Philosopher) initialized (LLM: {'ON' if use_llm else 'OFF'})")

    def should_reflect(self, total_trades: int) -> bool:
        return (total_trades - self.last_reflected_count) >= self.TRIGGER_COUNT

    async def generate_reflection(self, trades: List[Dict]) -> Optional[ReflectionResult]:
        """Generate reflection from trade history."""
        if not trades or len(trades) < 3:
            return None

        # If LLM available, try LLM-based reflection
        if self.use_llm and self._llm:
            try:
                return await self._llm_reflection(trades)
            except Exception as e:
                logger.warning(f"LLM reflection failed: {e}, falling back to rule-based")

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

        winning = []
        losing = []
        recommendations = []

        if win_rate >= 55:
            winning.append("Win rate above 55% - current filters are effective")
        if avg_win > avg_loss and avg_win > 0:
            winning.append("Average win exceeds average loss - healthy risk-reward")

        if win_rate <= 45:
            losing.append("Win rate below 45% - edge is weak")
        if avg_loss > avg_win:
            losing.append("Average loss exceeds average win - tighten stops")
        if total_pnl < 0:
            losing.append("Net negative PnL in recent trades")

        if win_rate < 50:
            recommendations.append("Tighten entry filters, reduce low-confidence trades")
        if avg_loss > avg_win:
            recommendations.append("Improve risk-reward: trim size or wait for cleaner setups")
        if not recommendations:
            recommendations.append("Maintain discipline; prioritize high-conviction setups")

        summary = (
            f"{total} trades: win rate {win_rate:.1f}%, "
            f"avg win ₹{avg_win:.2f}, avg loss ₹{avg_loss:.2f}, total PnL ₹{total_pnl:.2f}"
        )

        result = ReflectionResult(
            reflection_id=f"ref_{self.reflection_count + 1:03d}",
            trades_analyzed=len(trades),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            summary=summary,
            patterns={"winning_conditions": winning, "losing_conditions": losing},
            recommendations=recommendations,
            confidence_calibration="Calibration requires more data" if total < 10 else (
                "Confidence aligned" if win_rate > 50 else "Confidence needs recalibration"
            ),
            market_insights="Reinforce trend-aligned entries" if total >= 5 else "Limited sample",
        )

        self.reflection_count += 1
        self.last_reflected_count += len(trades)
        self.last_reflection = result
        logger.info(f"Reflection #{self.reflection_count}: {summary}")
        return result

    async def _llm_reflection(self, trades: List[Dict]) -> ReflectionResult:
        """LLM-based reflection (uses existing LLM client's reflect_on_trades)."""
        from ..llm.base import Message, MessageRole

        trade_summary = []
        for i, t in enumerate(trades, 1):
            pnl = self._extract_pnl(t)
            symbol = t.get("symbol", "?")
            action = t.get("action", t.get("side", "?"))
            trade_summary.append(f"{i}. {symbol} {action} PnL=₹{pnl:.2f}")

        prompt = (
            "Analyze these recent trades and provide JSON with: summary, patterns "
            "(winning_conditions, losing_conditions), recommendations, confidence_calibration, "
            f"market_insights.\n\nTrades:\n" + "\n".join(trade_summary)
        )

        messages = [
            Message(role=MessageRole.SYSTEM, content="You are a trading retrospection analyst for Indian equity markets."),
            Message(role=MessageRole.USER, content=prompt),
        ]

        response = await self._llm.chat(messages)
        # Try to parse JSON from response
        try:
            text = response.content.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            data = json.loads(text)

            result = ReflectionResult(
                reflection_id=f"ref_{self.reflection_count + 1:03d}",
                trades_analyzed=len(trades),
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                summary=data.get("summary", "LLM analysis complete"),
                patterns=data.get("patterns", {"winning_conditions": [], "losing_conditions": []}),
                recommendations=data.get("recommendations", []),
                confidence_calibration=data.get("confidence_calibration", ""),
                market_insights=data.get("market_insights", ""),
            )
            self.reflection_count += 1
            self.last_reflected_count += len(trades)
            self.last_reflection = result
            return result
        except Exception:
            # Fallback to rule-based
            return self._rule_based_reflection(trades)

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
