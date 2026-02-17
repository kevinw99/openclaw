"""Session 数据模型"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ContentBlock:
    """消息内容块"""
    block_type: str  # text, tool_use, tool_result, thinking
    text: str = ""
    tool_name: str = ""
    tool_input: Dict[str, Any] = field(default_factory=dict)
    tool_use_id: str = ""


@dataclass
class SessionMessage:
    """单条会话消息"""
    uuid: str
    parent_uuid: Optional[str]
    msg_type: str  # user, assistant, system, progress
    role: str = ""  # user, assistant
    content_blocks: List[ContentBlock] = field(default_factory=list)
    timestamp: str = ""
    session_id: str = ""
    line_number: int = 0  # JSONL 中的行号
    is_sidechain: bool = False
    subtype: str = ""
    cwd: str = ""  # 工作目录

    @property
    def text_content(self) -> str:
        """获取纯文本内容"""
        parts = []
        for block in self.content_blocks:
            if block.block_type == "text" and block.text:
                parts.append(block.text)
        return "\n".join(parts)

    @property
    def file_paths(self) -> List[str]:
        """提取所有工具调用中的文件路径"""
        paths = []
        for block in self.content_blocks:
            if block.block_type == "tool_use":
                for key in ("file_path", "path", "notebook_path"):
                    val = block.tool_input.get(key, "")
                    if val and "/" in val:
                        paths.append(val)
                # Bash command 中的路径
                cmd = block.tool_input.get("command", "")
                if cmd:
                    paths.extend(_extract_paths_from_command(cmd))
                # Grep/Glob 的 path 参数
                pattern = block.tool_input.get("pattern", "")
                if pattern and "/" in pattern:
                    paths.append(pattern)
        return paths

    @property
    def tool_names(self) -> List[str]:
        """获取所有工具调用名称"""
        return [b.tool_name for b in self.content_blocks if b.block_type == "tool_use"]


@dataclass
class Session:
    """会话"""
    session_id: str
    file_path: str  # JSONL 文件路径
    messages: List[SessionMessage] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    version: str = ""
    git_branch: str = ""

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def user_message_count(self) -> int:
        return sum(1 for m in self.messages if m.role == "user")

    @property
    def assistant_message_count(self) -> int:
        return sum(1 for m in self.messages if m.role == "assistant")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "file_path": self.file_path,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "message_count": self.message_count,
            "user_messages": self.user_message_count,
            "assistant_messages": self.assistant_message_count,
            "version": self.version,
            "git_branch": self.git_branch,
        }


def _extract_paths_from_command(cmd: str) -> List[str]:
    """从 Bash 命令中提取文件路径"""
    import re
    paths = []
    # 匹配绝对路径或项目相对路径
    for match in re.finditer(r'(?:/Users/\S+|(?:规格|源代码|研究|知识库|工具)/\S+)', cmd):
        path = match.group(0).rstrip("'\"`;,)")
        paths.append(path)
    return paths
