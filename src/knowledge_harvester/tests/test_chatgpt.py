"""ChatGPT 适配器测试"""

import json
import zipfile
from pathlib import Path

from knowledge_harvester.adapters.chatgpt import ChatGPTAdapter, _timestamp_to_iso

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_timestamp_to_iso():
    assert _timestamp_to_iso(1700000000.0) == "2023-11-14T22:13:20+00:00"
    assert _timestamp_to_iso(None) == ""
    assert _timestamp_to_iso("invalid") == ""


def test_extract_from_json():
    adapter = ChatGPTAdapter()
    conversations = list(adapter.extract(str(FIXTURES_DIR / "chatgpt_export.json")))

    assert len(conversations) == 3

    # 第一段对话: Python 装饰器
    conv1 = conversations[0]
    assert conv1.id == "conv-001-decorators"
    assert conv1.title == "Python 装饰器教程"
    assert conv1.platform == "chatgpt"
    assert conv1.metadata["model"] == "gpt-4"

    # 消息 (system 空消息应被跳过)
    assert len(conv1.messages) == 4
    assert conv1.messages[0].role == "user"
    assert "装饰器" in conv1.messages[0].content
    assert conv1.messages[1].role == "assistant"
    assert "def my_decorator" in conv1.messages[1].content
    assert conv1.messages[2].role == "user"
    assert conv1.messages[3].role == "assistant"

    # 时间戳
    assert conv1.messages[0].timestamp.startswith("2023-11-14")


def test_extract_second_conversation():
    adapter = ChatGPTAdapter()
    conversations = list(adapter.extract(str(FIXTURES_DIR / "chatgpt_export.json")))

    conv2 = conversations[1]
    assert conv2.id == "conv-002-react-hooks"
    assert conv2.title == "React Hooks 入门"
    assert len(conv2.messages) == 2
    assert "useState" in conv2.messages[0].content


def test_extract_with_image():
    adapter = ChatGPTAdapter()
    conversations = list(adapter.extract(str(FIXTURES_DIR / "chatgpt_export.json")))

    conv3 = conversations[2]
    assert conv3.id == "conv-003-image"
    assert len(conv3.messages) == 2

    # 助手消息应包含媒体引用
    assistant_msg = conv3.messages[1]
    assert "猫咪" in assistant_msg.content
    assert len(assistant_msg.media) == 1
    assert assistant_msg.media[0].type == "image"
    assert "file-abc123" in assistant_msg.media[0].original_url


def test_extract_from_zip(tmp_path):
    adapter = ChatGPTAdapter()

    # 创建包含 conversations.json 的 ZIP
    fixture_json = FIXTURES_DIR / "chatgpt_export.json"
    zip_path = tmp_path / "export.zip"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(fixture_json, "conversations.json")

    conversations = list(adapter.extract(str(zip_path)))
    assert len(conversations) == 3
    assert conversations[0].title == "Python 装饰器教程"


def test_extract_empty_conversations():
    adapter = ChatGPTAdapter()

    # 空映射的对话应被跳过
    data = [{"id": "empty", "title": "Empty", "mapping": {}}]
    json_path = Path("/tmp/test_empty_conversations.json")
    json_path.write_text(json.dumps(data), encoding="utf-8")

    try:
        conversations = list(adapter.extract(str(json_path)))
        assert len(conversations) == 0
    finally:
        json_path.unlink(missing_ok=True)


def test_participants():
    adapter = ChatGPTAdapter()
    conversations = list(adapter.extract(str(FIXTURES_DIR / "chatgpt_export.json")))
    assert conversations[0].participants == ["user", "chatgpt"]


def test_metadata():
    adapter = ChatGPTAdapter()
    conversations = list(adapter.extract(str(FIXTURES_DIR / "chatgpt_export.json")))

    meta = conversations[0].metadata
    assert "create_time" in meta
    assert "update_time" in meta
    assert meta["model"] == "gpt-4"
