"""Index 数据模型 - 索引和引用"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MessagePointer:
    """消息指针 - 指向 JSONL 中的特定消息"""
    uuid: str
    line_number: int
    msg_type: str  # user, assistant
    timestamp: str = ""
    preview: str = ""  # 前100个字符的预览

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "line_number": self.line_number,
            "msg_type": self.msg_type,
            "timestamp": self.timestamp,
            "preview": self.preview,
        }


@dataclass
class SessionReference:
    """会话引用 - 一个会话对某个实体的引用"""
    session_id: str
    file_path: str  # JSONL 文件的绝对路径
    confidence: float = 0.0
    start_time: str = ""
    end_time: str = ""
    message_count: int = 0
    matched_messages: List[MessagePointer] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "file_path": self.file_path,
            "confidence": round(self.confidence, 3),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "message_count": self.message_count,
            "matched_message_count": len(self.matched_messages),
            "matched_messages": [m.to_dict() for m in self.matched_messages],
            "evidence": self.evidence[:5],
        }


@dataclass
class EntityIndex:
    """实体索引 - 存储在 entity/history/sessions-index.json"""
    entity_id: str
    entity_type: str
    display_name: str
    directory: str
    sessions: List[SessionReference] = field(default_factory=list)
    last_updated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "display_name": self.display_name,
            "directory": self.directory,
            "session_count": len(self.sessions),
            "sessions": [s.to_dict() for s in self.sessions],
            "last_updated": self.last_updated,
        }
