"""Keyword Signal - 基于关键词匹配评分"""

from typing import List, Set

from ..models.category import Entity
from ..models.session import SessionMessage
from ..parser.message_extractor import MessageExtractor


class KeywordSignal:
    """通过关键词匹配实体 (最低权重信号)"""

    def __init__(self):
        self.extractor = MessageExtractor()

    def score(self, messages: List[SessionMessage], entity: Entity) -> float:
        """计算关键词匹配分数 (0.0 - 1.0)"""
        if not messages or not entity.keywords:
            return 0.0

        entity_keywords = self._normalize_keywords(entity.keywords)
        matched = 0
        total_with_text = 0

        for msg in messages:
            msg_keywords = self.extractor.extract_keywords(msg)
            if not msg_keywords:
                continue
            total_with_text += 1
            # 检查消息关键词是否与实体关键词有交集
            msg_lower = {k.lower() for k in msg_keywords}
            if msg_lower & entity_keywords:
                matched += 1

        if total_with_text == 0:
            return 0.0

        ratio = matched / total_with_text
        if matched > 0:
            return max(0.1, min(ratio, 0.8))  # 关键词匹配有上限
        return 0.0

    def matched_messages(self, messages: List[SessionMessage], entity: Entity) -> List[SessionMessage]:
        """返回匹配的消息列表"""
        entity_keywords = self._normalize_keywords(entity.keywords)
        result = []
        for msg in messages:
            msg_keywords = self.extractor.extract_keywords(msg)
            msg_lower = {k.lower() for k in msg_keywords}
            if msg_lower & entity_keywords:
                result.append(msg)
        return result

    def _normalize_keywords(self, keywords: List[str]) -> Set[str]:
        """归一化关键词"""
        normalized = set()
        for kw in keywords:
            normalized.add(kw.lower())
            # 对下划线/连字符分词也加入
            for part in kw.replace("-", "_").split("_"):
                if part and len(part) > 2:
                    normalized.add(part.lower())
        return normalized
