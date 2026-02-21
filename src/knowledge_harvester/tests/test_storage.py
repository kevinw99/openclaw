"""存储层测试"""

import json
from pathlib import Path

from knowledge_harvester.config import Config
from knowledge_harvester.models import Conversation, Message
from knowledge_harvester.storage import Storage


def _make_config(tmp_path: Path) -> Config:
    config = Config()
    config.output_root = str(tmp_path / "output")
    # Override property by setting _project_root isn't needed since output_root is absolute now
    # We need to make output_dir work with an absolute path
    return config


def _make_storage(tmp_path: Path) -> Storage:
    """创建使用临时目录的 Storage"""
    config = Config()
    # Monkey-patch output_dir to use tmp_path
    output_dir = tmp_path / "conversations"
    config.__class__ = type("TestConfig", (Config,), {
        "output_dir": property(lambda self: output_dir),
        "platform_dir": lambda self, p: output_dir / p,
        "conversation_path": lambda self, p, cid: output_dir / p / f"{cid}.jsonl",
        "index_path": lambda self, p: output_dir / p / "index.json",
        "state_path": lambda self, p: output_dir / p / "state.json",
    })
    return Storage(config)


def _sample_conversation() -> Conversation:
    return Conversation(
        id="test-conv-1",
        platform="chatgpt",
        title="测试对话",
        participants=["user", "chatgpt"],
        messages=[
            Message(role="user", content="你好", timestamp="2024-01-01T00:00:00+00:00"),
            Message(role="assistant", content="你好！有什么可以帮你的？", timestamp="2024-01-01T00:00:01+00:00"),
        ],
        metadata={"model": "gpt-4"},
    )


def test_save_and_load(tmp_path):
    storage = _make_storage(tmp_path)
    conv = _sample_conversation()

    path = storage.save_conversation(conv)
    assert path.exists()

    # 验证 JSONL 内容
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    msg0 = json.loads(lines[0])
    assert msg0["role"] == "user"
    assert msg0["content"] == "你好"

    # 验证索引
    index_path = path.parent / "index.json"
    assert index_path.exists()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(index) == 1
    assert index[0]["id"] == "test-conv-1"
    assert index[0]["title"] == "测试对话"


def test_load_conversation(tmp_path):
    storage = _make_storage(tmp_path)
    conv = _sample_conversation()
    storage.save_conversation(conv)

    loaded = storage.load_conversation("chatgpt", "test-conv-1")
    assert loaded.id == "test-conv-1"
    assert loaded.title == "测试对话"
    assert len(loaded.messages) == 2
    assert loaded.messages[0].content == "你好"
    assert loaded.messages[1].role == "assistant"


def test_index_update_replaces_existing(tmp_path):
    storage = _make_storage(tmp_path)

    conv1 = _sample_conversation()
    storage.save_conversation(conv1)

    # 保存同一对话 (更新)
    conv1.messages.append(Message(role="user", content="再见"))
    storage.save_conversation(conv1)

    index = storage.list_conversations("chatgpt")
    assert len(index) == 1
    assert index[0]["message_count"] == 3


def test_multiple_conversations(tmp_path):
    storage = _make_storage(tmp_path)

    conv1 = _sample_conversation()
    conv2 = Conversation(
        id="test-conv-2",
        platform="chatgpt",
        title="第二段对话",
        messages=[Message(role="user", content="hello")],
    )

    storage.save_conversation(conv1)
    storage.save_conversation(conv2)

    index = storage.list_conversations("chatgpt")
    assert len(index) == 2


def test_list_platforms(tmp_path):
    storage = _make_storage(tmp_path)

    conv_chatgpt = _sample_conversation()
    conv_grok = Conversation(
        id="grok-1",
        platform="grok",
        title="Grok 对话",
        messages=[Message(role="user", content="hi")],
    )

    storage.save_conversation(conv_chatgpt)
    storage.save_conversation(conv_grok)

    platforms = storage.list_platforms()
    assert "chatgpt" in platforms
    assert "grok" in platforms


def test_list_platforms_empty(tmp_path):
    storage = _make_storage(tmp_path)
    assert storage.list_platforms() == []


# --- 增量提取状态测试 ---


def test_state_empty_by_default(tmp_path):
    storage = _make_storage(tmp_path)
    state = storage.load_state("chatgpt")
    assert state == {"last_run": "", "conversations": {}}
    assert storage.get_known_ids("chatgpt") == set()


def test_state_save_and_load(tmp_path):
    storage = _make_storage(tmp_path)
    state = {"last_run": "", "conversations": {}}

    conv = _sample_conversation()
    storage.update_state_for_conversation(state, conv)
    storage.save_state("chatgpt", state)

    loaded = storage.load_state("chatgpt")
    assert "test-conv-1" in loaded["conversations"]
    assert loaded["conversations"]["test-conv-1"]["message_count"] == 2
    assert loaded["last_run"] != ""  # save_state 自动设置


def test_is_conversation_changed_new(tmp_path):
    storage = _make_storage(tmp_path)
    conv = _sample_conversation()
    # 没有状态 → 一定是新的
    assert storage.is_conversation_changed("chatgpt", conv) is True


def test_is_conversation_changed_unchanged(tmp_path):
    storage = _make_storage(tmp_path)
    conv = _sample_conversation()

    # 保存状态
    state = {"last_run": "", "conversations": {}}
    storage.update_state_for_conversation(state, conv)
    storage.save_state("chatgpt", state)

    # 同样的对话 → 没有变化
    assert storage.is_conversation_changed("chatgpt", conv) is False


def test_is_conversation_changed_new_messages(tmp_path):
    storage = _make_storage(tmp_path)
    conv = _sample_conversation()

    # 保存状态
    state = {"last_run": "", "conversations": {}}
    storage.update_state_for_conversation(state, conv)
    storage.save_state("chatgpt", state)

    # 添加新消息 → 有变化
    conv.messages.append(Message(role="user", content="新消息", timestamp="2024-01-02T00:00:00+00:00"))
    assert storage.is_conversation_changed("chatgpt", conv) is True


def test_get_known_ids(tmp_path):
    storage = _make_storage(tmp_path)

    state = {"last_run": "", "conversations": {}}
    conv1 = _sample_conversation()
    conv2 = Conversation(id="conv-2", platform="chatgpt", title="第二段",
                         messages=[Message(role="user", content="hi")])

    storage.update_state_for_conversation(state, conv1)
    storage.update_state_for_conversation(state, conv2)
    storage.save_state("chatgpt", state)

    known = storage.get_known_ids("chatgpt")
    assert known == {"test-conv-1", "conv-2"}
