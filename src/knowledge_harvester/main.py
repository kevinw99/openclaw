"""CLI 入口 - 知识收割机"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_harvester.config import Config
from knowledge_harvester.storage import Storage
from knowledge_harvester.adapters.chatgpt import ChatGPTAdapter


def _get_config(args) -> Config:
    config = Config()
    if hasattr(args, "output") and args.output:
        config.output_root = args.output
    return config


def _run_extraction(storage, adapter, platform, source="", incremental=False,
                    skip_compat_check=False):
    """通用提取逻辑 (支持增量模式)"""
    # 兼容性检查
    if not skip_compat_check:
        warnings = adapter.check_compatibility()
        if warnings:
            print("⚠ 兼容性警告:")
            for w in warnings:
                print(f"  - {w}")
            print()

    state = storage.load_state(platform) if incremental else {"last_run": "", "conversations": {}}
    known_ids = set(state.get("conversations", {}).keys()) if incremental else set()

    if incremental:
        print(f"增量模式: 已知 {len(known_ids)} 段对话")
        if state.get("last_run"):
            print(f"上次提取: {state['last_run']}")

    count = 0
    skipped = 0
    for conversation in adapter.extract(source):
        if incremental and not storage.is_conversation_changed(platform, conversation):
            skipped += 1
            continue

        storage.save_conversation(conversation)
        storage.update_state_for_conversation(state, conversation)
        count += 1
        print(f"  ✓ [{count}] {conversation.title[:50]} ({conversation.message_count} msgs)")

    if incremental:
        storage.save_state(platform, state)

    print("-" * 60)
    print(f"完成! 导入 {count} 段对话" + (f", 跳过 {skipped} 段未变化" if skipped else ""))
    return count


def cmd_import_chatgpt(args):
    """导入 ChatGPT 导出数据"""
    config = _get_config(args)
    storage = Storage(config)
    adapter = ChatGPTAdapter()

    print("=" * 60)
    print("知识收割机 - 导入 ChatGPT")
    print("=" * 60)
    print(f"数据源: {args.source}")
    print(f"输出目录: {config.output_dir}")
    print("-" * 60)

    _run_extraction(storage, adapter, "chatgpt", source=args.source,
                    incremental=getattr(args, "incremental", False))


def cmd_scrape_grok(args):
    """从 Grok 网页提取对话"""
    from knowledge_harvester.adapters.grok import GrokAdapter
    from knowledge_harvester.browser_client import BrowserClient

    config = _get_config(args)
    storage = Storage(config)
    browser = BrowserClient(base_url=args.browser_url, profile=args.profile)
    adapter = GrokAdapter(browser)

    print("=" * 60)
    print("知识收割机 - 提取 Grok 对话")
    print("=" * 60)
    print(f"浏览器: {args.browser_url} (profile: {args.profile})")
    print(f"输出目录: {config.output_dir}")
    print("-" * 60)

    _run_extraction(storage, adapter, "grok",
                    incremental=getattr(args, "incremental", False))


def cmd_scrape_doubao(args):
    """从豆包网页提取对话"""
    from knowledge_harvester.adapters.doubao import DoubaoAdapter
    from knowledge_harvester.browser_client import BrowserClient

    config = _get_config(args)
    storage = Storage(config)
    browser = BrowserClient(base_url=args.browser_url, profile=args.profile)
    adapter = DoubaoAdapter(browser)

    print("=" * 60)
    print("知识收割机 - 提取豆包对话")
    print("=" * 60)
    print(f"浏览器: {args.browser_url} (profile: {args.profile})")
    print(f"输出目录: {config.output_dir}")
    print("-" * 60)

    _run_extraction(storage, adapter, "doubao",
                    incremental=getattr(args, "incremental", False))


def cmd_extract_wechat(args):
    """提取微信对话"""
    from knowledge_harvester.adapters.wechat import WeChatAdapter

    config = _get_config(args)
    storage = Storage(config)

    db_key = args.key or ""
    if args.key_file:
        db_key = Path(args.key_file).read_text().strip()

    adapter = WeChatAdapter(db_key=db_key, data_dir=args.data_dir or "")

    print("=" * 60)
    print("知识收割机 - 提取微信对话")
    print("=" * 60)
    print(f"密钥: {'已提供' if db_key else '未提供 (尝试无加密模式)'}")
    print(f"输出目录: {config.output_dir}")
    print("-" * 60)

    _run_extraction(storage, adapter, "wechat", source=args.source or "",
                    incremental=getattr(args, "incremental", False))


def cmd_search(args):
    """搜索已导入的对话"""
    from knowledge_harvester.search import SearchEngine

    config = _get_config(args)
    engine = SearchEngine(config)

    query = args.query
    platform = args.platform

    print(f"搜索: \"{query}\"" + (f" (平台: {platform})" if platform else ""))
    print("-" * 60)

    results = engine.search(query, platform=platform, max_results=args.limit)

    if not results:
        print("未找到匹配结果。")
        return

    for r in results:
        ts = r.message.timestamp[:19] if r.message.timestamp else ""
        preview = r.message.content[:120].replace("\n", " ")
        print(f"\n  [{r.platform}] {r.title[:40]}")
        print(f"  {r.message.role:9s} | {ts} | {preview}")

    print(f"\n共 {len(results)} 条结果")


def cmd_list(args):
    """列出已导入的对话"""
    config = _get_config(args)
    storage = Storage(config)

    platforms = storage.list_platforms()
    if not platforms:
        print("暂无已导入的对话。")
        return

    for platform in platforms:
        conversations = storage.list_conversations(platform)
        print(f"\n[{platform}] {len(conversations)} 段对话")
        for conv in conversations:
            title = conv.get("title", "(无标题)")[:50]
            msg_count = conv.get("message_count", 0)
            print(f"  {conv['id'][:8]}... | {title} | {msg_count} msgs")


def cmd_view(args):
    """查看完整对话"""
    import json as _json
    config = _get_config(args)
    storage = Storage(config)

    query = args.conversation.lower()
    limit = args.limit

    # Search across all platforms for matching conversation
    platforms = storage.list_platforms()
    matches = []
    for platform in platforms:
        for conv in storage.list_conversations(platform):
            conv_id = conv["id"]
            title = conv.get("title", "")
            # Match by ID prefix or title substring
            if (query in conv_id.lower() or query in title.lower()):
                matches.append((platform, conv))

    if not matches:
        print(f"未找到匹配 \"{args.conversation}\" 的对话。")
        print("提示: 使用 'list' 命令查看所有对话, 或 'search' 搜索消息内容。")
        return

    if len(matches) > 1 and not args.all:
        print(f"找到 {len(matches)} 段匹配的对话:")
        for platform, conv in matches[:20]:
            title = conv.get("title", "(无标题)")[:50]
            msg_count = conv.get("message_count", 0)
            print(f"  [{platform}] {conv['id'][:30]}... | {title} | {msg_count} msgs")
        if len(matches) > 20:
            print(f"  ... 还有 {len(matches) - 20} 段")
        print("\n请使用更具体的名称, 或加 --all 查看所有匹配。")
        return

    for platform, conv in matches[:5] if not args.all else matches:
        conv_id = conv["id"]
        title = conv.get("title", "(无标题)")
        msg_count = conv.get("message_count", 0)

        print(f"\n{'=' * 60}")
        print(f"[{platform}] {title}")
        print(f"ID: {conv_id} | {msg_count} 条消息")
        print(f"{'=' * 60}")

        path = config.conversation_path(platform, conv_id)
        if not path.exists():
            print("  (文件不存在)")
            continue

        shown = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = _json.loads(line)
                except _json.JSONDecodeError:
                    continue

                role = data.get("role", "?")
                ts = data.get("timestamp", "")[:19]
                content = data.get("content", "")

                # Truncate very long messages
                if len(content) > 500:
                    content = content[:500] + "..."

                marker = "→" if role == "user" else "←"
                print(f"\n{marker} [{ts}] {role}")
                print(f"  {content}")
                shown += 1
                if limit and shown >= limit:
                    remaining = msg_count - shown
                    if remaining > 0:
                        print(f"\n  ... 还有 {remaining} 条消息 (使用 --limit 0 查看全部)")
                    break


def cmd_stats(args):
    """显示统计信息"""
    from knowledge_harvester.search import SearchEngine

    config = _get_config(args)
    engine = SearchEngine(config)

    s = engine.stats()
    if not s["platforms"]:
        print("暂无已导入的对话。")
        return

    print("=" * 60)
    print("知识库统计")
    print("=" * 60)

    for plat, data in s["platforms"].items():
        print(f"  {plat}: {data['conversations']} 段对话, {data['messages']} 条消息")

    print(f"\n总计: {s['total_conversations']} 段对话, {s['total_messages']} 条消息")
    print(f"平台数: {len(s['platforms'])}")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="知识收割机 - 多平台对话历史提取系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
支持的平台:
  chatgpt   — 官方 JSON 导出 (Settings > Data Controls > Export)
  grok      — 浏览器自动化 (需要 OpenClaw 网关)
  doubao    — 浏览器自动化 (需要 OpenClaw 网关)
  wechat    — 本地 SQLite 数据库 (需要解密密钥)

示例:
  python3 -m knowledge_harvester import-chatgpt ~/Downloads/chatgpt-export.zip
  python3 -m knowledge_harvester scrape-grok
  python3 -m knowledge_harvester search "Python 装饰器"
        """,
    )
    parser.add_argument("--output", "-o", help="输出目录 (默认: 知识库/conversations)")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 公共参数
    _incremental_help = "增量模式: 跳过未变化的对话"

    # import-chatgpt
    p_chatgpt = subparsers.add_parser("import-chatgpt", help="导入 ChatGPT 导出数据")
    p_chatgpt.add_argument("source", help="ChatGPT 导出的 ZIP 或 conversations.json 路径")
    p_chatgpt.add_argument("--incremental", "-i", action="store_true", help=_incremental_help)

    # scrape-grok
    p_grok = subparsers.add_parser("scrape-grok", help="从 Grok 网页提取对话")
    p_grok.add_argument("--browser-url", default="http://127.0.0.1:18791",
                        help="OpenClaw 浏览器服务地址")
    p_grok.add_argument("--profile", default="chrome", help="浏览器 profile 名")
    p_grok.add_argument("--incremental", "-i", action="store_true", help=_incremental_help)

    # scrape-doubao
    p_doubao = subparsers.add_parser("scrape-doubao", help="从豆包网页提取对话")
    p_doubao.add_argument("--browser-url", default="http://127.0.0.1:18791",
                          help="OpenClaw 浏览器服务地址")
    p_doubao.add_argument("--profile", default="chrome", help="浏览器 profile 名")
    p_doubao.add_argument("--incremental", "-i", action="store_true", help=_incremental_help)

    # extract-wechat
    p_wechat = subparsers.add_parser("extract-wechat", help="提取微信对话")
    p_wechat.add_argument("--key", help="SQLCipher 密钥 (64位十六进制)")
    p_wechat.add_argument("--key-file", help="包含密钥的文件路径")
    p_wechat.add_argument("--data-dir", help="微信数据目录 (默认自动检测)")
    p_wechat.add_argument("--incremental", "-i", action="store_true", help=_incremental_help)
    p_wechat.add_argument("source", nargs="?", default="",
                          help="数据库文件或目录路径 (默认自动检测)")

    # search
    p_search = subparsers.add_parser("search", help="搜索对话内容")
    p_search.add_argument("query", help="搜索关键词")
    p_search.add_argument("--platform", "-p", help="限定搜索平台")
    p_search.add_argument("--limit", "-n", type=int, default=20, help="最大结果数")

    # view
    p_view = subparsers.add_parser("view", help="查看完整对话")
    p_view.add_argument("conversation", help="对话 ID 或标题关键词")
    p_view.add_argument("--limit", "-n", type=int, default=100, help="显示消息数 (0=全部)")
    p_view.add_argument("--all", "-a", action="store_true", help="查看所有匹配的对话")

    # list
    subparsers.add_parser("list", help="列出已导入的对话")

    # stats
    subparsers.add_parser("stats", help="显示统计信息")

    args = parser.parse_args()

    commands = {
        "import-chatgpt": cmd_import_chatgpt,
        "scrape-grok": cmd_scrape_grok,
        "scrape-doubao": cmd_scrape_doubao,
        "extract-wechat": cmd_extract_wechat,
        "search": cmd_search,
        "view": cmd_view,
        "list": cmd_list,
        "stats": cmd_stats,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
