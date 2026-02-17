"""Keyword Signal - score based on keyword matching"""

from typing import List, Set

from ..config.settings import Settings
from ..models.category import Entity
from ..models.session import SessionMessage
from ..parser.message_extractor import MessageExtractor


class KeywordSignal:
    """Match entities via keywords (lowest weight signal)."""

    def __init__(self, settings: Settings = None):
        self.extractor = MessageExtractor(settings=settings)

    def score(self, messages: List[SessionMessage], entity: Entity) -> float:
        """Compute keyword match score (0.0 - 1.0)."""
        if not messages or not entity.keywords:
            return 0.0

        entity_keywords = self._normalize_keywords(entity.keywords)
        matched = 0
        total_with_text = 0

        for msg in messages:
            msg_keywords = self.extractor.extract_keywords(msg)
            if not msg_keywords:
                continue
            total_with_text += 1
            msg_lower = {k.lower() for k in msg_keywords}
            if msg_lower & entity_keywords:
                matched += 1

        if total_with_text == 0:
            return 0.0

        ratio = matched / total_with_text
        if matched > 0:
            return max(0.1, min(ratio, 0.8))
        return 0.0

    def matched_messages(self, messages: List[SessionMessage], entity: Entity) -> List[SessionMessage]:
        """Return list of matching messages."""
        entity_keywords = self._normalize_keywords(entity.keywords)
        result = []
        for msg in messages:
            msg_keywords = self.extractor.extract_keywords(msg)
            msg_lower = {k.lower() for k in msg_keywords}
            if msg_lower & entity_keywords:
                result.append(msg)
        return result

    def _normalize_keywords(self, keywords: List[str]) -> Set[str]:
        """Normalize keywords."""
        normalized = set()
        for kw in keywords:
            normalized.add(kw.lower())
            for part in kw.replace("-", "_").split("_"):
                if part and len(part) > 2:
                    normalized.add(part.lower())
        return normalized
