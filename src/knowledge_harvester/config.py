"""配置管理"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """全局配置"""
    # 项目根目录
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)

    # 对话输出根目录
    output_root: str = "知识库/conversations"

    # 媒体文件目录名
    media_dir: str = "media"

    @property
    def output_dir(self) -> Path:
        return self.project_root / self.output_root

    def platform_dir(self, platform: str) -> Path:
        return self.output_dir / platform

    def platform_media_dir(self, platform: str, conversation_id: str) -> Path:
        return self.output_dir / platform / self.media_dir / conversation_id

    def conversation_path(self, platform: str, conversation_id: str) -> Path:
        return self.platform_dir(platform) / f"{conversation_id}.jsonl"

    def index_path(self, platform: str) -> Path:
        return self.platform_dir(platform) / "index.json"

    def state_path(self, platform: str) -> Path:
        """增量提取状态文件"""
        return self.platform_dir(platform) / "state.json"
