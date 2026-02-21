"""适配器基类"""

from abc import ABC, abstractmethod
from typing import Iterator, List, Tuple

from ..models import Conversation


class BaseAdapter(ABC):
    """平台适配器抽象基类"""

    @property
    @abstractmethod
    def platform(self) -> str:
        """平台标识符, 如 'chatgpt', 'grok'"""

    @abstractmethod
    def extract(self, source: str) -> Iterator[Conversation]:
        """从数据源提取对话

        Args:
            source: 数据源路径或标识 (如 ZIP 文件路径、URL 等)

        Yields:
            Conversation 对象
        """

    def check_compatibility(self) -> List[str]:
        """检查适配器与当前数据源的兼容性

        返回警告列表。空列表表示一切正常。
        子类可覆盖此方法实现平台特定检查。
        """
        return []
