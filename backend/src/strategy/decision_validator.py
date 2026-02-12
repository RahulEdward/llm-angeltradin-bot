"""
Decision Validator
==================

Validates LLM trading decisions for safety and correctness.

Rules:
1. Required fields check
2. Value range validation
3. Stop-loss direction check (long: SL < entry, short: SL > entry)
4. Risk-reward ratio check (min 2:1)
5. Format validation (no range symbols, no comma separators in numbers)

Adapted for Indian equity markets:
- No short-selling (delivery only) — open_short is disallowed
- Leverage is always 1x
"""

import re
from typing import Dict, List, Tuple, Optional
from loguru import logger


class DecisionValidator:
    """
    Validates trading decisions from LLM output.
    
    Indian equity adaptations:
    - max_leverage = 1 (no leverage for delivery-based trades)
    - open_short is invalid (no short-selling)
    - Valid actions: open_long (buy), close_position (sell), hold, wait
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        self.max_leverage = self.config.get('max_leverage', 1)
        self.max_position_pct = self.config.get('max_position_pct', 30.0)
        self.min_confidence = self.config.get('min_confidence', 0)
        self.max_confidence = self.config.get('max_confidence', 100)
        self.min_risk_reward_ratio = self.config.get('min_risk_reward_ratio', 2.0)

    def validate(self, decision: Dict) -> Tuple[bool, List[str]]:
        """
        Validate a decision dict.
        
        Returns:
            (is_valid, errors)
        """
        errors = []

        # 1. Required fields
        required_fields = ['symbol', 'action', 'reasoning']
        for field in required_fields:
            if field not in decision:
                errors.append(f"Missing required field: {field}")

        if errors:
            return False, errors

        # 2. Action validity (Indian equities: no short-selling)
        valid_actions = [
            'open_long',
            'close_position',
            'hold', 'wait'
        ]
        if decision['action'] not in valid_actions:
            errors.append(f"Invalid action: {decision['action']} "
                         f"(valid: {', '.join(valid_actions)})")

        # 3. Confidence check
        if 'confidence' in decision:
            confidence = decision.get('confidence', 0)
            if not (self.min_confidence <= confidence <= self.max_confidence):
                errors.append(f"Confidence out of range [{self.min_confidence}, {self.max_confidence}]: {confidence}")

        # 4. Format validation
        format_errors = self._validate_format(decision)
        errors.extend(format_errors)

        # 5. Open position checks
        if decision['action'] == 'open_long':
            open_required = ['stop_loss', 'take_profit']
            for field in open_required:
                if field not in decision or decision[field] is None:
                    errors.append(f"Open trade missing required field: {field}")

            if any('Open trade missing' in e for e in errors):
                return False, errors

            # Numeric format check
            numeric_fields = ['stop_loss', 'take_profit', 'position_size_pct']
            for field in numeric_fields:
                if field in decision:
                    value = decision[field]
                    if isinstance(value, str):
                        errors.append(f"{field} must not be a string (possible formula): {value}")
                    elif not isinstance(value, (int, float)):
                        errors.append(f"{field} must be numeric: {value}")

            # Stop-loss direction (long: SL < entry)
            if not self.validate_stop_loss_direction(decision):
                entry = decision.get('entry_price', decision.get('current_price', 0))
                stop_loss = decision.get('stop_loss', 0)
                errors.append(f"Long SL direction error: stop_loss ({stop_loss}) must be < entry_price ({entry})")

            # Risk-reward ratio
            if not self.validate_risk_reward_ratio(decision):
                ratio = self.calculate_risk_reward_ratio(decision)
                errors.append(f"Risk:Reward ratio insufficient: {ratio:.2f} < {self.min_risk_reward_ratio}")

        return len(errors) == 0, errors

    def _validate_format(self, decision: Dict) -> List[str]:
        """Validate no range symbols (~) or thousand separators in values."""
        errors = []
        for key, value in decision.items():
            if isinstance(value, str):
                if '~' in value:
                    errors.append(f"Field {key} contains forbidden range symbol '~': {value}")
                if re.match(r'^\d{1,3}(,\d{3})+(\.\d+)?$', value):
                    errors.append(f"Field {key} contains forbidden thousand separator ',': {value}")
        return errors

    def validate_stop_loss_direction(self, decision: Dict) -> bool:
        """For long: stop_loss must be below entry_price."""
        action = decision.get('action')
        if action != 'open_long':
            return True

        entry_price = decision.get('entry_price') or decision.get('current_price')
        stop_loss = decision.get('stop_loss')

        if entry_price is None or stop_loss is None:
            return True

        return stop_loss < entry_price

    def validate_risk_reward_ratio(self, decision: Dict) -> bool:
        """Validate risk:reward >= min_risk_reward_ratio."""
        ratio = self.calculate_risk_reward_ratio(decision)
        if ratio is None:
            return True
        return ratio >= self.min_risk_reward_ratio

    def calculate_risk_reward_ratio(self, decision: Dict) -> Optional[float]:
        """Calculate risk:reward ratio for open_long trades."""
        action = decision.get('action')
        if action != 'open_long':
            return None

        entry_price = decision.get('entry_price') or decision.get('current_price')
        stop_loss = decision.get('stop_loss')
        take_profit = decision.get('take_profit')

        if None in [entry_price, stop_loss, take_profit]:
            return None

        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)

        if risk == 0:
            return None
        return reward / risk

    def get_validation_summary(self, decision: Dict) -> str:
        """Get validation summary for logging."""
        is_valid, errors = self.validate(decision)

        if is_valid:
            summary = f"✅ Decision validated: {decision.get('action', 'unknown')}"
            if decision.get('action') == 'open_long':
                ratio = self.calculate_risk_reward_ratio(decision)
                if ratio:
                    summary += f", R:R {ratio:.2f}"
        else:
            summary = f"❌ Decision validation failed: {len(errors)} error(s)\n"
            for i, error in enumerate(errors, 1):
                summary += f"  {i}. {error}\n"

        return summary
