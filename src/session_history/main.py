"""CLI 入口 - 会话历史分类系统"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 确保模块可以被正确导入
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
from session_history.models.category import Entity, EntityMatch, EntityType, SessionClassification
from session_history.models.index import SessionReference


def cmd_scan(args):
    """扫描所有会话并分类"""
    settings = Settings()
    if args.sessions_dir:
        settings.sessions_dir = Path(args.sessions_dir)

    print("=" * 60)
    print("会话历史分类系统 - 扫描")
    print("=" * 60)
    print(f"会话目录: {settings.sessions_dir}")
    print(f"项目根: {settings.project_root}")

    # 增量模式检查
    last_scan = {}
    if args.incremental and settings.scan_state_path.exists():
        with open(settings.scan_state_path, "r", encoding="utf-8") as f:
            last_scan = json.load(f)
        print("模式: 增量扫描")
    else:
        print("模式: 全量扫描")

    print("-" * 60)

    # 1. 发现实体
    registry = EntityRegistry(settings.project_root, history_root=settings.history_root)
    entities = registry.discover_all()
    print(f"\n[1/4] 发现 {len(entities)} 个实体")
    for e in entities:
        print(f"  - {e.display_name} ({e.entity_type.value})")

    # 2. 读取会话
    reader = JsonlReader(
        exclude_thinking=settings.exclude_thinking,
        exclude_sidechains=settings.exclude_sidechains,
    )
    session_files = reader.list_session_files(str(settings.sessions_dir))

    # 增量过滤
    if args.incremental and last_scan:
        filtered = []
        for f in session_files:
            mtime = os.path.getmtime(f)
            last_mtime = last_scan.get("file_mtimes", {}).get(f, 0)
            if mtime > last_mtime:
                filtered.append(f)
        if not filtered:
            print(f"\n[2/4] 无新增或修改的会话文件，跳过扫描")
            return
        print(f"\n[2/4] 增量扫描 {len(filtered)}/{len(session_files)} 个会话文件")
        session_files = filtered
    else:
        print(f"\n[2/4] 读取 {len(session_files)} 个会话文件")

    sessions = []
    for fp in session_files:
        try:
            session = reader.read_session(fp)
            sessions.append(session)
            print(f"  ✓ {Path(fp).stem[:8]}... ({session.message_count} msgs)")
        except Exception as e:
            print(f"  ✗ {Path(fp).stem[:8]}... 错误: {e}")

    # 3. 分类
    print(f"\n[3/4] 分类 {len(sessions)} 个会话...")
    classifier = CompositeClassifier(settings)
    new_classifications = []
    for session in sessions:
        classification = classifier.classify(session, entities)
        new_classifications.append(classification)
        if classification.matches:
            top = classification.matches[0]
            print(f"  {session.session_id[:8]}... -> {top.entity.display_name} ({top.confidence:.2f})")
            for m in classification.matches[1:3]:
                print(f"    + {m.entity.display_name} ({m.confidence:.2f})")
        else:
            print(f"  {session.session_id[:8]}... -> Uncategorized")

    # 增量模式: 合并新分类到已有分类
    history_dir = settings.history_dir
    if args.incremental:
        classifications = _merge_classifications(new_classifications, history_dir)
    else:
        classifications = new_classifications

    # 4. 生成索引
    print(f"\n[4/4] 生成索引...")
    index_gen = IndexGenerator(settings.project_root)

    # 按实体生成索引 (session 归入所有匹配的实体, 支持多实体 session 拆分)
    entity_refs = {}  # entity_id -> [SessionReference]
    # 为合并后的全量分类构建引用, 需要加载所有 session 对象
    all_sessions_map = {s.session_id: s for s in sessions}  # 已加载的 session
    for classification in classifications:
        if not classification.matches:
            continue
        for match in classification.matches:
            eid = match.entity.entity_id
            if eid not in entity_refs:
                entity_refs[eid] = {"entity": match.entity, "refs": []}
            # 尝试从已加载 session 获取, 否则从分类记录构建 ref
            loaded_session = all_sessions_map.get(classification.session_id)
            if loaded_session:
                ref = classifier.build_session_reference(loaded_session, match)
            else:
                ref = SessionReference(
                    session_id=classification.session_id,
                    file_path=classification.file_path,
                    confidence=match.confidence,
                    start_time=classification.start_time,
                    end_time=classification.end_time,
                    message_count=classification.message_count,
                )
            entity_refs[eid]["refs"].append(ref)

    for eid, data in entity_refs.items():
        entity = data["entity"]
        refs = data["refs"]
        entity_index = index_gen.build_entity_index(entity, refs)
        index_gen.write_entity_index(entity, entity_index)
        print(f"  ✓ {entity.display_name}: {len(refs)} 会话")

    # 清理不再有 session 的实体索引
    for entity in entities:
        if entity.entity_id not in entity_refs:
            idx_path = settings.project_root / entity.history_dir / "sessions-index.json"
            if idx_path.exists():
                idx_path.unlink()
                print(f"  ✗ {entity.display_name}: 已移除空索引")

    # 主索引和报告
    index_gen.write_master_index(classifications, history_dir)
    index_gen.write_categorization_report(classifications, entities, history_dir)

    # 未分类会话
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

        # 生成未分类会话的回放文件
        uncat_sessions = []
        for c in uncategorized:
            s = all_sessions_map.get(c.session_id)
            if not s:
                # 增量模式: 从文件加载未重新扫描的 session
                fp = c.file_path
                if fp and Path(fp).exists():
                    s = reader.read_session(fp)
            if s:
                uncat_sessions.append(s)
        if uncat_sessions:
            replay_gen = ReadableReplayGenerator(exclude_thinking=settings.exclude_thinking)
            uncat_files = replay_gen.generate_uncategorized(uncat_sessions, history_dir)
            print(f"  ✓ Uncategorized: {len(uncategorized)} 会话, {len(uncat_files)} 回放文件")
    else:
        # 清理空的 uncategorized 目录
        uncat_replay = history_dir / "uncategorized" / "replay"
        if uncat_replay.exists():
            for old_file in uncat_replay.glob("*.md"):
                old_file.unlink()
        uncat_json = history_dir / "uncategorized" / "sessions.json"
        if uncat_json.exists():
            with open(uncat_json, "w", encoding="utf-8") as f:
                json.dump({"sessions": [], "count": 0}, f, ensure_ascii=False, indent=2)

    # 保存扫描状态 (用于增量扫描)
    scan_state = {
        "last_scan": datetime.now().isoformat(),
        "file_mtimes": {
            f: os.path.getmtime(f) for f in reader.list_session_files(str(settings.sessions_dir))
        },
    }
    history_dir.mkdir(parents=True, exist_ok=True)
    with open(settings.scan_state_path, "w", encoding="utf-8") as f:
        json.dump(scan_state, f, ensure_ascii=False, indent=2)

    print(f"\n完成! 分类 {len(classifications)} 个会话")
    print(f"  已分类: {len(classifications) - len(uncategorized)}")
    print(f"  未分类: {len(uncategorized)}")
    print(f"  主索引: {history_dir / 'all-sessions.json'}")
    print(f"  报告: {history_dir / 'categorization-report.md'}")


def _merge_classifications(new_classifications, history_dir):
    """增量扫描时, 合并新分类到已有的 all-sessions.json"""
    master_path = history_dir / "all-sessions.json"
    if not master_path.exists():
        return new_classifications

    with open(master_path, "r", encoding="utf-8") as f:
        existing_data = json.load(f)

    # 用 session_id 做 key, 新分类覆盖旧分类
    new_ids = {c.session_id for c in new_classifications}

    # 从旧数据重建 SessionClassification 对象 (仅保留未被重新扫描的)
    merged = list(new_classifications)
    for s in existing_data.get("sessions", []):
        if s["session_id"] in new_ids:
            continue  # 已被重新扫描, 使用新结果
        # 重建 SessionClassification
        matches = []
        for m in s.get("matches", []):
            eid = m.get("entity_id", "")
            etype_str, _, ename = eid.partition(":")
            try:
                etype = EntityType(etype_str)
            except ValueError:
                continue
            entity = Entity(
                entity_type=etype,
                name=ename,
                display_name=m.get("display_name", ename),
                directory="",
            )
            matches.append(EntityMatch(
                entity=entity,
                confidence=m.get("confidence", 0),
                file_path_score=m.get("file_path_score", 0),
                text_pattern_score=m.get("text_pattern_score", 0),
                keyword_score=m.get("keyword_score", 0),
                matched_messages=m.get("matched_messages", 0),
                total_messages=m.get("total_messages", 0),
                evidence=m.get("evidence", []),
            ))
        classification = SessionClassification(
            session_id=s["session_id"],
            file_path=s.get("file_path", ""),
            matches=matches,
            start_time=s.get("start_time", ""),
            end_time=s.get("end_time", ""),
            message_count=s.get("message_count", 0),
            user_message_count=s.get("user_message_count", 0),
        )
        merged.append(classification)

    return merged


def _load_entity_index(settings, entity_id):
    """查找实体并加载其索引, 返回 (entity, entity_index, history_dir) 或 None"""
    registry = EntityRegistry(settings.project_root, history_root=settings.history_root)
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
        print(f"未找到匹配的实体: {entity_id}")
        print("可用实体:")
        for e in entities:
            print(f"  {e.entity_id} - {e.display_name}")
        return None

    index_path = settings.project_root / matched_entity.history_dir / "sessions-index.json"
    if not index_path.exists():
        print(f"实体 {matched_entity.display_name} 没有索引文件。请先运行 scan。")
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
    """生成会话回放"""
    settings = Settings()
    entity_id = args.entity

    # 特殊处理: replay uncategorized
    if entity_id.lower() in ("uncategorized", "uncat"):
        _replay_uncategorized(settings)
        return

    result = _load_entity_index(settings, entity_id)
    if result is None:
        return
    matched_entity, entity_index, history_dir = result

    if args.raw:
        # 旧格式: 单文件 HTML + Markdown
        html_gen = HtmlGenerator(exclude_thinking=settings.exclude_thinking)
        html_path = history_dir / "replay.html"
        html_gen.generate(entity_index, html_path)
        print(f"HTML 回放: {html_path}")

        md_gen = MarkdownGenerator(exclude_thinking=settings.exclude_thinking)
        md_path = history_dir / "replay.md"
        md_gen.generate(entity_index, md_path)
        print(f"Markdown 回放: {md_path}")
    else:
        # 新格式: 按 session 的可读回放文件
        replay_gen = ReadableReplayGenerator(exclude_thinking=settings.exclude_thinking)
        generated_files = replay_gen.generate(entity_index, history_dir)

        # 生成 replay-index.md
        index_gen = ReplayIndexGenerator()
        index_gen.write_entity_index(entity_index, history_dir, generated_files)

        print(f"Readable replay for {matched_entity.display_name}:")
        for fp in generated_files:
            print(f"  {fp.name}")
        print(f"Index: {history_dir / 'replay-index.md'}")
        print(f"Total: {len(generated_files)} session file(s)")

    print(f"\n完成! 为 {matched_entity.display_name} 生成了回放文件")


def _replay_uncategorized(settings):
    """生成未分类会话的回放"""
    history_dir = settings.history_dir
    uncat_json = history_dir / "uncategorized" / "sessions.json"

    if not uncat_json.exists():
        print("没有未分类会话。请先运行 scan。")
        return

    with open(uncat_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    reader = JsonlReader(
        exclude_thinking=settings.exclude_thinking,
        exclude_sidechains=settings.exclude_sidechains,
    )

    sessions = []
    for s in data.get("sessions", []):
        fp = s.get("file_path", "")
        if fp and Path(fp).exists():
            sessions.append(reader.read_session(fp))

    if not sessions:
        print("未分类会话的 JSONL 文件不存在。")
        return

    replay_gen = ReadableReplayGenerator(exclude_thinking=settings.exclude_thinking)
    generated_files = replay_gen.generate_uncategorized(sessions, history_dir)

    print(f"Readable replay for Uncategorized sessions:")
    for fp in generated_files:
        print(f"  {fp.name}")
    print(f"Output: {history_dir / 'uncategorized' / 'replay'}")
    print(f"Total: {len(generated_files)} session file(s)")
    print(f"\n完成! 为 {len(generated_files)} 个未分类会话生成了回放文件")


def cmd_search(args):
    """搜索会话"""
    settings = Settings()
    query = args.query.lower()

    reader = JsonlReader(
        exclude_thinking=settings.exclude_thinking,
        exclude_sidechains=settings.exclude_sidechains,
    )
    session_files = reader.list_session_files(str(settings.sessions_dir))

    print(f"搜索: \"{args.query}\"")
    print(f"扫描 {len(session_files)} 个会话...")
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
            print(f"\n📁 {sid}... ({time_str}) - {len(matches)} match(es)")
            for m in matches[:args.limit]:
                print(f"  [{m['type']:9s}] {m['time']} | {m['preview']}")
            if len(matches) > args.limit:
                print(f"  ... and {len(matches) - args.limit} more")
            total_matches += len(matches)

    print(f"\n总计: {total_matches} 匹配")


def cmd_list(args):
    """列出会话及分类"""
    settings = Settings()
    master_path = settings.history_dir / "all-sessions.json"

    if not master_path.exists():
        print("主索引不存在。请先运行 scan。")
        return

    with open(master_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("=" * 60)
    print("会话列表")
    print("=" * 60)
    print(f"总会话数: {data['total_sessions']}")
    print(f"已分类: {data['categorized']} | 未分类: {data['uncategorized']}")
    print("-" * 60)

    for s in data.get("sessions", []):
        sid = s["session_id"][:8]
        time_str = s.get("start_time", "")[:10] or "N/A"
        msg_count = s.get("message_count", 0)
        primary = s.get("primary_entity", "Uncategorized")

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
        print(f"    → {matches_str}")

    # 按类型筛选
    if args.type:
        filtered = [
            s for s in data.get("sessions", [])
            if any(m.get("entity_id", "").startswith(args.type) for m in s.get("matches", []))
        ]
        print(f"\n--- Filtered by type '{args.type}': {len(filtered)} sessions ---")


def cmd_stats(args):
    """显示分类统计"""
    settings = Settings()
    master_path = settings.history_dir / "all-sessions.json"

    if not master_path.exists():
        print("主索引不存在。请先运行 scan。")
        return

    with open(master_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("=" * 60)
    print("分类统计")
    print("=" * 60)

    total = data["total_sessions"]
    categorized = data["categorized"]
    uncategorized = data["uncategorized"]

    print(f"\n总会话数: {total}")
    pct = (categorized / total * 100) if total else 0
    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    print(f"分类率:   [{bar}] {pct:.1f}%")
    print(f"已分类: {categorized} | 未分类: {uncategorized}")

    # 按实体类型统计
    type_counts = {}
    entity_counts = {}
    for s in data.get("sessions", []):
        for m in s.get("matches", []):
            etype = m.get("entity_id", "unknown").split(":")[0]
            ename = m.get("display_name", "unknown")
            type_counts[etype] = type_counts.get(etype, 0) + 1
            entity_counts[ename] = entity_counts.get(ename, 0) + 1

    print("\n按类型:")
    for etype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {etype:15s}: {count} 会话")

    print("\n按实体 (Top 10):")
    for ename, count in sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {ename:40s}: {count} 会话")

    # 多分类统计
    multi_classified = sum(
        1 for s in data.get("sessions", [])
        if len(s.get("matches", [])) > 1
    )
    print(f"\n多分类会话: {multi_classified} ({multi_classified/total*100:.1f}% of total)" if total else "")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="会话历史分类系统 - 分类和回放 Claude Code 会话",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # scan
    p_scan = subparsers.add_parser("scan", help="扫描会话并分类")
    p_scan.add_argument("--sessions-dir", help="会话 JSONL 目录")
    p_scan.add_argument("--incremental", "-i", action="store_true", help="增量扫描")

    # replay
    p_replay = subparsers.add_parser("replay", help="生成会话回放")
    p_replay.add_argument("entity", help="实体标识 (编号、名称或 entity_id)")
    p_replay.add_argument("--raw", action="store_true", help="使用旧格式 (单文件 HTML/Markdown)")

    # search
    p_search = subparsers.add_parser("search", help="搜索会话内容")
    p_search.add_argument("query", help="搜索关键词")
    p_search.add_argument("--limit", "-n", type=int, default=5, help="每个会话显示的最大匹配数")

    # list
    p_list = subparsers.add_parser("list", help="列出会话及分类")
    p_list.add_argument("--type", "-t", help="按实体类型筛选")

    # stats
    p_stats = subparsers.add_parser("stats", help="显示分类统计")

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
