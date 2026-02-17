"""Turn 数据模型 - 用户提问 + AI 回答 的一轮对话"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Turn:
    """一轮对话: 用户提示 → AI 回答"""
    turn_number: int
    timestamp: str  # 用户提问的时间
    title: str  # 自动生成的标题 (用户提示前60字符)
    user_prompt: str  # 用户输入文本
    assistant_response: str  # AI 最终回答文本 (最后一个 tool_use 之后的文本)
    tool_counts: Dict[str, int] = field(default_factory=dict)  # 工具调用次数 {tool_name: count}
    tool_narrative: str = ""  # 工具使用叙述 (文件路径, bash 描述等)
    is_long_prompt: bool = False  # 用户输入是否超过 500 字符

    @property
    def tool_summary_line(self) -> str:
        """生成工具摘要行, 如 'Read (4), Write (5), Bash (1)'"""
        if not self.tool_counts:
            return ""
        parts = [f"{name} ({count})" for name, count in sorted(self.tool_counts.items())]
        return ", ".join(parts)

    @property
    def time_short(self) -> str:
        """提取 HH:MM 格式的时间"""
        if len(self.timestamp) >= 16:
            return self.timestamp[11:16]
        return self.timestamp
