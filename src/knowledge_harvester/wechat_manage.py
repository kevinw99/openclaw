"""WeChat conversation management commands.

Provides audit, categorization, and policy-based filtering for WeChat conversations.
"""

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import List, Optional

from knowledge_harvester.config import Config
from knowledge_harvester.filters.wechat_filter import (
    FilterPolicy,
    build_conversation_meta,
)


def cmd_audit(config: Config, verbose: bool = False):
    """Audit existing WeChat conversations and print breakdown."""
    index_path = config.output_dir / "wechat" / "index.json"
    if not index_path.exists():
        print("No WeChat conversations found.")
        return

    index = json.loads(index_path.read_text(encoding="utf-8"))
    total = len(index)

    groups = [c for c in index if c.get("metadata", {}).get("is_group", False)]
    dms = [c for c in index if not c.get("metadata", {}).get("is_group", False)]

    total_msgs = sum(c.get("message_count", 0) for c in index)
    group_msgs = sum(c.get("message_count", 0) for c in groups)
    dm_msgs = sum(c.get("message_count", 0) for c in dms)

    print("=" * 60)
    print("WeChat Conversation Audit")
    print("=" * 60)
    print(f"Total conversations: {total}")
    print(f"  DM conversations:  {len(dms)} ({len(dms)*100//total}%)")
    print(f"  Group chats:       {len(groups)} ({len(groups)*100//total}%)")
    print(f"\nTotal messages: {total_msgs:,}")
    print(f"  Group messages:    {group_msgs:,} ({group_msgs*100//total_msgs}%)")
    print(f"  DM messages:       {dm_msgs:,} ({dm_msgs*100//total_msgs}%)")

    # Message count distribution
    def bucket(n):
        if n >= 1000: return ">1000"
        if n >= 200: return "200-999"
        if n >= 50: return "50-199"
        if n >= 20: return "20-49"
        if n >= 5: return "5-19"
        return "<5"

    dist = Counter()
    for c in index:
        dist[bucket(c.get("message_count", 0))] += 1

    print("\nBy message count:")
    for b in [">1000", "200-999", "50-199", "20-49", "5-19", "<5"]:
        print(f"  {b:>10s}: {dist.get(b, 0):4d} conversations")

    # Group analysis
    small_groups = [g for g in groups if g.get("message_count", 0) < 20]
    medium_groups = [g for g in groups if 20 <= g.get("message_count", 0) < 200]
    large_groups = [g for g in groups if g.get("message_count", 0) >= 200]
    print(f"\nGroup chat activity:")
    print(f"  <20 msgs:   {len(small_groups):3d} groups (likely dead)")
    print(f"  20-199:     {len(medium_groups):3d} groups (low/medium)")
    print(f"  200+ msgs:  {len(large_groups):3d} groups (active)")

    # Tiny conversations
    tiny = [c for c in index if c.get("message_count", 0) < 5]
    print(f"\nTiny conversations (<5 msgs): {len(tiny)}")

    # Top conversations
    top = sorted(index, key=lambda c: c.get("message_count", 0), reverse=True)[:20]
    print(f"\nTop 20 by message count:")
    for i, c in enumerate(top):
        title = c.get("title", "(untitled)")[:40]
        mc = c.get("message_count", 0)
        is_g = "(group)" if c.get("metadata", {}).get("is_group") else "(DM)"
        tier = c.get("metadata", {}).get("tier", "")
        tier_str = f" [{tier}]" if tier else ""
        print(f"  {i+1:2d}. {title:42s} {is_g:8s} {mc:6,d} msgs{tier_str}")

    # Tier distribution (if any tagged)
    tier_dist = Counter()
    for c in index:
        t = c.get("metadata", {}).get("tier", "untagged")
        tier_dist[t] += 1
    if "untagged" not in tier_dist or len(tier_dist) > 1:
        print(f"\nBy tier:")
        for tier in ["keep", "archive", "exclude", "untagged"]:
            if tier_dist[tier]:
                print(f"  {tier:10s}: {tier_dist[tier]:4d} conversations")


def cmd_apply_policy(config: Config, policy_path: str, dry_run: bool = False):
    """Apply filter policy to existing conversations."""
    index_path = config.output_dir / "wechat" / "index.json"
    wechat_dir = config.output_dir / "wechat"

    if not index_path.exists():
        print("No WeChat conversations found.")
        return

    policy = FilterPolicy.load(policy_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))

    keep_count = 0
    archive_count = 0
    exclude_count = 0
    results = []

    for conv in index:
        meta = build_conversation_meta(conv)
        tier, rule = policy.evaluate(meta)
        results.append((conv, tier, rule))

        if tier == "keep":
            keep_count += 1
        elif tier == "archive":
            archive_count += 1
        elif tier == "exclude":
            exclude_count += 1

    # Print summary
    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}Policy: {policy_path}")
    print(f"{prefix}Default tier: {policy.default_tier}")
    print(f"{prefix}Rules: {len(policy.rules)}")
    print(f"\n{prefix}Results:")
    print(f"  Keep:    {keep_count:4d} conversations")
    print(f"  Archive: {archive_count:4d} conversations")
    print(f"  Exclude: {exclude_count:4d} conversations")

    # Show excluded conversations
    excluded = [(c, r) for c, t, r in results if t == "exclude"]
    if excluded:
        excluded_msgs = sum(c.get("message_count", 0) for c, _ in excluded)
        print(f"\n{prefix}Excluded conversations ({len(excluded)}, {excluded_msgs:,} msgs):")
        for c, rule in sorted(excluded, key=lambda x: x[0].get("message_count", 0)):
            title = c.get("title", "(untitled)")[:45]
            mc = c.get("message_count", 0)
            is_g = "G" if c.get("metadata", {}).get("is_group") else "D"
            print(f"  [{is_g}] {title:47s} {mc:5d} msgs  (rule: {rule})")

    if dry_run:
        print(f"\n{prefix}No changes made. Remove --dry-run to apply.")
        return

    # Apply: update tiers in index, move excluded files
    excluded_dir = wechat_dir / "_excluded"
    excluded_dir.mkdir(exist_ok=True)

    excluded_index = []
    kept_index = []

    for conv, tier, rule in results:
        conv.setdefault("metadata", {})
        conv["metadata"]["tier"] = tier
        conv["metadata"]["filter_rule"] = rule

        if tier == "exclude":
            # Move JSONL file to _excluded/
            conv_id = conv["id"]
            src = wechat_dir / f"{conv_id}.jsonl"
            dst = excluded_dir / f"{conv_id}.jsonl"
            if src.exists():
                shutil.move(str(src), str(dst))
            excluded_index.append(conv)
        else:
            kept_index.append(conv)

    # Save updated index (only kept + archived)
    index_path.write_text(
        json.dumps(kept_index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Save excluded index
    excluded_index_path = excluded_dir / "index.json"
    excluded_index_path.write_text(
        json.dumps(excluded_index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nApplied! {len(kept_index)} conversations kept, {len(excluded_index)} excluded.")
    print(f"Excluded files moved to: {excluded_dir}")


def cmd_stats(config: Config):
    """Show conversation stats by tier."""
    index_path = config.output_dir / "wechat" / "index.json"
    excluded_path = config.output_dir / "wechat" / "_excluded" / "index.json"

    active = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    excluded = json.loads(excluded_path.read_text(encoding="utf-8")) if excluded_path.exists() else []

    all_convs = active + excluded

    tier_stats = {}
    for c in all_convs:
        tier = c.get("metadata", {}).get("tier", "untagged")
        if tier not in tier_stats:
            tier_stats[tier] = {"count": 0, "messages": 0}
        tier_stats[tier]["count"] += 1
        tier_stats[tier]["messages"] += c.get("message_count", 0)

    print("=" * 60)
    print("WeChat Conversation Stats by Tier")
    print("=" * 60)

    for tier in ["keep", "archive", "exclude", "untagged"]:
        s = tier_stats.get(tier, {"count": 0, "messages": 0})
        if s["count"]:
            print(f"  {tier:10s}: {s['count']:4d} conversations, {s['messages']:8,d} messages")

    total_c = sum(s["count"] for s in tier_stats.values())
    total_m = sum(s["messages"] for s in tier_stats.values())
    print(f"\n  {'total':10s}: {total_c:4d} conversations, {total_m:8,d} messages")

    active_msgs = sum(c.get("message_count", 0) for c in active)
    if excluded:
        excluded_msgs = sum(c.get("message_count", 0) for c in excluded)
        print(f"\n  Active index: {len(active)} convos ({active_msgs:,} msgs)")
        print(f"  Excluded:     {len(excluded)} convos ({excluded_msgs:,} msgs)")


def cmd_add_rule(config: Config, policy_path: str, name: str, match_json: str,
                 tier: str, priority: int = 50, reason: str = ""):
    """Add a rule to the policy file."""
    from knowledge_harvester.filters.wechat_filter import FilterRule

    path = Path(policy_path)
    if path.exists():
        policy = FilterPolicy.load(str(path))
    else:
        policy = FilterPolicy()

    match = json.loads(match_json)
    rule = FilterRule(name=name, match=match, tier=tier, priority=priority, reason=reason)
    policy.rules.append(rule)
    policy.save(str(path))

    print(f"Added rule '{name}' (tier={tier}, priority={priority}) to {policy_path}")
    print(f"Total rules: {len(policy.rules)}")
