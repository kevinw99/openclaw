"""端到端测试 (需要真实环境)

这些测试需要真实的平台账号或数据, 不能在 CI 中自动运行。
手动运行: python3 -m pytest knowledge_harvester/tests/test_e2e.py -v -k <test_name>

前置条件:
  - ChatGPT: 需要一个真实的 ChatGPT 导出文件 (ZIP)
  - Grok/Doubao: 需要 OpenClaw 网关 + Chrome 扩展 + 已登录账号
  - WeChat: 需要 SQLCipher 密钥或未加密的数据库
"""

import os
import pytest
from pathlib import Path

from knowledge_harvester.config import Config
from knowledge_harvester.storage import Storage

# 跳过标记: 除非设置环境变量, 否则跳过所有 e2e 测试
pytestmark = pytest.mark.skipif(
    not os.environ.get("KH_E2E"),
    reason="端到端测试需要设置 KH_E2E=1 环境变量"
)


def _make_e2e_storage(tmp_path: Path) -> Storage:
    """创建 e2e 测试用 Storage"""
    config = Config()
    output_dir = tmp_path / "e2e_output"
    config.__class__ = type("E2EConfig", (Config,), {
        "output_dir": property(lambda self: output_dir),
        "platform_dir": lambda self, p: output_dir / p,
        "conversation_path": lambda self, p, cid: output_dir / p / f"{cid}.jsonl",
        "index_path": lambda self, p: output_dir / p / "index.json",
        "state_path": lambda self, p: output_dir / p / "state.json",
    })
    return Storage(config)


# --- ChatGPT E2E ---

class TestChatGPTE2E:
    """ChatGPT 端到端测试 (需要 KH_CHATGPT_EXPORT 环境变量)"""

    @pytest.fixture
    def export_path(self):
        path = os.environ.get("KH_CHATGPT_EXPORT", "")
        if not path or not Path(path).exists():
            pytest.skip("需要设置 KH_CHATGPT_EXPORT 指向 ChatGPT 导出文件")
        return path

    def test_import_real_export(self, tmp_path, export_path):
        from knowledge_harvester.adapters.chatgpt import ChatGPTAdapter

        storage = _make_e2e_storage(tmp_path)
        adapter = ChatGPTAdapter()

        conversations = list(adapter.extract(export_path))
        assert len(conversations) > 0, "应该至少提取一段对话"

        # 保存并验证
        for conv in conversations:
            storage.save_conversation(conv)

        assert len(storage.list_conversations("chatgpt")) > 0

    def test_incremental_reimport(self, tmp_path, export_path):
        from knowledge_harvester.adapters.chatgpt import ChatGPTAdapter

        storage = _make_e2e_storage(tmp_path)
        adapter = ChatGPTAdapter()

        # 第一次导入
        state = {"last_run": "", "conversations": {}}
        count1 = 0
        for conv in adapter.extract(export_path):
            storage.save_conversation(conv)
            storage.update_state_for_conversation(state, conv)
            count1 += 1
        storage.save_state("chatgpt", state)

        # 第二次导入 (应该全部跳过)
        count2 = 0
        for conv in adapter.extract(export_path):
            if storage.is_conversation_changed("chatgpt", conv):
                count2 += 1

        assert count2 == 0, f"增量导入应跳过所有对话, 但发现 {count2} 段有变化"


# --- Grok E2E ---

class TestGrokE2E:
    """Grok 端到端测试 (需要 OpenClaw 网关 + Chrome 已登录 grok.com)"""

    def test_compatibility_check(self):
        from knowledge_harvester.adapters.grok import GrokAdapter
        from knowledge_harvester.browser_client import BrowserClient

        browser = BrowserClient()
        if not browser.is_ready():
            pytest.skip("OpenClaw 浏览器网关未启动")

        adapter = GrokAdapter(browser)
        warnings = adapter.check_compatibility()

        # 打印警告 (不一定失败, 但应检查)
        for w in warnings:
            print(f"  WARNING: {w}")

    def test_extract_conversations(self, tmp_path):
        from knowledge_harvester.adapters.grok import GrokAdapter
        from knowledge_harvester.browser_client import BrowserClient

        browser = BrowserClient()
        if not browser.is_ready():
            pytest.skip("OpenClaw 浏览器网关未启动")

        storage = _make_e2e_storage(tmp_path)
        adapter = GrokAdapter(browser)

        conversations = list(adapter.extract())
        print(f"  提取了 {len(conversations)} 段 Grok 对话")

        for conv in conversations:
            storage.save_conversation(conv)
            print(f"  - {conv.title[:50]} ({conv.message_count} msgs)")

        assert len(conversations) >= 0  # 可能没有对话, 但不应崩溃


# --- Doubao E2E ---

class TestDoubaoE2E:
    """豆包端到端测试 (需要 OpenClaw 网关 + Chrome 已登录 doubao.com)"""

    def test_compatibility_check(self):
        from knowledge_harvester.adapters.doubao import DoubaoAdapter
        from knowledge_harvester.browser_client import BrowserClient

        browser = BrowserClient()
        if not browser.is_ready():
            pytest.skip("OpenClaw 浏览器网关未启动")

        adapter = DoubaoAdapter(browser)
        warnings = adapter.check_compatibility()

        for w in warnings:
            print(f"  WARNING: {w}")

    def test_extract_conversations(self, tmp_path):
        from knowledge_harvester.adapters.doubao import DoubaoAdapter
        from knowledge_harvester.browser_client import BrowserClient

        browser = BrowserClient()
        if not browser.is_ready():
            pytest.skip("OpenClaw 浏览器网关未启动")

        storage = _make_e2e_storage(tmp_path)
        adapter = DoubaoAdapter(browser)

        conversations = list(adapter.extract())
        print(f"  提取了 {len(conversations)} 段豆包对话")

        for conv in conversations:
            storage.save_conversation(conv)


# --- WeChat E2E ---

class TestWeChatE2E:
    """微信端到端测试 (需要 KH_WECHAT_KEY 或未加密数据库)"""

    def test_compatibility_check(self):
        from knowledge_harvester.adapters.wechat import WeChatAdapter

        adapter = WeChatAdapter()
        warnings = adapter.check_compatibility()

        for w in warnings:
            print(f"  WARNING: {w}")

    def test_extract_with_key(self, tmp_path):
        from knowledge_harvester.adapters.wechat import WeChatAdapter

        key = os.environ.get("KH_WECHAT_KEY", "")
        if not key:
            pytest.skip("需要设置 KH_WECHAT_KEY 环境变量")

        storage = _make_e2e_storage(tmp_path)
        adapter = WeChatAdapter(db_key=key)

        conversations = list(adapter.extract())
        print(f"  提取了 {len(conversations)} 段微信对话")

        for conv in conversations[:5]:  # 只打印前 5 段
            storage.save_conversation(conv)
            print(f"  - {conv.title[:40]} ({conv.message_count} msgs)")

    def test_extract_from_path(self, tmp_path):
        db_path = os.environ.get("KH_WECHAT_DB", "")
        if not db_path or not Path(db_path).exists():
            pytest.skip("需要设置 KH_WECHAT_DB 指向数据库文件或目录")

        from knowledge_harvester.adapters.wechat import WeChatAdapter

        key = os.environ.get("KH_WECHAT_KEY", "")
        adapter = WeChatAdapter(db_key=key)

        conversations = list(adapter.extract(db_path))
        print(f"  提取了 {len(conversations)} 段微信对话")


# --- 跨平台搜索 E2E ---

class TestSearchE2E:
    """搜索端到端测试 (需要已有导入数据)"""

    def test_search_existing_data(self):
        from knowledge_harvester.search import SearchEngine

        config = Config()
        if not config.output_dir.exists():
            pytest.skip("知识库目录不存在, 请先导入数据")

        engine = SearchEngine(config)
        stats = engine.stats()

        if stats["total_conversations"] == 0:
            pytest.skip("知识库为空, 请先导入数据")

        print(f"  知识库统计: {stats['total_conversations']} 段对话, {stats['total_messages']} 条消息")
        print(f"  平台: {', '.join(stats['platforms'].keys())}")

        # 尝试搜索
        results = engine.search("Python", max_results=5)
        print(f"  搜索 'Python': {len(results)} 条结果")
