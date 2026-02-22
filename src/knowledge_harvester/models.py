"""数据模型 - 统一的对话和消息格式

遵循 specs/03_personal-knowledge-extraction 定义的统一 schema。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MediaRef:
    """媒体引用 (图片、文件、语音、链接等)"""
    type: str           # "image" | "file" | "voice" | "link" | "video" | "mini_program"
    path: str = ""      # 本地路径 (下载后)
    original_url: str = ""
    filename: str = ""
    size_bytes: int = 0
    description: str = ""   # 文章摘要 / 文件描述 (来自 XML <des>)
    summary: str = ""       # AI 生成的内容摘要 (Tier 2, 后续填充)


def _media_ref_to_dict(m: MediaRef) -> Dict[str, Any]:
    """MediaRef → dict, 省略空字段 (sparse serialization)"""
    d: Dict[str, Any] = {"type": m.type}
    if m.path:
        d["path"] = m.path
    if m.original_url:
        d["original_url"] = m.original_url
    if m.filename:
        d["filename"] = m.filename
    if m.size_bytes:
        d["size_bytes"] = m.size_bytes
    if m.description:
        d["description"] = m.description
    if m.summary:
        d["summary"] = m.summary
    return d


@dataclass
class Message:
    """单条消息"""
    role: str               # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: str = ""     # ISO 8601
    message_id: str = ""    # 平台原始消息 ID
    content_type: str = "text"  # "text" | "image" | "audio" | "file" | "mixed"
    media: List[MediaRef] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.message_id:
            result["message_id"] = self.message_id
        if self.content_type != "text":
            result["content_type"] = self.content_type
        if self.media:
            result["media"] = [_media_ref_to_dict(m) for m in self.media]
        return result

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Message":
        media = [
            MediaRef(
                type=m["type"],
                path=m.get("path", ""),
                original_url=m.get("original_url", ""),
                filename=m.get("filename", ""),
                size_bytes=m.get("size_bytes", 0),
                description=m.get("description", ""),
                summary=m.get("summary", ""),
            )
            for m in d.get("media", [])
        ]
        return cls(
            role=d["role"],
            content=d["content"],
            timestamp=d.get("timestamp", ""),
            message_id=d.get("message_id", ""),
            content_type=d.get("content_type", "text"),
            media=media,
        )


@dataclass
class Conversation:
    """一段对话"""
    id: str
    platform: str       # "chatgpt" | "grok" | "doubao" | "wechat"
    title: str
    participants: List[str] = field(default_factory=list)
    messages: List[Message] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def to_index_entry(self) -> Dict[str, Any]:
        """生成索引条目 (不含消息体)"""
        first_ts = ""
        last_ts = ""
        if self.messages:
            first_ts = self.messages[0].timestamp
            last_ts = self.messages[-1].timestamp
        return {
            "id": self.id,
            "platform": self.platform,
            "title": self.title,
            "participants": self.participants,
            "message_count": self.message_count,
            "first_message_time": first_ts,
            "last_message_time": last_ts,
            "metadata": self.metadata,
        }
