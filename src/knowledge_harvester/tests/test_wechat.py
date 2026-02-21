"""微信适配器测试

测试使用未加密的 SQLite 数据库 (模拟已解密或旧版本场景)。
"""

import sqlite3
from pathlib import Path

from knowledge_harvester.adapters.wechat import WeChatAdapter, _sanitize_id


def _create_test_db(tmp_path: Path, table_format: str = "new") -> Path:
    """创建模拟微信消息数据库"""
    db_path = tmp_path / "test_msg.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    if table_format == "new":
        # WeChat macOS 4.x MSG 表格式
        cursor.execute("""
            CREATE TABLE MSG (
                localId INTEGER PRIMARY KEY,
                TalkerId INT,
                MsgSvrID INT,
                Type INT,
                SubType INT,
                IsSender INT,
                CreateTime INT,
                Sequence INT,
                StatusEx INT,
                FlagEx INT,
                Status INT,
                MsgServerSeq INT,
                MsgSequence INT,
                StrTalker TEXT,
                StrContent TEXT,
                DisplayContent TEXT
            )
        """)
        # 插入测试消息
        messages = [
            (1, 1, 1001, 1, 0, 1, 1700000000, 1, 0, 0, 0, 1, 1, "friend_001", "你好！", ""),
            (2, 1, 1002, 1, 0, 0, 1700000010, 2, 0, 0, 0, 2, 2, "friend_001", "你好，有什么事吗？", ""),
            (3, 1, 1003, 1, 0, 1, 1700000020, 3, 0, 0, 0, 3, 3, "friend_001", "想问问 Python 的问题", ""),
            (4, 2, 2001, 1, 0, 0, 1700000100, 1, 0, 0, 0, 1, 1, "group@chatroom", "大家好", ""),
            (5, 2, 2002, 1, 0, 1, 1700000200, 2, 0, 0, 0, 2, 2, "group@chatroom", "你好啊", ""),
            (6, 2, 2003, 3, 0, 0, 1700000300, 3, 0, 0, 0, 3, 3, "group@chatroom", "[图片]", ""),
        ]
        cursor.executemany(
            "INSERT INTO MSG VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            messages,
        )

    elif table_format == "old":
        # 旧版 message 表格式
        cursor.execute("""
            CREATE TABLE message (
                msgId INTEGER PRIMARY KEY,
                type INT,
                isSend INT,
                createTime INT,
                talker TEXT,
                content TEXT
            )
        """)
        messages = [
            (1, 1, 1, 1700000000, "old_friend", "旧版消息1"),
            (2, 1, 0, 1700000010, "old_friend", "旧版消息2"),
        ]
        cursor.executemany(
            "INSERT INTO message VALUES (?,?,?,?,?,?)",
            messages,
        )

    conn.commit()
    conn.close()
    return db_path


def test_extract_unencrypted_new_format(tmp_path):
    db_path = _create_test_db(tmp_path, "new")
    adapter = WeChatAdapter()

    conversations = list(adapter.extract(str(db_path)))

    assert len(conversations) == 2

    # 按 talker 排序
    conversations.sort(key=lambda c: c.metadata["talker"])

    # friend_001 的对话
    friend_conv = conversations[0]
    assert friend_conv.platform == "wechat"
    assert friend_conv.metadata["talker"] == "friend_001"
    assert friend_conv.metadata["is_group"] is False
    assert len(friend_conv.messages) == 3
    assert friend_conv.messages[0].role == "user"  # IsSender=1
    assert friend_conv.messages[0].content == "你好！"
    assert friend_conv.messages[1].role == "assistant"  # IsSender=0
    assert friend_conv.messages[1].content == "你好，有什么事吗？"

    # 群聊
    group_conv = conversations[1]
    assert group_conv.metadata["is_group"] is True
    assert len(group_conv.messages) == 3
    assert group_conv.messages[2].content_type == "image"  # Type=3


def test_extract_unencrypted_old_format(tmp_path):
    db_path = _create_test_db(tmp_path, "old")
    adapter = WeChatAdapter()

    conversations = list(adapter.extract(str(db_path)))

    assert len(conversations) == 1
    conv = conversations[0]
    assert conv.metadata["talker"] == "old_friend"
    assert len(conv.messages) == 2
    assert conv.messages[0].role == "user"
    assert conv.messages[0].content == "旧版消息1"


def test_extract_timestamps(tmp_path):
    db_path = _create_test_db(tmp_path, "new")
    adapter = WeChatAdapter()

    conversations = list(adapter.extract(str(db_path)))
    conversations.sort(key=lambda c: c.metadata["talker"])

    msg = conversations[0].messages[0]
    assert msg.timestamp.startswith("2023-11-14")


def test_extract_nonexistent_path():
    import pytest
    adapter = WeChatAdapter()
    # Non-existent .db file doesn't pass is_file() check → ValueError
    with pytest.raises(ValueError):
        list(adapter.extract("/nonexistent/path.db"))
    # Non-.db file also raises ValueError
    with pytest.raises(ValueError):
        list(adapter.extract("/nonexistent/not_a_db.txt"))


def test_extract_directory(tmp_path):
    db_path = _create_test_db(tmp_path, "new")
    adapter = WeChatAdapter()

    # 传入目录应该找到所有 .db 文件
    conversations = list(adapter.extract(str(tmp_path)))
    assert len(conversations) == 2


def test_sanitize_id():
    assert _sanitize_id("friend_001") == "friend_001"
    assert _sanitize_id("group@chatroom") == "group_chatroom"
    assert _sanitize_id("用户123") == "用户123"  # Unicode 字母保留


def test_encrypted_db_without_key(tmp_path):
    """加密数据库无密钥应该给出提示"""
    # 创建一个看起来像加密数据库的文件 (非有效 SQLite)
    fake_db = tmp_path / "encrypted.db"
    fake_db.write_bytes(b"SQLCipher encrypted data" + b"\x00" * 100)

    adapter = WeChatAdapter()
    conversations = list(adapter.extract(str(fake_db)))
    # 应该打印警告但不崩溃
    assert len(conversations) == 0


def test_message_id_preserved(tmp_path):
    db_path = _create_test_db(tmp_path, "new")
    adapter = WeChatAdapter()

    conversations = list(adapter.extract(str(db_path)))
    conversations.sort(key=lambda c: c.metadata["talker"])

    msg = conversations[0].messages[0]
    assert msg.message_id == "1001"  # MsgSvrID
