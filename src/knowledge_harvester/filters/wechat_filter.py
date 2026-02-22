"""WeChat conversation filter engine.

Evaluates filter policies to classify conversations into tiers:
  - keep: Extract and embed for PKB search
  - archive: Extract but don't embed (keyword search only)
  - exclude: Don't extract (move to _excluded/)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

log = logging.getLogger(__name__)


@dataclass
class FilterRule:
    name: str
    match: Dict[str, Any]
    tier: str  # "keep" | "archive" | "exclude"
    priority: int = 10
    reason: str = ""

    def to_dict(self) -> dict:
        d = {"name": self.name, "match": self.match, "tier": self.tier, "priority": self.priority}
        if self.reason:
            d["reason"] = self.reason
        return d


@dataclass
class FilterPolicy:
    version: int = 1
    default_tier: str = "archive"
    rules: List[FilterRule] = field(default_factory=list)

    @classmethod
    def load(cls, path: str) -> "FilterPolicy":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        rules = [FilterRule(**r) for r in data.get("rules", [])]
        return cls(
            version=data.get("version", 1),
            default_tier=data.get("default_tier", "archive"),
            rules=rules,
        )

    def save(self, path: str):
        data = {
            "version": self.version,
            "default_tier": self.default_tier,
            "rules": [r.to_dict() for r in self.rules],
        }
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def evaluate(self, meta: dict) -> Tuple[str, str]:
        """Evaluate a conversation against all rules.

        Returns (tier, matched_rule_name).
        """
        matched_tier = self.default_tier
        matched_rule = "default"
        matched_priority = -1

        for rule in self.rules:
            if rule.priority > matched_priority and _matches(rule, meta):
                matched_tier = rule.tier
                matched_rule = rule.name
                matched_priority = rule.priority

        return matched_tier, matched_rule


def _matches(rule: FilterRule, meta: dict) -> bool:
    """Check if a conversation matches a rule's criteria."""
    match = rule.match

    if "is_group" in match:
        if meta.get("is_group") != match["is_group"]:
            return False

    if "username" in match:
        usernames = match["username"]
        if isinstance(usernames, str):
            usernames = [usernames]
        if meta.get("username") not in usernames:
            return False

    if "title_contains" in match:
        title = meta.get("title", "")
        if not any(kw in title for kw in match["title_contains"]):
            return False

    if "title_not_contains" in match:
        title = meta.get("title", "")
        if any(kw in title for kw in match["title_not_contains"]):
            return False

    if "min_messages" in match:
        if meta.get("message_count", 0) < match["min_messages"]:
            return False

    if "max_messages" in match:
        if meta.get("message_count", 0) > match["max_messages"]:
            return False

    if "active_within_days" in match:
        last = meta.get("last_message_time", "")
        if last:
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=match["active_within_days"])
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                if last_dt < cutoff:
                    return False
            except (ValueError, TypeError):
                return False
        else:
            return False

    if "dormant_days" in match:
        last = meta.get("last_message_time", "")
        if last:
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=match["dormant_days"])
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                if last_dt >= cutoff:
                    return False
            except (ValueError, TypeError):
                pass

    return True


def build_conversation_meta(conv_entry: dict) -> dict:
    """Build filter-compatible metadata from an index.json entry."""
    metadata = conv_entry.get("metadata", {})
    return {
        "id": conv_entry.get("id", ""),
        "title": conv_entry.get("title", ""),
        "message_count": conv_entry.get("message_count", 0),
        "is_group": metadata.get("is_group", False),
        "username": metadata.get("username", ""),
        "last_message_time": metadata.get("last_message_time", ""),
    }
