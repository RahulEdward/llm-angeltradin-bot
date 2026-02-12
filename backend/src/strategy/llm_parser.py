"""
LLM Output Parser
==================

Parses structured LLM output (XML tags + JSON).

Supports format:
<reasoning>
Analysis process...
</reasoning>

<decision>
```json
[{
  "symbol": "RELIANCE",
  "action": "open_long",
  ...
}]
```
</decision>

Features:
1. Priority extraction from XML tags
2. Support for ```json code blocks
3. Auto-fix common character errors (full-width chars, range symbols)
4. Safe fallback mode (returns wait decision on parse failure)
"""

import re
import json
from typing import Dict, Optional, Tuple
from loguru import logger


class LLMOutputParser:
    """
    LLM output parser for structured trading decisions.
    
    Handles:
    - XML <decision> and <final_vote> tags
    - Markdown ```json code blocks
    - Balanced JSON extraction
    - Character normalization (full-width → half-width)
    - Safe fallback on parse failure
    """

    def __init__(self):
        self.supported_tags = ['decision', 'final_vote']

    def parse(self, llm_response: str) -> Dict:
        """
        Parse LLM output into reasoning + decision.
        
        Returns:
            {
                'reasoning': str,
                'decision': dict,
                'raw_response': str
            }
        """
        try:
            reasoning = self._extract_tag_content(llm_response, 'reasoning')

            decision_json = None
            for tag in self.supported_tags:
                decision_json = self._extract_tag_content(llm_response, tag)
                if decision_json:
                    break

            if not decision_json:
                decision_json = self._extract_json_from_text(llm_response)

            if decision_json:
                decision = self._parse_json_with_fallback(decision_json)
            else:
                logger.warning("No decision JSON found, using safe fallback")
                decision = self._get_fallback_decision()

            if not decision or 'action' not in decision:
                logger.warning("Invalid decision, using safe fallback")
                decision = self._get_fallback_decision()

            return {
                'reasoning': reasoning or '',
                'decision': decision,
                'raw_response': llm_response
            }

        except Exception as e:
            logger.error(f"LLM output parse failed: {e}, using fallback")
            return {
                'reasoning': '',
                'decision': self._get_fallback_decision(),
                'raw_response': llm_response,
                'parse_error': str(e)
            }

    def _extract_tag_content(self, text: str, tag: str) -> Optional[str]:
        """Extract content from XML-style tags."""
        patterns = [
            rf'<{tag}>\s*```json\s*(.*?)\s*```\s*</{tag}>',
            rf'<{tag}>\s*```\s*(.*?)\s*```\s*</{tag}>',
            rf'<{tag}>(.*?)</{tag}>',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                if tag in self.supported_tags:
                    content = re.sub(r'^```json\s*', '', content)
                    content = re.sub(r'^```\s*', '', content)
                    content = re.sub(r'\s*```$', '', content)
                return content

        return None

    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """Extract JSON from text using bracket-counting."""
        # Try array first
        json_str = self._extract_balanced_json(text, '[', ']')
        if json_str:
            return json_str

        # Try object
        json_str = self._extract_balanced_json(text, '{', '}')
        if json_str:
            return json_str

        # Regex fallback
        arr_match = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
        if arr_match:
            return arr_match.group(0)

        obj_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if obj_match:
            return obj_match.group(0)

        return None

    def _extract_balanced_json(self, text: str, open_char: str, close_char: str) -> Optional[str]:
        """Extract balanced JSON structure using bracket counting."""
        start_idx = text.find(open_char)
        if start_idx == -1:
            return None

        count = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(text[start_idx:], start_idx):
            if escape_next:
                escape_next = False
                continue

            if char == '\\' and in_string:
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == open_char:
                    count += 1
                elif char == close_char:
                    count -= 1
                    if count == 0:
                        json_str = text[start_idx:i + 1]
                        try:
                            json.loads(json_str)
                            return json_str
                        except json.JSONDecodeError:
                            return None

        return None

    def _parse_json_with_fallback(self, json_str: str) -> Dict:
        """Parse JSON with character normalization and error recovery."""
        normalized = self._normalize_characters(json_str)

        try:
            data = json.loads(normalized)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            return data
        except json.JSONDecodeError:
            pass

        try:
            cleaned = re.sub(r',\s*}', '}', normalized)
            cleaned = re.sub(r',\s*\]', ']', cleaned)
            data = json.loads(cleaned)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            return data
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed after normalization: {e}")
            return {}

    def _normalize_characters(self, text: str) -> str:
        """Normalize full-width chars, remove range symbols and thousand separators."""
        replacements = {
            '\uff3b': '[', '\uff3d': ']',
            '\uff5b': '{', '\uff5d': '}',
            '\uff1a': ':', '\uff0c': ',',
            '\u201c': '"', '\u201d': '"',
            '\u2018': "'", '\u2019': "'",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        # Remove range symbol ~ (take first value)
        text = re.sub(r'(\d+\.?\d*)\s*~\s*\d+\.?\d*', r'\1', text)

        # Remove thousand separators in string values
        text = re.sub(r'"(\d{1,3}(?:,\d{3})+(?:\.\d+)?)"',
                      lambda m: '"' + m.group(1).replace(',', '') + '"', text)

        # Remove thousand separators in numeric values
        text = re.sub(r':\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?)\s*([,}\]])',
                      lambda m: ': ' + m.group(1).replace(',', '') + m.group(2), text)

        return text

    def _get_fallback_decision(self) -> Dict:
        """Safe fallback decision when parsing fails."""
        return {
            'symbol': 'UNKNOWN',
            'action': 'wait',
            'confidence': 0,
            'reasoning': 'Parse error, fallback to safe wait decision'
        }

    def normalize_action(self, action: str) -> str:
        """
        Normalize action strings to standard form.
        Indian equity only: no open_short, close_short.
        """
        action_map = {
            # Buy / Open Long
            'long': 'open_long',
            'buy': 'open_long',
            'go_long': 'open_long',
            # Close
            'close_long': 'close_position',
            'exit_long': 'close_position',
            'close': 'close_position',
            'exit': 'close_position',
            'sell': 'close_position',
            'close_position': 'close_position',
            # Hold / Wait
            'wait': 'wait',
            'hold': 'hold',
            'skip': 'wait',
        }
        return action_map.get(action.lower(), action)

    def validate_format(self, json_str: str) -> Tuple[bool, str]:
        """Validate JSON format requirements."""
        stripped = json_str.strip()
        if not stripped.startswith('[{') and not stripped.startswith('{'):
            return False, "JSON must start with { or [{"

        if '~' in json_str:
            return False, "Range symbol ~ is not allowed"

        if re.search(r'\d{1,3},\d{3}', json_str):
            return False, "Thousand separators are not allowed"

        return True, ""
