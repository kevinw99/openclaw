"""微信 (WeChat) macOS 对话提取适配器

从微信 macOS 桌面版的本地 SQLite 数据库提取对话历史。

数据库位置 (WeChat 4.x, macOS):
  ~/Library/Containers/com.tencent.xinWeChat/Data/Documents/
  xwechat_files/{wxid}_{hash}/db_storage/message/message_*.db

加密方式:
  WeChat 4.x 使用 WCDB (基于 SQLCipher 4) 加密数据库。
  - PBKDF2-HMAC-SHA512, 256,000 次迭代
  - 每个 DB 文件的前 16 字节作为 salt
  - 所有 DB 共享同一个 master password (32 字节)

密钥提取 (macOS, Apple Silicon):
  需要一次性关闭 SIP:
    1. 关闭 SIP: csrutil disable (Recovery Mode)
    2. 退出微信, 重新签名二进制:
       codesign --force -s - --entitlements debug.plist WeChat
    3. 用 LLDB 启动微信, 拦截 CCKeyDerivationPBKDF:
       lldb -b -s extract_key.lldb
    4. 登录微信, 等待 256000 rounds 的 PBKDF2 调用
    5. 密码 (password_hex) 即为 master password
    6. 恢复 SIP: csrutil enable (Recovery Mode)

  或使用 scripts/extract_wechat_key.py 自动化上述过程。

使用方式:
  python3 -m knowledge_harvester extract-wechat --key <64位十六进制master密码>
  python3 -m knowledge_harvester extract-wechat --key-file ~/.wechat_db_key
"""

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

try:
    import zstandard as _zstd
    _zstd_decompressor = _zstd.ZstdDecompressor()
except ImportError:
    _zstd_decompressor = None

from .base import BaseAdapter
from ..models import Conversation, MediaRef, Message

# WeChat macOS 数据目录
WECHAT_CONTAINER = Path.home() / "Library/Containers/com.tencent.xinWeChat"

# WeChat 4.x (新版) 路径
WECHAT_DATA_V4 = WECHAT_CONTAINER / "Data/Documents/xwechat_files"

# WeChat 旧版路径
WECHAT_DATA_LEGACY = WECHAT_CONTAINER / "Data/Library/Application Support/com.tencent.xinWeChat"


def _format_size(size_bytes: int) -> str:
    """格式化文件大小: 1234567 → '1.2MB'"""
    if size_bytes <= 0:
        return ""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def _parse_type49_xml(raw_content: str) -> Tuple[str, List[MediaRef]]:
    """解析 type=49 (appmsg) 消息的 XML 内容.

    Returns:
        (inline_label, media_refs) — Tier 0 展示文本 + Tier 1 媒体元数据
    """
    if not raw_content or not raw_content.strip():
        return "[链接/文件]", []

    # 清理 XML: 去掉可能的前缀文本 (群消息会有 "wxid_xxx:\n" 前缀)
    xml_text = raw_content
    msg_idx = xml_text.find("<msg")
    if msg_idx > 0:
        xml_text = xml_text[msg_idx:]
    elif not xml_text.strip().startswith("<"):
        return "[链接/文件]", []

    # 解析 XML
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # Regex fallback: 尝试提取 title
        title_match = re.search(r"<title>([^<]+)</title>", raw_content)
        if title_match:
            title = title_match.group(1).strip()
            return f"[链接: {title}]", [MediaRef(type="link", filename=title)]
        return "[链接/文件]", []

    appmsg = root.find("appmsg") or root
    title_el = appmsg.find("title")
    des_el = appmsg.find("des")
    type_el = appmsg.find("type")
    url_el = appmsg.find("url")

    title = (title_el.text or "").strip() if title_el is not None else ""
    description = (des_el.text or "").strip() if des_el is not None else ""
    url = (url_el.text or "").strip() if url_el is not None else ""

    try:
        sub_type = int(type_el.text) if type_el is not None and type_el.text else 0
    except (ValueError, TypeError):
        sub_type = 0

    # 文件附件信息
    appattach = appmsg.find("appattach")
    file_size = 0
    file_ext = ""
    attach_filename = ""
    if appattach is not None:
        totallen_el = appattach.find("totallen")
        fileext_el = appattach.find("fileext")
        filename_el = appattach.find("attachfilename")
        if totallen_el is not None and totallen_el.text:
            try:
                file_size = int(totallen_el.text)
            except ValueError:
                pass
        if fileext_el is not None:
            file_ext = (fileext_el.text or "").strip()
        if filename_el is not None:
            attach_filename = (filename_el.text or "").strip()

    filename = attach_filename or title

    # 根据 appmsg sub-type 生成标签和 MediaRef
    if sub_type == 6:
        # 文件
        size_str = _format_size(file_size)
        size_part = f" ({size_str})" if size_str else ""
        label = f"[文件: {filename}{size_part}]"
        media = [MediaRef(
            type="file", filename=filename, original_url=url,
            size_bytes=file_size, description=description,
        )]
    elif sub_type == 5:
        # 链接/文章
        label = f"[链接: {title}]" if title else "[链接]"
        media = [MediaRef(
            type="link", filename=title, original_url=url,
            description=description,
        )]
    elif sub_type in (33, 36):
        # 小程序
        label = f"[小程序: {title}]" if title else "[小程序]"
        media = [MediaRef(type="mini_program", filename=title, original_url=url)]
    elif sub_type == 57:
        # 引用消息
        ref_content = ""
        refermsg = appmsg.find("refermsg")
        if refermsg is not None:
            ref_content_el = refermsg.find("content")
            if ref_content_el is not None:
                ref_content = (ref_content_el.text or "").strip()[:80]
        label = f"[引用: {ref_content}]" if ref_content else "[引用]"
        # 引用消息本身可能包含 title 作为回复内容
        if title:
            label = f"{title}\n{label}"
        media = []
    elif sub_type == 19:
        # 合并转发的聊天记录
        label = f"[聊天记录: {title}]" if title else "[聊天记录]"
        media = []
    elif sub_type == 4:
        # 音乐
        label = f"[音乐: {title}]" if title else "[音乐]"
        media = [MediaRef(type="link", filename=title, original_url=url)]
    elif sub_type in (2000, 2001):
        # 转账 / 红包
        label = "[转账]" if sub_type == 2000 else "[红包]"
        media = []
    elif sub_type == 51:
        # 视频号
        label = f"[视频号: {title}]" if title else "[视频号]"
        media = [MediaRef(type="link", filename=title, original_url=url)]
    elif sub_type == 53:
        # 群通话
        label = "[群通话]"
        media = []
    elif sub_type == 87:
        # 群公告
        label = f"[群公告: {title}]" if title else "[群公告]"
        media = []
    else:
        # 未知 sub-type, 尽量保留 title
        if title:
            label = f"[链接: {title}]"
            media = [MediaRef(type="link", filename=title, original_url=url,
                              description=description)]
        else:
            label = "[链接/文件]"
            media = []

    return label, media


def _decompress_content(hex_content: str) -> Optional[str]:
    """解压 WCDB 压缩内容 (Zstandard).

    WeChat WCDB 使用 WCDB_CT_message_content 标记压缩:
    - CT=4: Zstandard 压缩 (magic bytes: 28 B5 2F FD)

    Args:
        hex_content: 消息内容的十六进制编码

    Returns:
        解压后的文本, 或 None 如果解压失败
    """
    if not hex_content or not _zstd_decompressor:
        return None
    try:
        raw = bytes.fromhex(hex_content)
    except ValueError:
        return None
    # Zstandard magic: 28 B5 2F FD
    if len(raw) >= 4 and raw[:4] == b'\x28\xb5\x2f\xfd':
        try:
            decoded = _zstd_decompressor.decompress(raw)
            return decoded.decode('utf-8', errors='replace')
        except Exception:
            pass
    return None


def _derive_raw_key(master_password_hex: str, db_path: Path) -> str:
    """从 master password 和 DB 文件的 salt 派生 SQLCipher raw key.

    WeChat WCDB 加密流程:
      1. 所有 DB 共享同一个 32 字节 master password
      2. 每个 DB 文件的前 16 字节作为 PBKDF2 salt
      3. PBKDF2-HMAC-SHA512(password, salt, 256000, dklen=32) → raw key
      4. raw key 用于 SQLCipher 默认配置 (page_size=4096)

    Returns:
        64 字符十六进制 raw key
    """
    password = bytes.fromhex(master_password_hex)
    with open(db_path, "rb") as f:
        salt = f.read(16)
    if len(salt) < 16:
        raise ValueError(f"DB 文件过小, 无法读取 salt: {db_path}")
    derived = hashlib.pbkdf2_hmac("sha512", password, salt, 256000, dklen=32)
    return derived.hex()


class WeChatAdapter(BaseAdapter):
    """微信 macOS 对话提取"""

    def __init__(self, db_key: str = "", data_dir: str = ""):
        """
        Args:
            db_key: 64 位十六进制密钥 (master password, PBKDF2 输入)
            data_dir: 微信数据目录 (自动检测如果不指定)
        """
        self._db_key = db_key
        self._data_dir = Path(data_dir) if data_dir else None
        self._sqlcipher_bin = shutil.which("sqlcipher") or ""
        self._contact_map: dict = {}  # md5_hash → {username, nick_name, remark}
        self._wechat_user_root: Optional[Path] = None  # WeChat user data root

    @property
    def platform(self) -> str:
        return "wechat"

    def check_compatibility(self) -> list:
        """检查微信数据目录和数据库可用性"""
        warnings = []

        if self._db_key and not self._sqlcipher_bin:
            warnings.append(
                "需要安装 sqlcipher CLI 来解密微信数据库:\n"
                "  brew install sqlcipher"
            )

        if self._data_dir:
            if not self._data_dir.exists():
                warnings.append(f"指定的数据目录不存在: {self._data_dir}")
            return warnings

        # 检查默认路径
        v4_exists = WECHAT_DATA_V4.exists()
        legacy_exists = WECHAT_DATA_LEGACY.exists()

        if not v4_exists and not legacy_exists:
            warnings.append(
                f"未找到微信数据目录。\n"
                f"  预期路径 (4.x): {WECHAT_DATA_V4}\n"
                f"  预期路径 (旧版): {WECHAT_DATA_LEGACY}\n"
                f"  请确保微信已安装并登录过。"
            )
            return warnings

        db_files = self._find_message_dbs()
        if not db_files:
            warnings.append("找到微信数据目录但未发现消息数据库文件")
        else:
            # 检查是否加密
            if not self._db_key:
                try:
                    conn = sqlite3.connect(str(db_files[0]))
                    conn.execute("SELECT name FROM sqlite_master LIMIT 1")
                    conn.close()
                except Exception:
                    warnings.append(
                        f"数据库已加密 ({len(db_files)} 个文件), 需要提供 --key 参数\n"
                        f"  密钥提取: python3 scripts/extract_wechat_key.py"
                    )

        return warnings

    def extract(self, source: str = "") -> Iterator[Conversation]:
        """提取微信对话

        Args:
            source: 可选 — 数据库文件/目录路径 (不指定则自动检测)
        """
        if source:
            source_path = Path(source)
            if source_path.is_file() and source_path.suffix == ".db":
                db_files = [source_path]
            elif source_path.is_dir():
                db_files = list(source_path.glob("**/*.db"))
            else:
                raise ValueError(f"无效数据源: {source}")
        else:
            db_files = self._find_message_dbs()

        if not db_files:
            print("  未找到微信数据库文件。")
            print(f"  预期位置 (4.x): {WECHAT_DATA_V4}")
            print(f"  预期位置 (旧版): {WECHAT_DATA_LEGACY}")
            print("  请确保微信已登录且有聊天记录。")
            return

        # 过滤: 只要 message_*.db, 跳过 fts/resource/media/kvdb
        msg_dbs = [
            f for f in db_files
            if f.name.startswith("message_") and f.suffix == ".db"
            and not f.name.endswith("_fts.db")
            and not f.name.endswith("_resource.db")
        ]

        if not msg_dbs:
            msg_dbs = db_files  # fallback: use all .db files

        print(f"  找到 {len(msg_dbs)} 个消息数据库文件")

        # 加载联系人映射 (用于将 Msg_<md5> → 真实名称)
        if self._db_key:
            self._load_contact_map(msg_dbs)

        for db_path in msg_dbs:
            try:
                yield from self._extract_from_db(db_path)
            except Exception as e:
                print(f"  ✗ {db_path.name}: {e}")

    def _find_message_dbs(self) -> List[Path]:
        """自动查找微信消息数据库文件"""
        if self._data_dir:
            return sorted(self._data_dir.glob("**/*.db"))

        db_files = []

        # 1. WeChat 4.x 路径: xwechat_files/{wxid}_{hash}/db_storage/message/
        if WECHAT_DATA_V4.exists():
            for user_dir in WECHAT_DATA_V4.iterdir():
                if not user_dir.is_dir() or user_dir.name in ("all_users", "Backup"):
                    continue
                msg_dir = user_dir / "db_storage" / "message"
                if msg_dir.exists():
                    db_files.extend(msg_dir.glob("*.db"))
                    self._wechat_user_root = user_dir

        # 2. 旧版路径: Application Support/com.tencent.xinWeChat/{version}/{uuid}/Message/
        if not db_files and WECHAT_DATA_LEGACY.exists():
            for version_dir in WECHAT_DATA_LEGACY.iterdir():
                if not version_dir.is_dir():
                    continue
                for uuid_dir in version_dir.iterdir():
                    if not uuid_dir.is_dir():
                        continue
                    msg_dir = uuid_dir / "Message"
                    if msg_dir.exists():
                        db_files.extend(msg_dir.glob("*.db"))

        return sorted(db_files)

    def _load_contact_map(self, msg_dbs: List[Path]):
        """从 contact.db 加载联系人映射: MD5(username) → display name"""
        if not msg_dbs:
            return

        # contact.db 在 db_storage/contact/ 目录 (与 message/ 同级)
        db_storage = msg_dbs[0].parent.parent
        contact_db = db_storage / "contact" / "contact.db"
        if not contact_db.exists():
            return

        raw_key = _derive_raw_key(self._db_key, contact_db)
        rows = self._sqlcipher_query(
            contact_db, raw_key,
            "SELECT username, nick_name, remark FROM contact;"
        )
        if not rows:
            return

        for row in rows:
            try:
                username = str(row[0] or "")
                nick = str(row[1] or "")
                remark = str(row[2] or "")
            except IndexError:
                continue
            if not username:
                continue
            md5 = hashlib.md5(username.encode()).hexdigest()
            self._contact_map[md5] = {
                "username": username,
                "nick_name": nick,
                "remark": remark,
                "display": remark or nick or username,
            }

        print(f"  加载了 {len(self._contact_map)} 个联系人映射")

    def _extract_from_db(self, db_path: Path) -> Iterator[Conversation]:
        """从单个数据库文件提取对话"""
        if self._db_key:
            yield from self._extract_encrypted(db_path)
        else:
            yield from self._extract_unencrypted(db_path)

    def _extract_unencrypted(self, db_path: Path) -> Iterator[Conversation]:
        """尝试以非加密方式打开数据库 (适用于部分旧版本或已解密数据库)"""
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            if "MSG" in tables:
                yield from self._read_unencrypted_msg(conn, db_path.name)
            elif "message" in tables:
                yield from self._read_unencrypted_legacy(conn, db_path.name)
            else:
                print(f"  ⚠ {db_path.name}: 未找到已知消息表 (找到: {', '.join(tables[:10])})")

            conn.close()

        except sqlite3.DatabaseError as e:
            if "file is not a database" in str(e) or "file is encrypted" in str(e):
                print(f"  ⚠ {db_path.name}: 数据库已加密, 需要提供密钥 (--key)")
            else:
                raise

    def _read_unencrypted_msg(self, conn, db_name: str) -> Iterator[Conversation]:
        """读取未加密 MSG 表"""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT StrTalker FROM MSG "
            "WHERE StrTalker IS NOT NULL AND StrTalker != '' ORDER BY StrTalker"
        )
        talkers = [row[0] for row in cursor.fetchall()]

        for talker in talkers:
            cursor.execute(
                "SELECT MsgSvrID, Type, SubType, IsSender, CreateTime, "
                "StrTalker, StrContent, DisplayContent FROM MSG "
                "WHERE StrTalker = ? ORDER BY CreateTime ASC", (talker,)
            )
            messages = []
            for row in cursor.fetchall():
                msg = self._parse_msg_row(list(row))
                if msg:
                    messages.append(msg)
            if messages:
                conv_id = f"wechat-{_sanitize_id(talker)}"
                is_group = "@chatroom" in talker
                yield Conversation(
                    id=conv_id, platform="wechat", title=talker,
                    participants=[talker] if not is_group else [],
                    messages=messages,
                    metadata={"talker": talker, "is_group": is_group, "db_file": db_name},
                )

    def _read_unencrypted_legacy(self, conn, db_name: str) -> Iterator[Conversation]:
        """读取未加密旧版 message 表"""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT talker FROM message "
            "WHERE talker IS NOT NULL AND talker != ''"
        )
        talkers = [row[0] for row in cursor.fetchall()]

        for talker in talkers:
            cursor.execute(
                "SELECT msgId, type, isSend, createTime, talker, content "
                "FROM message WHERE talker = ? ORDER BY createTime ASC", (talker,)
            )
            messages = []
            for row in cursor.fetchall():
                content = str(row[5] or "")
                if not content.strip():
                    continue
                role = "user" if row[2] else "assistant"
                timestamp = ""
                if row[3]:
                    try:
                        dt = datetime.fromtimestamp(row[3], tz=timezone.utc)
                        timestamp = dt.isoformat()
                    except (ValueError, OSError):
                        pass
                messages.append(Message(
                    role=role, content=content, timestamp=timestamp,
                    message_id=str(row[0] or ""),
                ))
            if messages:
                yield Conversation(
                    id=f"wechat-{_sanitize_id(talker)}", platform="wechat",
                    title=talker, participants=[talker], messages=messages,
                    metadata={"talker": talker, "db_file": db_name},
                )

    def _extract_encrypted(self, db_path: Path) -> Iterator[Conversation]:
        """使用 sqlcipher CLI 解密数据库并提取对话"""
        if not self._sqlcipher_bin:
            raise RuntimeError(
                "需要安装 sqlcipher CLI 来解密微信数据库:\n"
                "  brew install sqlcipher"
            )

        # 为每个 DB 派生 raw key
        raw_key = _derive_raw_key(self._db_key, db_path)

        # 查询所有表名
        tables = self._sqlcipher_query(
            db_path, raw_key,
            "SELECT name FROM sqlite_master WHERE type='table';"
        )
        if tables is None:
            print(f"  ✗ {db_path.name}: 解密失败 (密钥无效?)")
            return

        table_names = [row[0] for row in tables]

        # WCDB v4: Msg_<hash> 表
        msg_tables = [t for t in table_names if t.startswith("Msg_")]
        if msg_tables:
            yield from self._read_wcdb_v4_tables(db_path, raw_key, msg_tables)
        elif "MSG" in table_names:
            yield from self._read_msg_table_via_cli(db_path, raw_key)
        else:
            print(f"  ⚠ {db_path.name}: 解密成功但未找到消息表 (找到: {', '.join(table_names[:10])})")

    def _sqlcipher_query(self, db_path: Path, raw_key: str, sql: str) -> Optional[List[list]]:
        """通过 sqlcipher CLI 执行查询, 返回行列表"""
        commands = f"PRAGMA key = \"x'{raw_key}'\";\n.mode json\n{sql}\n"
        try:
            result = subprocess.run(
                [self._sqlcipher_bin, str(db_path)],
                input=commands.encode("utf-8"),
                capture_output=True, timeout=60,
            )
        except subprocess.TimeoutExpired:
            return None

        stderr = result.stderr.decode("utf-8", errors="replace")
        if "file is not a database" in stderr:
            return None

        output = result.stdout.decode("utf-8", errors="replace").strip()
        if not output or output == "ok":
            return []

        # sqlcipher .mode json outputs multi-line JSON arrays.
        # Extract JSON by finding [ ... ] blocks (skip "ok" lines from PRAGMAs).
        # Collect all text after the first "[" until we have valid JSON.
        json_start = output.find("[")
        if json_start >= 0:
            json_text = output[json_start:]
            try:
                parsed = json.loads(json_text)
                if isinstance(parsed, list):
                    return [[v for v in row.values()] for row in parsed]
            except (json.JSONDecodeError, AttributeError):
                pass

        # Fallback: parse pipe-separated output
        rows = []
        for line in output.split("\n"):
            line = line.strip()
            if line and line != "ok" and "|" in line:
                rows.append(line.split("|"))

        return rows if rows else []

    def _read_wcdb_v4_tables(self, db_path: Path, raw_key: str,
                              msg_tables: List[str]) -> Iterator[Conversation]:
        """读取 WCDB v4 格式的 Msg_<hash> 表"""
        # 同时读取 Name2Id 表获取 talker 名映射
        name_map = {}
        name_rows = self._sqlcipher_query(
            db_path, raw_key,
            "SELECT rowid, name FROM Name2Id;"
        )
        if name_rows:
            for row in name_rows:
                try:
                    name_map[int(row[0])] = row[1]
                except (ValueError, IndexError):
                    pass

        for table_name in msg_tables:
            # Include hex(message_content) for compressed message recovery
            rows = self._sqlcipher_query(
                db_path, raw_key,
                f"SELECT local_id, server_id, local_type, real_sender_id, "
                f"create_time, status, message_content, "
                f"WCDB_CT_message_content, "
                f"CASE WHEN WCDB_CT_message_content != 0 "
                f"THEN hex(message_content) ELSE '' END "
                f"FROM {table_name} ORDER BY create_time ASC;"
            )
            if not rows:
                continue

            messages = []
            for row in rows:
                msg = self._parse_v4_msg_row(row)
                if msg:
                    messages.append(msg)

            if not messages:
                continue

            # Resolve media file paths on disk
            table_hash = table_name.replace("Msg_", "")
            self._resolve_media_paths(messages, table_hash)

            # Map Msg_<md5> → contact name via MD5(username)
            contact = self._contact_map.get(table_hash, {})
            username = contact.get("username", "")
            display_name = contact.get("display", table_hash)
            is_group = "@chatroom" in username

            conv_id = f"wechat-{_sanitize_id(username or table_hash)}"
            yield Conversation(
                id=conv_id,
                platform="wechat",
                title=display_name,
                participants=[username] if username and not is_group else [],
                messages=messages,
                metadata={
                    "table": table_name,
                    "username": username,
                    "is_group": is_group,
                    "db_file": db_path.name,
                },
            )

    def _resolve_media_paths(self, messages: List[Message],
                              contact_hash: str) -> None:
        """为消息中的 MediaRef 解析本地文件路径.

        WeChat 本地媒体文件结构:
          msg/attach/<contact_hash>/YYYY-MM/Img/  → 图片 (.dat)
          msg/video/YYYY-MM/                       → 视频 (.mp4)
          msg/file/YYYY-MM/                        → 文件
          cache/YYYY-MM/Message/<contact_hash>/Thumb/{local_id}_{ts}_thumb.jpg
        """
        root = self._wechat_user_root
        if not root:
            return

        for msg in messages:
            if not msg.media:
                continue
            for m in msg.media:
                if m.path:  # Already resolved
                    continue

                # Parse timestamp for YYYY-MM directory
                yyyy_mm = ""
                if msg.timestamp:
                    yyyy_mm = msg.timestamp[:7]  # "2026-01" from ISO

                if m.type == "file" and m.filename and yyyy_mm:
                    # Files: msg/file/YYYY-MM/<filename>
                    candidate = root / "msg" / "file" / yyyy_mm / m.filename
                    if candidate.exists():
                        m.path = str(candidate)

                elif m.type == "video" and yyyy_mm:
                    # Videos: msg/video/YYYY-MM/ — match by nearby timestamps
                    video_dir = root / "msg" / "video" / yyyy_mm
                    if video_dir.exists():
                        # Look for .mp4 files (not _thumb.jpg)
                        mp4s = list(video_dir.glob("*.mp4"))
                        if mp4s:
                            # Best-effort: can't reliably map without msg_id,
                            # but we can confirm videos exist for this month
                            m.path = str(video_dir)

                elif m.type == "image":
                    # Cache thumbnails: identifiable by local_id
                    if msg.message_id and yyyy_mm:
                        thumb = self._find_cache_thumbnail(
                            contact_hash, yyyy_mm, msg.message_id)
                        if thumb:
                            m.path = str(thumb)

    def _find_cache_thumbnail(self, contact_hash: str, yyyy_mm: str,
                               local_id: str) -> Optional[Path]:
        """Find cache thumbnail by local_id pattern.

        Thumbnails are at: cache/YYYY-MM/Message/<hash>/Thumb/{local_id}_{ts}_thumb.jpg
        """
        root = self._wechat_user_root
        if not root:
            return None
        thumb_dir = root / "cache" / yyyy_mm / "Message" / contact_hash / "Thumb"
        if not thumb_dir.exists():
            return None
        pattern = f"{local_id}_*_thumb.jpg"
        matches = list(thumb_dir.glob(pattern))
        return matches[0] if matches else None

    def _parse_v4_msg_row(self, row) -> Optional[Message]:
        """解析 WCDB v4 Msg_<hash> 表的一行

        Schema: local_id, server_id, local_type, real_sender_id,
                create_time, status, message_content, WCDB_CT_message_content,
                hex_content (CASE WHEN compressed)
        """
        try:
            local_id = row[0] or ""
            raw_type = int(row[2] or 0)
            create_time = int(row[4] or 0)
            status = int(row[5] or 0)
            content = str(row[6] or "")
            compression = int(row[7] or 0) if len(row) > 7 else 0
            hex_content = str(row[8] or "") if len(row) > 8 else ""
        except (ValueError, IndexError):
            return None

        # local_type: low 16 bits = message type, high bits = sub-type
        msg_type = raw_type & 0xFFFF

        # Decompress content (Zstandard) if compressed
        if compression != 0 and hex_content:
            decompressed = _decompress_content(hex_content)
            if decompressed:
                content = decompressed
                compression = 0  # Treat as uncompressed from here on
            elif msg_type == 1:
                content = "[压缩文本]"

        if not content.strip() and msg_type == 1:
            return None

        # status == 3 → sent by self; otherwise received
        is_sender = (status == 3)

        content_type = "text"
        media: List[MediaRef] = []

        if msg_type == 3:
            content_type = "image"
            content = "[图片]"
            media = [MediaRef(type="image")]
        elif msg_type == 34:
            content_type = "audio"
            content = "[语音]"
            media = [MediaRef(type="voice")]
        elif msg_type == 43:
            content_type = "video"
            content = "[视频]"
            media = [MediaRef(type="video")]
        elif msg_type == 47:
            content_type = "sticker"
            content = "[表情]"
        elif msg_type == 48:
            content_type = "location"
            content = "[位置]"
        elif msg_type == 49:
            content_type = "link"
            if compression != 0 and not content.strip().startswith("<"):
                content = "[链接/文件]"
            else:
                content, media = _parse_type49_xml(content)
        elif msg_type == 10000:
            pass  # system message, keep content
        elif msg_type == 10002:
            pass  # revoke message
        elif msg_type not in (1,):
            # Unknown non-text type
            if not content.strip() or compression != 0:
                return None

        role = "user" if is_sender else "assistant"

        timestamp = ""
        if create_time:
            try:
                dt = datetime.fromtimestamp(create_time, tz=timezone.utc)
                timestamp = dt.isoformat()
            except (ValueError, OSError):
                pass

        return Message(
            role=role,
            content=content,
            timestamp=timestamp,
            message_id=str(local_id),
            content_type=content_type,
            media=media,
        )

    def _read_msg_table_via_cli(self, db_path: Path, raw_key: str) -> Iterator[Conversation]:
        """读取 MSG 表 (旧版 WeChat 4.x 格式) 通过 CLI"""
        rows = self._sqlcipher_query(
            db_path, raw_key,
            "SELECT DISTINCT StrTalker FROM MSG "
            "WHERE StrTalker IS NOT NULL AND StrTalker != '' ORDER BY StrTalker;"
        )
        if not rows:
            return

        for talker_row in rows:
            talker = talker_row[0]
            msg_rows = self._sqlcipher_query(
                db_path, raw_key,
                f"SELECT MsgSvrID, Type, SubType, IsSender, CreateTime, "
                f"StrTalker, StrContent, DisplayContent FROM MSG "
                f"WHERE StrTalker = '{talker}' ORDER BY CreateTime ASC;"
            )
            if not msg_rows:
                continue

            messages = []
            for row in msg_rows:
                msg = self._parse_msg_row(row)
                if msg:
                    messages.append(msg)

            if not messages:
                continue

            conv_id = f"wechat-{_sanitize_id(talker)}"
            is_group = "@chatroom" in talker

            yield Conversation(
                id=conv_id,
                platform="wechat",
                title=talker,
                participants=[talker] if not is_group else [],
                messages=messages,
                metadata={
                    "talker": talker,
                    "is_group": is_group,
                    "db_file": db_path.name,
                },
            )

    def _parse_msg_row(self, row) -> Optional[Message]:
        """解析 MSG 表的一行 (旧版格式)"""
        msg_id = row[0] or ""
        msg_type = int(row[1] or 0)
        is_sender = int(row[3] or 0)
        create_time = int(row[4] or 0)
        content = str(row[6] or "")

        if not content.strip():
            return None

        content_type = "text"
        media: List[MediaRef] = []

        if msg_type == 3:
            content_type = "image"
            media = [MediaRef(type="image")]
        elif msg_type == 34:
            content_type = "audio"
            media = [MediaRef(type="voice")]
        elif msg_type == 43:
            content_type = "video"
            media = [MediaRef(type="video")]
        elif msg_type == 49:
            content_type = "link"
            content, media = _parse_type49_xml(content)
        elif msg_type == 10000:
            pass  # system message

        role = "user" if is_sender else "assistant"

        timestamp = ""
        if create_time:
            try:
                dt = datetime.fromtimestamp(create_time, tz=timezone.utc)
                timestamp = dt.isoformat()
            except (ValueError, OSError):
                pass

        return Message(
            role=role,
            content=content,
            timestamp=timestamp,
            message_id=str(msg_id),
            content_type=content_type,
            media=media,
        )


def _sanitize_id(s: str) -> str:
    """将字符串转为安全的文件名/ID (保留 Unicode 字母和数字)"""
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in s)
