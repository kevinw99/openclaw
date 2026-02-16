"""Text Pattern Signal - score based on regex text patterns"""

import re
from typing import List

from ..config.settings import Settings
from ..models.category import Entity
from ..models.session import SessionMessage
from ..parser.message_extractor import MessageExtractor


class TextPatternSignal:
    """Match entities via regex text patterns."""

    def __init__(self, settings: Settings = None):
        self.extractor = MessageExtractor(settings=settings)
        self._compiled_cache = {}

    def score(self, messages: List[SessionMessage], entity: Entity) -> float:
        """Compute text pattern match score (0.0 - 1.0)."""
        if not messages or not entity.text_patterns:
            return 0.0

        patterns = self._get_compiled(entity)
        matched = 0
        total_with_text = 0

        for msg in messages:
            text = self.extractor.extract_text(msg)
            if not text:
                continue
            total_with_text += 1
            for pat in patterns:
                if pat.search(text):
                    matched += 1
                    break

        if total_with_text == 0:
            return 0.0

        ratio = matched / total_with_text
        if matched > 0:
            return max(0.2, ratio)
        return 0.0

    def matched_messages(self, messages: List[SessionMessage], entity: Entity) -> List[SessionMessage]:
        """Return list of matching messages."""
        patterns = self._get_compiled(entity)
        result = []
        for msg in messages:
            text = self.extractor.extract_text(msg)
            if not text:
                continue
            for pat in patterns:
                if pat.search(text):
                    result.append(msg)
                    break
        return result

    def _get_compiled(self, entity: Entity) -> list:
        """Get compiled regex patterns (cached)."""
        key = entity.entity_id
        if key not in self._compiled_cache:
            compiled = []
            for pattern in entity.text_patterns:
                try:
                    compiled.append(re.compile(pattern, re.IGNORECASE))
                except re.error:
                    continue
            self._compiled_cache[key] = compiled
        return self._compiled_cache[key]
