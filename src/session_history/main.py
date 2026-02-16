"""CLI entry point - Session History Categorization System"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure module can be imported correctly
sys.path.insert(0, str(Path(__file__).parent.parent))

from session_history.config.settings import Settings
from session_history.config.entity_registry import EntityRegistry
from session_history.parser.jsonl_reader import JsonlReader
from session_history.classifier.composite_classifier import CompositeClassifier
from session_history.generator.index_generator import IndexGenerator
from session_history.generator.html_generator import HtmlGenerator
from session_history.generator.markdown_generator import MarkdownGenerator
from session_history.generator.readable_replay_generator import ReadableReplayGenerator
from session_history.generator.replay_index_generator import ReplayIndexGenerator
from session_history.models.category import SessionClassification


def cmd_scan(args):
    """Scan all sessions and classify them."""
    settings = Settings()
    if args.sessions_dir:
        settings.sessions_dir = Path(args.sessions_dir)

    print("=" * 60)
    print("Session History Categorization - Scan")
    print("=" * 60)
    print(f"Sessions dir: {settings.sessions_dir}")
    print(f"Project root: {settings.project_root}")

    # Incremental mode check
    last_scan = {}
    if args.incremental and settings.scan_state_path.exists():
        with open(settings.scan_state_path, "r", encoding="utf-8") as f:
            last_scan = json.load(f)
        print("Mode: incremental scan")
    else:
        print("Mode: full scan")

    print("-" * 60)

    # 1. Discover entities
    registry = EntityRegistry(settings.project_root, settings=settings)
    entities = registry.discover_all()
    print(f"\n[1/4] Discovered {len(entities)} entities")
    for e in entities:
        print(f"  - {e.display_name} ({e.entity_type.value})")

    # 2. Read sessions
    reader = JsonlReader(
        exclude_thinking=settings.exclude_thinking,
        exclude_sidechains=settings.exclude_sidechains,
    )
    session_files = reader.list_session_files(str(settings.sessions_dir))

    # Incremental filter
    if args.incremental and last_scan:
        filtered = []
        for f in session_files:
            mtime = os.path.getmtime(f)
            last_mtime = last_scan.get("file_mtimes", {}).get(f, 0)
            if mtime > last_mtime:
                filtered.append(f)
        if not filtered:
            print(f"\n[2/4] No new or modified session files, skipping scan")
            return
        print(f"\n[2/4] Incremental scan {len(filtered)}/{len(session_files)} session files")
        session_files = filtered
    else:
        print(f"\n[2/4] Reading {len(session_files)} session files")

    sessions = []
    for fp in session_files:
        try:
            session = reader.read_session(fp)
            sessions.append(session)
            print(f"  + {Path(fp).stem[:8]}... ({session.message_count} msgs)")
        except Exception as e:
            print(f"  x {Path(fp).stem[:8]}... error: {e}")

    # 3. Classify
    print(f"\n[3/4] Classifying {len(sessions)} sessions...")
    classifier = CompositeClassifier(settings)
    classifications = []
    for session in sessions:
        classification = classifier.classify(session, entities)
        classifications.append(classification)
        if classification.matches:
            top = classification.matches[0]
            print(f"  {session.session_id[:8]}... -> {top.entity.display_name} ({top.confidence:.2f})")
            for m in classification.matches[1:3]:
                print(f"    + {m.entity.display_name} ({m.confidence:.2f})")
        else:
            print(f"  {session.session_id[:8]}... -> Uncategorized")

    # 4. Generate indices
    print(f"\n[4/4] Generating indices...")
    index_gen = IndexGenerator(settings.project_root)

    entity_refs = {}
    for classification in classifications:
        if not classification.matches:
            continue
        for match in classification.matches:
            eid = match.entity.entity_id
            if eid not in entity_refs:
                entity_refs[eid] = {"entity": match.entity, "refs": []}
            ref = classifier.build_session_reference(
                next(s for s in sessions if s.session_id == classification.session_id),
                match,
            )
            entity_refs[eid]["refs"].append(ref)

    for eid, data in entity_refs.items():
        entity = data["entity"]
        refs = data["refs"]
        entity_index = index_gen.build_entity_index(entity, refs)
        index_gen.write_entity_index(entity, entity_index)
        print(f"  + {entity.display_name}: {len(refs)} sessions")

    # Clean up empty entity indices
    for entity in entities:
        if entity.entity_id not in entity_refs:
            idx_path = settings.project_root / entity.history_dir / "sessions-index.json"
            if idx_path.exists():
                idx_path.unlink()
                print(f"  x {entity.display_name}: removed empty index")

    # Master index and report
    history_dir = settings.history_dir
    index_gen.write_master_index(classifications, history_dir)
    index_gen.write_categorization_report(classifications, entities, history_dir)

    # Uncategorized sessions
    uncategorized = [c for c in classifications if c.is_uncategorized]
    if uncategorized:
        uncat_dir = history_dir / "uncategorized"
        uncat_dir.mkdir(parents=True, exist_ok=True)
        uncat_data = {
            "sessions": [c.to_dict() for c in uncategorized],
            "count": len(uncategorized),
        }
        with open(uncat_dir / "sessions.json", "w", encoding="utf-8") as f:
            json.dump(uncat_data, f, ensure_ascii=False, indent=2)
        print(f"  + Uncategorized: {len(uncategorized)} sessions")

    # Save scan state
    scan_state = {
        "last_scan": datetime.now().isoformat(),
        "file_mtimes": {
            f: os.path.getmtime(f) for f in reader.list_session_files(str(settings.sessions_dir))
        },
    }
    history_dir.mkdir(parents=True, exist_ok=True)
    with open(settings.scan_state_path, "w", encoding="utf-8") as f:
        json.dump(scan_state, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Classified {len(classifications)} sessions")
    print(f"  Categorized: {len(classifications) - len(uncategorized)}")
    print(f"  Uncategorized: {len(uncategorized)}")
    print(f"  Master index: {history_dir / 'all-sessions.json'}")
    print(f"  Report: {history_dir / 'categorization-report.md'}")


def _load_entity_index(settings, entity_id):
    """Find entity and load its index, return (entity, entity_index, history_dir) or None."""
    registry = EntityRegistry(settings.project_root, settings=settings)
    entities = registry.discover_all()

    matched_entity = None
    for entity in entities:
        if (
            entity_id in entity.name
            or entity_id in entity.entity_id
            or entity_id.lower() in entity.display_name.lower()
        ):
            matched_entity = entity
            break

    if not matched_entity:
        print(f"No matching entity found: {entity_id}")
        print("Available entities:")
        for e in entities:
            print(f"  {e.entity_id} - {e.display_name}")
        return None

    index_path = settings.project_root / matched_entity.history_dir / "sessions-index.json"
    if not index_path.exists():
        print(f"Entity {matched_entity.display_name} has no index file. Run scan first.")
        return None

    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    from session_history.models.index import EntityIndex, SessionReference

    entity_index = EntityIndex(
        entity_id=index_data["entity_id"],
        entity_type=index_data["entity_type"],
        display_name=index_data["display_name"],
        directory=index_data["directory"],
        last_updated=index_data.get("last_updated", ""),
    )
    for s in index_data.get("sessions", []):
        ref = SessionReference(
            session_id=s["session_id"],
            file_path=s["file_path"],
            confidence=s.get("confidence", 0),
            start_time=s.get("start_time", ""),
            end_time=s.get("end_time", ""),
            message_count=s.get("message_count", 0),
        )
        entity_index.sessions.append(ref)

    history_dir = settings.project_root / matched_entity.history_dir
    return matched_entity, entity_index, history_dir


def cmd_replay(args):
    """Generate session replay."""
    settings = Settings()
    entity_id = args.entity

    result = _load_entity_index(settings, entity_id)
    if result is None:
        return
    matched_entity, entity_index, history_dir = result

    if args.raw:
        html_gen = HtmlGenerator(exclude_thinking=settings.exclude_thinking)
        html_path = history_dir / "replay.html"
        html_gen.generate(entity_index, html_path)
        print(f"HTML replay: {html_path}")

        md_gen = MarkdownGenerator(exclude_thinking=settings.exclude_thinking)
        md_path = history_dir / "replay.md"
        md_gen.generate(entity_index, md_path)
        print(f"Markdown replay: {md_path}")
    else:
        replay_gen = ReadableReplayGenerator(
            exclude_thinking=settings.exclude_thinking,
            settings=settings,
        )
        generated_files = replay_gen.generate(entity_index, history_dir)

        index_gen = ReplayIndexGenerator()
        index_gen.write_entity_index(entity_index, history_dir, generated_files)

        print(f"Readable replay for {matched_entity.display_name}:")
        for fp in generated_files:
            print(f"  {fp.name}")
        print(f"Index: {history_dir / 'replay-index.md'}")
        print(f"Total: {len(generated_files)} session file(s)")

    print(f"\nDone! Generated replay for {matched_entity.display_name}")


def cmd_search(args):
    """Search sessions."""
    settings = Settings()
    query = args.query.lower()

    reader = JsonlReader(
        exclude_thinking=settings.exclude_thinking,
        exclude_sidechains=settings.exclude_sidechains,
    )
    session_files = reader.list_session_files(str(settings.sessions_dir))

    print(f"Search: \"{args.query}\"")
    print(f"Scanning {len(session_files)} sessions...")
    print("-" * 60)

    total_matches = 0
    for fp in session_files:
        session = reader.read_session(fp)
        matches = []
        for msg in session.messages:
            text = msg.text_content.lower()
            if query in text:
                preview = msg.text_content[:120].replace("\n", " ")
                matches.append({
                    "line": msg.line_number,
                    "type": msg.role or msg.msg_type,
                    "time": msg.timestamp[:19] if msg.timestamp else "",
                    "preview": preview,
                })

        if matches:
            sid = session.session_id[:8]
            time_str = session.start_time[:10] if session.start_time else "N/A"
            print(f"\n  {sid}... ({time_str}) - {len(matches)} match(es)")
            for m in matches[:args.limit]:
                print(f"  [{m['type']:9s}] {m['time']} | {m['preview']}")
            if len(matches) > args.limit:
                print(f"  ... and {len(matches) - args.limit} more")
            total_matches += len(matches)

    print(f"\nTotal: {total_matches} matches")


def cmd_list(args):
    """List sessions with classification."""
    settings = Settings()
    master_path = settings.history_dir / "all-sessions.json"

    if not master_path.exists():
        print("Master index not found. Run scan first.")
        return

    with open(master_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("=" * 60)
    print("Session List")
    print("=" * 60)
    print(f"Total sessions: {data['total_sessions']}")
    print(f"Categorized: {data['categorized']} | Uncategorized: {data['uncategorized']}")
    print("-" * 60)

    for s in data.get("sessions", []):
        sid = s["session_id"][:8]
        time_str = s.get("start_time", "")[:10] or "N/A"
        msg_count = s.get("message_count", 0)

        matches_str = ""
        if s.get("matches"):
            match_labels = [
                f"{m['display_name']} ({m['confidence']:.2f})"
                for m in s["matches"][:3]
            ]
            matches_str = " | ".join(match_labels)
        else:
            matches_str = "Uncategorized"

        print(f"\n  {sid}... | {time_str} | {msg_count:3d} msgs")
        print(f"    -> {matches_str}")

    if args.type:
        filtered = [
            s for s in data.get("sessions", [])
            if any(m.get("entity_id", "").startswith(args.type) for m in s.get("matches", []))
        ]
        print(f"\n--- Filtered by type '{args.type}': {len(filtered)} sessions ---")


def cmd_stats(args):
    """Show classification statistics."""
    settings = Settings()
    master_path = settings.history_dir / "all-sessions.json"

    if not master_path.exists():
        print("Master index not found. Run scan first.")
        return

    with open(master_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("=" * 60)
    print("Classification Statistics")
    print("=" * 60)

    total = data["total_sessions"]
    categorized = data["categorized"]
    uncategorized = data["uncategorized"]

    print(f"\nTotal sessions: {total}")
    pct = (categorized / total * 100) if total else 0
    bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
    print(f"Coverage:     [{bar}] {pct:.1f}%")
    print(f"Categorized: {categorized} | Uncategorized: {uncategorized}")

    type_counts = {}
    entity_counts = {}
    for s in data.get("sessions", []):
        for m in s.get("matches", []):
            etype = m.get("entity_id", "unknown").split(":")[0]
            ename = m.get("display_name", "unknown")
            type_counts[etype] = type_counts.get(etype, 0) + 1
            entity_counts[ename] = entity_counts.get(ename, 0) + 1

    print("\nBy type:")
    for etype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {etype:15s}: {count} sessions")

    print("\nBy entity (Top 10):")
    for ename, count in sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {ename:40s}: {count} sessions")

    multi_classified = sum(
        1 for s in data.get("sessions", [])
        if len(s.get("matches", [])) > 1
    )
    print(f"\nMulti-classified sessions: {multi_classified} ({multi_classified/total*100:.1f}% of total)" if total else "")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Session History Categorization System - classify and replay Claude Code sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan sessions and classify")
    p_scan.add_argument("--sessions-dir", help="Sessions JSONL directory")
    p_scan.add_argument("--incremental", "-i", action="store_true", help="Incremental scan")

    # replay
    p_replay = subparsers.add_parser("replay", help="Generate session replay")
    p_replay.add_argument("entity", help="Entity identifier (number, name, or entity_id)")
    p_replay.add_argument("--raw", action="store_true", help="Use raw format (single-file HTML/Markdown)")

    # search
    p_search = subparsers.add_parser("search", help="Search session content")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--limit", "-n", type=int, default=5, help="Max matches per session to show")

    # list
    p_list = subparsers.add_parser("list", help="List sessions with classification")
    p_list.add_argument("--type", "-t", help="Filter by entity type")

    # stats
    p_stats = subparsers.add_parser("stats", help="Show classification statistics")

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "replay":
        cmd_replay(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
