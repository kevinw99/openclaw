"""微信适配器测试

测试使用未加密的 SQLite 数据库 (模拟已解密或旧版本场景)。
"""

import sqlite3
from pathlib import Path

from knowledge_harvester.adapters.wechat import (
    WeChatAdapter, _sanitize_id, _parse_type49_xml, _format_size,
)


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


# =========================================================================
# _parse_type49_xml 测试
# =========================================================================

def test_parse_type49_file():
    """解析文件类型 (sub_type=6)"""
    xml = """<msg>
        <appmsg appid="" sdkver="">
            <title>英联股份AI计划.pdf</title>
            <des>公司AI战略规划</des>
            <type>6</type>
            <url>https://example.com/file</url>
            <appattach>
                <totallen>2400000</totallen>
                <fileext>pdf</fileext>
                <attachfilename>英联股份AI计划.pdf</attachfilename>
            </appattach>
        </appmsg>
    </msg>"""
    label, media = _parse_type49_xml(xml)
    assert "文件:" in label
    assert "英联股份AI计划.pdf" in label
    assert "2.3MB" in label
    assert len(media) == 1
    assert media[0].type == "file"
    assert media[0].filename == "英联股份AI计划.pdf"
    assert media[0].size_bytes == 2400000
    assert media[0].description == "公司AI战略规划"


def test_parse_type49_link():
    """解析链接/文章类型 (sub_type=5)"""
    xml = """<msg>
        <appmsg>
            <title>深度学习入门指南</title>
            <des>从零开始学习深度学习的完整教程</des>
            <type>5</type>
            <url>https://mp.weixin.qq.com/s/abc123</url>
        </appmsg>
    </msg>"""
    label, media = _parse_type49_xml(xml)
    assert label == "[链接: 深度学习入门指南]"
    assert len(media) == 1
    assert media[0].type == "link"
    assert media[0].original_url == "https://mp.weixin.qq.com/s/abc123"
    assert media[0].description == "从零开始学习深度学习的完整教程"


def test_parse_type49_mini_program():
    """解析小程序 (sub_type=33)"""
    xml = """<msg>
        <appmsg>
            <title>美团外卖</title>
            <type>33</type>
            <url>https://example.com/mp</url>
        </appmsg>
    </msg>"""
    label, media = _parse_type49_xml(xml)
    assert label == "[小程序: 美团外卖]"
    assert len(media) == 1
    assert media[0].type == "mini_program"


def test_parse_type49_reference():
    """解析引用消息 (sub_type=57)"""
    xml = """<msg>
        <appmsg>
            <title>我也这么觉得</title>
            <type>57</type>
            <refermsg>
                <content>昨天那个方案不错</content>
            </refermsg>
        </appmsg>
    </msg>"""
    label, media = _parse_type49_xml(xml)
    assert "引用:" in label
    assert "昨天那个方案不错" in label
    assert "我也这么觉得" in label
    assert media == []


def test_parse_type49_chat_history():
    """解析聊天记录合并转发 (sub_type=19)"""
    xml = """<msg>
        <appmsg>
            <title>群聊的聊天记录</title>
            <type>19</type>
        </appmsg>
    </msg>"""
    label, media = _parse_type49_xml(xml)
    assert label == "[聊天记录: 群聊的聊天记录]"


def test_parse_type49_transfer():
    """解析转账/红包 (sub_type=2000/2001)"""
    xml_transfer = '<msg><appmsg><title>转账</title><type>2000</type></appmsg></msg>'
    xml_hongbao = '<msg><appmsg><title>红包</title><type>2001</type></appmsg></msg>'

    label1, media1 = _parse_type49_xml(xml_transfer)
    assert label1 == "[转账]"
    assert media1 == []

    label2, media2 = _parse_type49_xml(xml_hongbao)
    assert label2 == "[红包]"


def test_parse_type49_malformed_xml():
    """畸形 XML 应该 fallback 不崩溃"""
    label, media = _parse_type49_xml("<msg><broken>")
    # regex fallback 或 默认 placeholder
    assert "[链接/文件]" in label or "[链接:" in label

    # 完全无 XML
    label2, media2 = _parse_type49_xml("not xml at all")
    assert label2 == "[链接/文件]"


def test_parse_type49_empty_input():
    """空输入处理"""
    label, media = _parse_type49_xml("")
    assert label == "[链接/文件]"
    assert media == []

    label2, media2 = _parse_type49_xml("   ")
    assert label2 == "[链接/文件]"


def test_parse_type49_with_prefix():
    """群消息中 XML 前有 wxid 前缀"""
    xml = """wxid_abc123:\n<msg>
        <appmsg>
            <title>分享一篇文章</title>
            <type>5</type>
            <url>https://example.com</url>
        </appmsg>
    </msg>"""
    label, media = _parse_type49_xml(xml)
    assert "分享一篇文章" in label


def test_parse_type49_regex_fallback():
    """XML 解析失败但有 title 标签时 regex 兜底"""
    # Intentionally broken XML but with extractable title
    raw = "<msg><appmsg><title>测试标题</title><type>5</type><broken"
    label, media = _parse_type49_xml(raw)
    assert "测试标题" in label


def test_format_size():
    """文件大小格式化"""
    assert _format_size(0) == ""
    assert _format_size(500) == "500B"
    assert _format_size(1024) == "1.0KB"
    assert _format_size(1536) == "1.5KB"
    assert _format_size(2400000) == "2.3MB"
    assert _format_size(1073741824) == "1.0GB"


def test_type49_msg_in_db(tmp_path):
    """集成测试: type=49 消息在 MSG 表中的完整提取流程"""
    db_path = tmp_path / "test_msg49.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE MSG (
            localId INTEGER PRIMARY KEY,
            TalkerId INT, MsgSvrID INT, Type INT, SubType INT,
            IsSender INT, CreateTime INT, Sequence INT, StatusEx INT,
            FlagEx INT, Status INT, MsgServerSeq INT, MsgSequence INT,
            StrTalker TEXT, StrContent TEXT, DisplayContent TEXT
        )
    """)
    file_xml = """<msg><appmsg>
        <title>报告.pdf</title><des>季度报告</des><type>6</type>
        <appattach><totallen>1048576</totallen><fileext>pdf</fileext>
        <attachfilename>报告.pdf</attachfilename></appattach>
    </appmsg></msg>"""
    cursor.execute(
        "INSERT INTO MSG VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (1, 1, 3001, 49, 0, 1, 1700000000, 1, 0, 0, 0, 1, 1,
         "friend_002", file_xml, ""),
    )
    conn.commit()
    conn.close()

    adapter = WeChatAdapter()
    conversations = list(adapter.extract(str(db_path)))
    assert len(conversations) == 1
    msg = conversations[0].messages[0]
    assert "文件:" in msg.content
    assert "报告.pdf" in msg.content
    assert msg.content_type == "link"
    assert len(msg.media) == 1
    assert msg.media[0].type == "file"
    assert msg.media[0].size_bytes == 1048576


def test_media_types_create_media_ref(tmp_path):
    """type 3/34/43 消息应创建对应的 MediaRef"""
    db_path = tmp_path / "test_media.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE MSG (
            localId INTEGER PRIMARY KEY,
            TalkerId INT, MsgSvrID INT, Type INT, SubType INT,
            IsSender INT, CreateTime INT, Sequence INT, StatusEx INT,
            FlagEx INT, Status INT, MsgServerSeq INT, MsgSequence INT,
            StrTalker TEXT, StrContent TEXT, DisplayContent TEXT
        )
    """)
    # image, audio, video
    cursor.executemany(
        "INSERT INTO MSG VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, 1, 4001, 3, 0, 1, 1700000000, 1, 0, 0, 0, 1, 1,
             "media_user", "[img]", ""),
            (2, 1, 4002, 34, 0, 0, 1700000010, 2, 0, 0, 0, 2, 2,
             "media_user", "[voice data]", ""),
            (3, 1, 4003, 43, 0, 1, 1700000020, 3, 0, 0, 0, 3, 3,
             "media_user", "[video data]", ""),
        ],
    )
    conn.commit()
    conn.close()

    adapter = WeChatAdapter()
    conversations = list(adapter.extract(str(db_path)))
    assert len(conversations) == 1
    msgs = conversations[0].messages
    assert len(msgs) == 3
    assert msgs[0].media[0].type == "image"
    assert msgs[1].media[0].type == "voice"
    assert msgs[2].media[0].type == "video"
