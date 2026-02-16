"""File Path Signal - score based on file paths in tool calls"""

from typing import List

from ..config.settings import Settings
from ..models.category import Entity
from ..models.session import SessionMessage
from ..parser.message_extractor import MessageExtractor


class FilePathSignal:
    """Match entities via file paths (highest weight signal)."""

    def __init__(self, settings: Settings = None):
        self.extractor = MessageExtractor(settings=settings)

    def score(self, messages: List[SessionMessage], entity: Entity) -> float:
        """Compute file path match score (0.0 - 1.0)."""
        if not messages or not entity.path_patterns:
            return 0.0

        matched = 0
        total_with_paths = 0

        for msg in messages:
            paths = self.extractor.extract_file_paths(msg)
            if not paths:
                continue
            total_with_paths += 1
            for path in paths:
                if self._matches_entity(path, entity):
                    matched += 1
                    break

        if total_with_paths == 0:
            return 0.0

        ratio = matched / total_with_paths
        if matched > 0:
            return max(0.3, ratio)
        return 0.0

    def matched_messages(self, messages: List[SessionMessage], entity: Entity) -> List[SessionMessage]:
        """Return list of matching messages."""
        result = []
        for msg in messages:
            paths = self.extractor.extract_file_paths(msg)
            for path in paths:
                if self._matches_entity(path, entity):
                    result.append(msg)
                    break
        return result

    def _matches_entity(self, path: str, entity: Entity) -> bool:
        """Check if a path matches the entity."""
        for pattern in entity.path_patterns:
            if path.startswith(pattern) or pattern.rstrip("/") in path:
                return True
        return False
