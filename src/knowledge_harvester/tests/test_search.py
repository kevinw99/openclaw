"""搜索引擎测试"""

import json
from pathlib import Path

from knowledge_harvester.config import Config
from knowledge_harvester.models import Conversation, Message
from knowledge_harvester.search import SearchEngine
from knowledge_harvester.storage import Storage


def _setup_test_data(tmp_path: Path) -> Config:
    """创建测试数据"""
    config = Config()
    output_dir = tmp_path / "conversations"
    config.__class__ = type("TestConfig", (Config,), {
        "output_dir": property(lambda self: output_dir),
        "platform_dir": lambda self, p: output_dir / p,
        "conversation_path": lambda self, p, cid: output_dir / p / f"{cid}.jsonl",
        "index_path": lambda self, p: output_dir / p / "index.json",
        "state_path": lambda self, p: output_dir / p / "state.json",
    })

    storage = Storage(config)

    # 创建测试对话
    conv1 = Conversation(
        id="conv-1",
        platform="chatgpt",
        title="Python 装饰器教程",
        messages=[
            Message(role="user", content="什么是 Python 装饰器？",
                    timestamp="2024-01-01T00:00:00+00:00"),
            Message(role="assistant", content="Python 装饰器是一种特殊的函数修饰符。",
                    timestamp="2024-01-01T00:00:10+00:00"),
        ],
    )
    conv2 = Conversation(
        id="conv-2",
        platform="chatgpt",
        title="React Hooks 入门",
        messages=[
            Message(role="user", content="React useState 怎么用？",
                    timestamp="2024-02-01T00:00:00+00:00"),
            Message(role="assistant", content="useState 是 React 最常用的 Hook。",
                    timestamp="2024-02-01T00:00:10+00:00"),
        ],
    )
    conv3 = Conversation(
        id="conv-3",
        platform="grok",
        title="Grok 对话",
        messages=[
            Message(role="user", content="Python 最佳实践有哪些？",
                    timestamp="2024-03-01T00:00:00+00:00"),
            Message(role="assistant", content="Python 最佳实践包括使用类型提示、装饰器等。",
                    timestamp="2024-03-01T00:00:10+00:00"),
        ],
    )

    storage.save_conversation(conv1)
    storage.save_conversation(conv2)
    storage.save_conversation(conv3)

    return config


def test_search_basic(tmp_path):
    config = _setup_test_data(tmp_path)
    engine = SearchEngine(config)

    results = engine.search("装饰器")
    assert len(results) >= 2  # conv1 和 conv3 都提到装饰器


def test_search_platform_filter(tmp_path):
    config = _setup_test_data(tmp_path)
    engine = SearchEngine(config)

    results = engine.search("Python", platform="chatgpt")
    for r in results:
        assert r.platform == "chatgpt"


def test_search_no_results(tmp_path):
    config = _setup_test_data(tmp_path)
    engine = SearchEngine(config)

    results = engine.search("不存在的关键词xyz")
    assert len(results) == 0


def test_search_multi_keyword(tmp_path):
    config = _setup_test_data(tmp_path)
    engine = SearchEngine(config)

    results = engine.search("Python 装饰器")
    # 只有同时包含两个关键词的结果
    for r in results:
        content_lower = r.message.content.lower()
        assert "python" in content_lower
        assert "装饰器" in content_lower


def test_search_by_role(tmp_path):
    config = _setup_test_data(tmp_path)
    engine = SearchEngine(config)

    results = engine.search_by_role("Python", "user")
    for r in results:
        assert r.message.role == "user"


def test_stats(tmp_path):
    config = _setup_test_data(tmp_path)
    engine = SearchEngine(config)

    s = engine.stats()
    assert s["total_conversations"] == 3
    assert s["total_messages"] == 6
    assert "chatgpt" in s["platforms"]
    assert "grok" in s["platforms"]
    assert s["platforms"]["chatgpt"]["conversations"] == 2
    assert s["platforms"]["grok"]["conversations"] == 1


def test_list_all(tmp_path):
    config = _setup_test_data(tmp_path)
    engine = SearchEngine(config)

    entries = engine.list_all()
    assert len(entries) == 3

    entries_chatgpt = engine.list_all(platform="chatgpt")
    assert len(entries_chatgpt) == 2


def test_search_limit(tmp_path):
    config = _setup_test_data(tmp_path)
    engine = SearchEngine(config)

    results = engine.search("Python", max_results=1)
    assert len(results) <= 1
