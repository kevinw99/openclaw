"""File Path Signal - 基于工具调用中的文件路径评分"""

from typing import List

from ..models.category import Entity
from ..models.session import SessionMessage
from ..parser.message_extractor import MessageExtractor


class FilePathSignal:
    """通过文件路径匹配实体 (最高权重信号)"""

    def __init__(self):
        self.extractor = MessageExtractor()

    def score(self, messages: List[SessionMessage], entity: Entity) -> float:
        """计算文件路径匹配分数 (0.0 - 1.0)

        综合考虑比例和绝对数量：即使在大型多主题会话中，
        只要某实体有足够多的文件路径匹配，就应被识别。
        """
        if not messages or not entity.path_patterns:
            return 0.0

        matched = 0
        total_with_paths = 0

        for msg in messages:
            paths = self.extractor.extract_file_paths(msg)
            if not paths:
                continue
            total_with_paths += 1
            for path in paths:
                if self._matches_entity(path, entity):
                    matched += 1
                    break

        if total_with_paths == 0:
            return 0.0

        # 比例分数
        ratio = matched / total_with_paths

        # 绝对数量奖励：匹配次数越多，分数越高
        # 3次匹配=0.3基础分, 5次=0.4, 10次=0.5, 20+=0.6
        if matched >= 20:
            count_bonus = 0.6
        elif matched >= 10:
            count_bonus = 0.5
        elif matched >= 5:
            count_bonus = 0.4
        elif matched >= 3:
            count_bonus = 0.3
        elif matched >= 1:
            count_bonus = 0.2
        else:
            return 0.0

        # 取比例分数和数量奖励的较大值
        return max(ratio, count_bonus)

    def matched_messages(self, messages: List[SessionMessage], entity: Entity) -> List[SessionMessage]:
        """返回匹配的消息列表"""
        result = []
        for msg in messages:
            paths = self.extractor.extract_file_paths(msg)
            for path in paths:
                if self._matches_entity(path, entity):
                    result.append(msg)
                    break
        return result

    def _matches_entity(self, path: str, entity: Entity) -> bool:
        """检查路径是否匹配实体"""
        for pattern in entity.path_patterns:
            if path.startswith(pattern) or pattern.rstrip("/") in path:
                return True
        return False
