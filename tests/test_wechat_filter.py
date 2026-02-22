"""Tests for WeChat conversation filter engine."""

import json
import tempfile
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_harvester.filters.wechat_filter import (
    FilterPolicy,
    FilterRule,
    build_conversation_meta,
    _matches,
)


# --- FilterRule basics ---

def test_filter_rule_to_dict():
    rule = FilterRule(name="test", match={"is_group": True}, tier="exclude", priority=10)
    d = rule.to_dict()
    assert d["name"] == "test"
    assert d["tier"] == "exclude"
    assert d["priority"] == 10
    assert "reason" not in d  # empty reason omitted


def test_filter_rule_to_dict_with_reason():
    rule = FilterRule(name="test", match={}, tier="keep", reason="important")
    d = rule.to_dict()
    assert d["reason"] == "important"


# --- FilterPolicy load/save ---

def test_policy_save_load_roundtrip():
    policy = FilterPolicy(
        version=1,
        default_tier="archive",
        rules=[
            FilterRule(name="r1", match={"is_group": True}, tier="exclude", priority=5),
            FilterRule(name="r2", match={"min_messages": 50}, tier="keep", priority=20),
        ],
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name

    policy.save(path)
    loaded = FilterPolicy.load(path)

    assert loaded.version == 1
    assert loaded.default_tier == "archive"
    assert len(loaded.rules) == 2
    assert loaded.rules[0].name == "r1"
    assert loaded.rules[1].priority == 20
    Path(path).unlink()


def test_policy_load_empty_rules():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"version": 1, "default_tier": "keep", "rules": []}, f)
        path = f.name

    loaded = FilterPolicy.load(path)
    assert loaded.default_tier == "keep"
    assert len(loaded.rules) == 0
    Path(path).unlink()


# --- Matching logic ---

def test_match_is_group():
    rule = FilterRule(name="groups", match={"is_group": True}, tier="exclude")
    assert _matches(rule, {"is_group": True}) is True
    assert _matches(rule, {"is_group": False}) is False


def test_match_username_string():
    rule = FilterRule(name="user", match={"username": "wxid_abc"}, tier="keep")
    assert _matches(rule, {"username": "wxid_abc"}) is True
    assert _matches(rule, {"username": "wxid_xyz"}) is False


def test_match_username_list():
    rule = FilterRule(name="users", match={"username": ["wxid_a", "wxid_b"]}, tier="keep")
    assert _matches(rule, {"username": "wxid_a"}) is True
    assert _matches(rule, {"username": "wxid_b"}) is True
    assert _matches(rule, {"username": "wxid_c"}) is False


def test_match_title_contains():
    rule = FilterRule(name="title", match={"title_contains": ["tennis", "ski"]}, tier="keep")
    assert _matches(rule, {"title": "Bay area tennis group"}) is True
    assert _matches(rule, {"title": "Tahoe ski trip"}) is True
    assert _matches(rule, {"title": "Book club"}) is False


def test_match_title_not_contains():
    rule = FilterRule(name="no-spam", match={"title_not_contains": ["广告", "spam"]}, tier="keep")
    assert _matches(rule, {"title": "Friends chat"}) is True
    assert _matches(rule, {"title": "广告群"}) is False


def test_match_min_messages():
    rule = FilterRule(name="min", match={"min_messages": 50}, tier="keep")
    assert _matches(rule, {"message_count": 100}) is True
    assert _matches(rule, {"message_count": 50}) is True
    assert _matches(rule, {"message_count": 49}) is False


def test_match_max_messages():
    rule = FilterRule(name="max", match={"max_messages": 4}, tier="exclude")
    assert _matches(rule, {"message_count": 3}) is True
    assert _matches(rule, {"message_count": 4}) is True
    assert _matches(rule, {"message_count": 5}) is False


def test_match_combined_criteria():
    """All criteria must match (AND logic)."""
    rule = FilterRule(name="combo", match={"is_group": True, "min_messages": 200}, tier="keep")
    assert _matches(rule, {"is_group": True, "message_count": 500}) is True
    assert _matches(rule, {"is_group": True, "message_count": 100}) is False
    assert _matches(rule, {"is_group": False, "message_count": 500}) is False


def test_match_active_within_days():
    rule = FilterRule(name="active", match={"active_within_days": 30}, tier="keep")
    # Recent timestamp
    assert _matches(rule, {"last_message_time": "2026-02-20T10:00:00Z"}) is True
    # Old timestamp
    assert _matches(rule, {"last_message_time": "2024-01-01T00:00:00Z"}) is False
    # No timestamp
    assert _matches(rule, {"last_message_time": ""}) is False
    assert _matches(rule, {}) is False


def test_match_dormant_days():
    rule = FilterRule(name="dormant", match={"dormant_days": 365}, tier="exclude")
    # Old timestamp (dormant)
    assert _matches(rule, {"last_message_time": "2024-01-01T00:00:00Z"}) is True
    # Recent timestamp (not dormant)
    assert _matches(rule, {"last_message_time": "2026-02-20T10:00:00Z"}) is False
    # No timestamp — passes (dormant assumed)
    assert _matches(rule, {"last_message_time": ""}) is True


# --- Policy evaluation ---

def test_evaluate_default_tier():
    policy = FilterPolicy(default_tier="archive", rules=[])
    tier, rule = policy.evaluate({"message_count": 10})
    assert tier == "archive"
    assert rule == "default"


def test_evaluate_single_rule_match():
    policy = FilterPolicy(
        default_tier="archive",
        rules=[FilterRule(name="keep-big", match={"min_messages": 100}, tier="keep", priority=10)],
    )
    tier, rule = policy.evaluate({"message_count": 200})
    assert tier == "keep"
    assert rule == "keep-big"


def test_evaluate_single_rule_no_match():
    policy = FilterPolicy(
        default_tier="archive",
        rules=[FilterRule(name="keep-big", match={"min_messages": 100}, tier="keep", priority=10)],
    )
    tier, rule = policy.evaluate({"message_count": 50})
    assert tier == "archive"
    assert rule == "default"


def test_evaluate_priority_ordering():
    """Higher priority rules win."""
    policy = FilterPolicy(
        default_tier="archive",
        rules=[
            FilterRule(name="low", match={"min_messages": 10}, tier="exclude", priority=5),
            FilterRule(name="high", match={"min_messages": 10}, tier="keep", priority=20),
        ],
    )
    tier, rule = policy.evaluate({"message_count": 50})
    assert tier == "keep"
    assert rule == "high"


def test_evaluate_most_specific_wins():
    """When both match, higher priority wins regardless of order."""
    policy = FilterPolicy(
        default_tier="archive",
        rules=[
            FilterRule(name="general", match={"is_group": True}, tier="exclude", priority=5),
            FilterRule(name="specific", match={"is_group": True, "min_messages": 200}, tier="keep", priority=20),
        ],
    )
    # Big group: specific rule wins
    tier, rule = policy.evaluate({"is_group": True, "message_count": 500})
    assert tier == "keep"
    assert rule == "specific"

    # Small group: only general matches
    tier, rule = policy.evaluate({"is_group": True, "message_count": 10})
    assert tier == "exclude"
    assert rule == "general"


# --- build_conversation_meta ---

def test_build_conversation_meta():
    entry = {
        "id": "conv123",
        "title": "Test Chat",
        "message_count": 42,
        "metadata": {
            "is_group": True,
            "username": "group@chatroom",
            "last_message_time": "2026-01-15T12:00:00Z",
        },
    }
    meta = build_conversation_meta(entry)
    assert meta["id"] == "conv123"
    assert meta["title"] == "Test Chat"
    assert meta["message_count"] == 42
    assert meta["is_group"] is True
    assert meta["username"] == "group@chatroom"
    assert meta["last_message_time"] == "2026-01-15T12:00:00Z"


def test_build_conversation_meta_missing_fields():
    entry = {"id": "x"}
    meta = build_conversation_meta(entry)
    assert meta["title"] == ""
    assert meta["message_count"] == 0
    assert meta["is_group"] is False
    assert meta["username"] == ""
