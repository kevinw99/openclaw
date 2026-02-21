"""数据模型测试"""

from knowledge_harvester.models import Conversation, MediaRef, Message


def test_message_to_dict_minimal():
    msg = Message(role="user", content="hello")
    d = msg.to_dict()
    assert d == {"role": "user", "content": "hello", "timestamp": ""}
    assert "media" not in d
    assert "message_id" not in d  # 空值不序列化
    assert "content_type" not in d  # 默认 "text" 不序列化


def test_message_to_dict_with_media():
    msg = Message(
        role="assistant",
        content="here's an image",
        timestamp="2024-01-01T00:00:00+00:00",
        content_type="mixed",
        media=[MediaRef(type="image", path="/tmp/img.png", original_url="https://example.com/img.png")],
    )
    d = msg.to_dict()
    assert d["timestamp"] == "2024-01-01T00:00:00+00:00"
    assert d["content_type"] == "mixed"
    assert len(d["media"]) == 1
    assert d["media"][0]["type"] == "image"


def test_message_to_dict_with_message_id():
    msg = Message(role="user", content="test", message_id="msg-123")
    d = msg.to_dict()
    assert d["message_id"] == "msg-123"


def test_message_from_dict():
    d = {
        "role": "user",
        "content": "test",
        "timestamp": "2024-01-01T00:00:00+00:00",
        "message_id": "msg-001",
        "content_type": "text",
        "media": [{"type": "image", "path": "", "original_url": "http://x.com/a.png"}],
    }
    msg = Message.from_dict(d)
    assert msg.role == "user"
    assert msg.content == "test"
    assert msg.message_id == "msg-001"
    assert msg.content_type == "text"
    assert len(msg.media) == 1
    assert msg.media[0].original_url == "http://x.com/a.png"


def test_message_from_dict_no_media():
    msg = Message.from_dict({"role": "assistant", "content": "hi"})
    assert msg.media == []
    assert msg.timestamp == ""
    assert msg.message_id == ""
    assert msg.content_type == "text"


def test_conversation_message_count():
    conv = Conversation(
        id="test-1",
        platform="chatgpt",
        title="Test",
        messages=[
            Message(role="user", content="q1"),
            Message(role="assistant", content="a1"),
            Message(role="user", content="q2"),
        ],
    )
    assert conv.message_count == 3


def test_conversation_to_index_entry():
    conv = Conversation(
        id="conv-123",
        platform="chatgpt",
        title="Python 教程",
        participants=["user", "chatgpt"],
        messages=[
            Message(role="user", content="hello", timestamp="2024-01-01T00:00:00+00:00"),
            Message(role="assistant", content="hi", timestamp="2024-01-01T00:01:00+00:00"),
        ],
        metadata={"model": "gpt-4"},
    )
    entry = conv.to_index_entry()
    assert entry["id"] == "conv-123"
    assert entry["platform"] == "chatgpt"
    assert entry["title"] == "Python 教程"
    assert entry["message_count"] == 2
    assert entry["first_message_time"] == "2024-01-01T00:00:00+00:00"
    assert entry["last_message_time"] == "2024-01-01T00:01:00+00:00"
    assert entry["metadata"]["model"] == "gpt-4"


def test_conversation_to_index_entry_empty():
    conv = Conversation(id="empty", platform="test", title="Empty", messages=[])
    entry = conv.to_index_entry()
    assert entry["first_message_time"] == ""
    assert entry["last_message_time"] == ""


def test_media_ref_fields():
    m = MediaRef(type="image", path="/tmp/a.png", original_url="http://x.com/a.png",
                 filename="a.png", size_bytes=12345)
    assert m.filename == "a.png"
    assert m.size_bytes == 12345
