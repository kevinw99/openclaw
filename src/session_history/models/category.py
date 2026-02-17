"""Category 数据模型 - 实体和分类"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class EntityType(Enum):
    """实体类型"""
    SPEC = "spec"
    SOURCE = "source"
    RESEARCH = "research"
    KNOWLEDGE = "knowledge"
    TOOL = "tool"
    UNCATEGORIZED = "uncategorized"


@dataclass
class Entity:
    """项目实体"""
    entity_type: EntityType
    name: str  # 目录名
    display_name: str  # 显示名
    directory: str  # 相对于项目根的路径
    keywords: List[str] = field(default_factory=list)
    path_patterns: List[str] = field(default_factory=list)  # 路径匹配模式
    text_patterns: List[str] = field(default_factory=list)  # 正则文本模式

    @property
    def history_dir(self) -> str:
        return f"{self.directory}/history"

    @property
    def entity_id(self) -> str:
        return f"{self.entity_type.value}:{self.name}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "name": self.name,
            "display_name": self.display_name,
            "directory": self.directory,
        }


@dataclass
class EntityMatch:
    """单个实体的匹配结果"""
    entity: Entity
    confidence: float = 0.0
    file_path_score: float = 0.0
    text_pattern_score: float = 0.0
    keyword_score: float = 0.0
    matched_messages: int = 0
    total_messages: int = 0
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity.entity_id,
            "display_name": self.entity.display_name,
            "confidence": round(self.confidence, 3),
            "file_path_score": round(self.file_path_score, 3),
            "text_pattern_score": round(self.text_pattern_score, 3),
            "keyword_score": round(self.keyword_score, 3),
            "matched_messages": self.matched_messages,
            "total_messages": self.total_messages,
            "evidence": self.evidence[:5],
        }


@dataclass
class SessionClassification:
    """会话分类结果"""
    session_id: str
    file_path: str
    matches: List[EntityMatch] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    message_count: int = 0
    user_message_count: int = 0

    @property
    def is_uncategorized(self) -> bool:
        return len(self.matches) == 0

    @property
    def primary_entity(self) -> str:
        if self.matches:
            return self.matches[0].entity.display_name
        return "Uncategorized"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "file_path": self.file_path,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "message_count": self.message_count,
            "user_message_count": self.user_message_count,
            "primary_entity": self.primary_entity,
            "matches": [m.to_dict() for m in self.matches],
        }
