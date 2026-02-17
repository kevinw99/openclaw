"""Settings - 配置管理"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class Settings:
    """全局设置"""
    # 项目根目录
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)

    # Claude Code session JSONL 目录
    sessions_dir: Path = field(default_factory=lambda: Path.home() / ".claude" / "projects" / "-Users-kweng-AI-Enpack-CCC")

    # 会话历史输出根目录
    history_root: str = "会话历史"

    # 分类阈值
    classification_threshold: float = 0.15

    # 信号权重
    signal_weights: Dict[str, float] = field(default_factory=lambda: {
        "file_path": 0.50,
        "text_pattern": 0.35,
        "keyword": 0.15,
    })

    # 是否排除 thinking blocks
    exclude_thinking: bool = True

    # 是否排除 sidechain 消息
    exclude_sidechains: bool = True

    # 增量扫描状态文件
    scan_state_file: str = ".scan-state.json"

    # 实体目录映射
    entity_dirs: Dict[str, str] = field(default_factory=lambda: {
        "spec": "规格",
        "source": "源代码",
        "research": "研究",
        "knowledge": "知识库",
        "tool": "工具",
    })

    @property
    def history_dir(self) -> Path:
        return self.project_root / self.history_root

    @property
    def scan_state_path(self) -> Path:
        return self.history_dir / self.scan_state_file
