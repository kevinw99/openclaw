"""Message Extractor - extract text and file paths from messages"""

import re
from typing import List, Set

from ..config.settings import Settings
from ..models.session import SessionMessage


class MessageExtractor:
    """Extract classification-relevant information from session messages."""

    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        # Build project prefixes dynamically from project_root
        root_str = str(self.settings.project_root)
        self._project_prefixes = [
            root_str + "/",
        ]
        # Also handle common path variations (spaces vs underscores)
        alt = root_str.replace("_", " ")
        if alt != root_str:
            self._project_prefixes.append(alt + "/")
        alt2 = root_str.replace(" ", "_")
        if alt2 != root_str:
            self._project_prefixes.append(alt2 + "/")

        # Build entity dir regex pattern from settings
        dir_names = list(self.settings.entity_dirs.values())
        if dir_names:
            escaped = [re.escape(d) for d in dir_names]
            self._dir_pattern = re.compile(
                r'(?:' + '|'.join(escaped) + r')/[^\s\'"`,;)\]}>]+'
            )
        else:
            self._dir_pattern = None

    def extract_file_paths(self, msg: SessionMessage) -> List[str]:
        """Extract all file paths referenced in the message (normalized to project-relative)."""
        raw_paths = msg.file_paths
        normalized = []
        for p in raw_paths:
            rel = self._normalize_path(p)
            if rel:
                normalized.append(rel)

        # Also extract paths from text content
        text = msg.text_content
        if text and self._dir_pattern:
            for match in self._dir_pattern.finditer(text):
                path = match.group(0).rstrip(".,;:)")
                normalized.append(path)

        return list(dict.fromkeys(normalized))  # dedupe preserving order

    def extract_text(self, msg: SessionMessage) -> str:
        """Extract plain text content (for keyword and pattern matching)."""
        parts = []

        text = msg.text_content
        if text:
            parts.append(text)

        if msg.msg_type == "system":
            for block in msg.content_blocks:
                if block.block_type == "text":
                    parts.append(block.text)

        return "\n".join(parts)

    def extract_keywords(self, msg: SessionMessage) -> Set[str]:
        """Extract keywords from the message (for fuzzy matching)."""
        text = self.extract_text(msg)
        if not text:
            return set()

        # Extract CJK words (consecutive CJK characters)
        chinese_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', text))

        # Extract English words
        english_words = set(
            w.lower() for w in re.findall(r'[a-zA-Z_]{3,}', text)
        )

        return chinese_words | english_words

    def _normalize_path(self, path: str) -> str:
        """Normalize absolute path to project-relative path."""
        for prefix in self._project_prefixes:
            if path.startswith(prefix):
                return path[len(prefix):]

        # Already a relative path matching known entity dirs
        dir_names = self.settings.entity_dirs.values()
        for d in dir_names:
            if path.startswith(f"{d}/"):
                return path

        return ""
