"""ChatGPT 官方数据导出解析器

解析从 ChatGPT Settings > Data Controls > Export 导出的 ZIP 文件中的 conversations.json。

导出格式:
  conversations.json 是一个数组, 每个元素是一段对话, 包含:
    - title: 对话标题
    - create_time: 创建时间 (Unix timestamp)
    - mapping: dict[node_id -> node], 节点树结构
      - 每个 node 有 id, message (可为 null), parent, children
      - message 有 author.role, content.parts, create_time 等
"""

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List

from .base import BaseAdapter
from ..models import Conversation, MediaRef, Message


class ChatGPTAdapter(BaseAdapter):
    """解析 ChatGPT 官方导出的 conversations.json"""

    @property
    def platform(self) -> str:
        return "chatgpt"

    def extract(self, source: str) -> Iterator[Conversation]:
        """从 ChatGPT 导出 ZIP 或 JSON 文件提取对话

        Args:
            source: ZIP 文件路径或 conversations.json 路径
        """
        path = Path(source)

        if path.suffix == ".zip":
            conversations_data = self._read_from_zip(path)
        elif path.suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                conversations_data = json.load(f)
        else:
            raise ValueError(f"不支持的文件格式: {path.suffix} (需要 .zip 或 .json)")

        if not isinstance(conversations_data, list):
            raise ValueError("conversations.json 应该是一个数组")

        for conv_data in conversations_data:
            conv = self._parse_conversation(conv_data)
            if conv and conv.messages:
                yield conv

    def _read_from_zip(self, zip_path: Path) -> list:
        """从 ZIP 文件中读取 conversations.json"""
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            # 查找 conversations.json (可能在子目录)
            conv_file = None
            for name in names:
                if name.endswith("conversations.json"):
                    conv_file = name
                    break

            if conv_file is None:
                raise FileNotFoundError("ZIP 中未找到 conversations.json")

            with zf.open(conv_file) as f:
                return json.load(f)

    def _parse_conversation(self, data: dict) -> Conversation:
        """解析单段对话"""
        conv_id = data.get("id", "")
        title = data.get("title", "")
        create_time = data.get("create_time")
        mapping = data.get("mapping", {})

        # 从 mapping 树中提取有序消息
        messages = self._extract_messages(mapping)

        # 元数据
        metadata = {}
        if create_time:
            metadata["create_time"] = _timestamp_to_iso(create_time)
        update_time = data.get("update_time")
        if update_time:
            metadata["update_time"] = _timestamp_to_iso(update_time)
        model_slug = data.get("default_model_slug")
        if model_slug:
            metadata["model"] = model_slug

        return Conversation(
            id=conv_id,
            platform="chatgpt",
            title=title,
            participants=["user", "chatgpt"],
            messages=messages,
            metadata=metadata,
        )

    def _extract_messages(self, mapping: dict) -> List[Message]:
        """从 mapping 树中按顺序提取消息

        ChatGPT mapping 是一棵树:
          - 找到根节点 (没有 parent 或 parent 不在 mapping 中)
          - 沿 children 遍历主线 (取每个节点的第一个 child)
        """
        if not mapping:
            return []

        # 找根节点
        root_id = None
        for node_id, node in mapping.items():
            parent = node.get("parent")
            if parent is None or parent not in mapping:
                root_id = node_id
                break

        if root_id is None:
            return []

        # 沿主线遍历, 提取消息
        messages = []
        current_id = root_id
        visited = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            node = mapping.get(current_id)
            if node is None:
                break

            msg = self._parse_node_message(node)
            if msg is not None:
                messages.append(msg)

            # 取第一个 child 继续
            children = node.get("children", [])
            current_id = children[0] if children else None

        return messages

    def _parse_node_message(self, node: dict) -> Message:
        """解析节点中的消息, 返回 None 如果不是有效消息"""
        msg_data = node.get("message")
        if msg_data is None:
            return None

        author = msg_data.get("author", {})
        role = author.get("role", "")

        # 跳过 system 消息 (通常是空的初始消息)
        if role == "system":
            content = self._extract_content(msg_data)
            if not content.strip():
                return None

        # 跳过未完成的消息
        status = msg_data.get("status")
        if status and status not in ("finished_successfully", "finished_partial_completion"):
            return None

        content, media = self._extract_content_and_media(msg_data)
        if not content and not media:
            return None

        # 时间戳
        create_time = msg_data.get("create_time")
        timestamp = _timestamp_to_iso(create_time) if create_time else ""

        # 消息 ID
        message_id = msg_data.get("id", "")

        # 标准化 role
        if role == "tool":
            role = "system"

        # 内容类型
        content_type = "text"
        if media and not content:
            content_type = media[0].type  # "image" or "voice"
        elif media and content:
            content_type = "mixed"

        return Message(
            role=role,
            content=content,
            timestamp=timestamp,
            message_id=message_id,
            content_type=content_type,
            media=media,
        )

    def _extract_content(self, msg_data: dict) -> str:
        """提取纯文本内容"""
        content_obj = msg_data.get("content", {})
        parts = content_obj.get("parts", [])
        text_parts = []
        for part in parts:
            if isinstance(part, str):
                text_parts.append(part)
        return "\n".join(text_parts)

    def _extract_content_and_media(self, msg_data: dict) -> tuple:
        """提取文本内容和媒体引用"""
        content_obj = msg_data.get("content", {})
        parts = content_obj.get("parts", [])

        text_parts = []
        media_refs = []

        for part in parts:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict):
                content_type = part.get("content_type", "")
                if content_type == "image_asset_pointer":
                    asset = part.get("asset_pointer", "")
                    media_refs.append(MediaRef(
                        type="image",
                        original_url=asset,
                        size_bytes=part.get("size_bytes", 0),
                    ))
                elif content_type == "audio_asset_pointer":
                    asset = part.get("asset_pointer", "")
                    media_refs.append(MediaRef(
                        type="voice",
                        original_url=asset,
                        size_bytes=part.get("size_bytes", 0),
                    ))

        return "\n".join(text_parts), media_refs


def _timestamp_to_iso(ts) -> str:
    """Unix timestamp → ISO 8601 字符串"""
    if ts is None:
        return ""
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError, OSError):
        return ""
