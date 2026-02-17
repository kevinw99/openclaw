"""Text Pattern Signal - 基于正则文本模式评分"""

import re
from typing import List

from ..models.category import Entity
from ..models.session import SessionMessage
from ..parser.message_extractor import MessageExtractor


class TextPatternSignal:
    """通过正则表达式文本模式匹配实体"""

    def __init__(self):
        self.extractor = MessageExtractor()
        self._compiled_cache = {}

    def score(self, messages: List[SessionMessage], entity: Entity) -> float:
        """计算文本模式匹配分数 (0.0 - 1.0)

        综合考虑比例和绝对数量：在多主题会话中，
        即使占比低，足够多的文本匹配也应被识别。
        """
        if not messages or not entity.text_patterns:
            return 0.0

        patterns = self._get_compiled(entity)
        matched = 0
        total_with_text = 0

        for msg in messages:
            text = self.extractor.extract_text(msg)
            if not text:
                continue
            total_with_text += 1
            for pat in patterns:
                if pat.search(text):
                    matched += 1
                    break

        if total_with_text == 0:
            return 0.0

        ratio = matched / total_with_text

        # 绝对数量奖励
        if matched >= 15:
            count_bonus = 0.5
        elif matched >= 8:
            count_bonus = 0.4
        elif matched >= 4:
            count_bonus = 0.3
        elif matched >= 2:
            count_bonus = 0.2
        elif matched >= 1:
            count_bonus = 0.1
        else:
            return 0.0

        return max(ratio, count_bonus)

    def matched_messages(self, messages: List[SessionMessage], entity: Entity) -> List[SessionMessage]:
        """返回匹配的消息列表"""
        patterns = self._get_compiled(entity)
        result = []
        for msg in messages:
            text = self.extractor.extract_text(msg)
            if not text:
                continue
            for pat in patterns:
                if pat.search(text):
                    result.append(msg)
                    break
        return result

    def _get_compiled(self, entity: Entity) -> list:
        """获取编译后的正则表达式 (缓存)"""
        key = entity.entity_id
        if key not in self._compiled_cache:
            compiled = []
            for pattern in entity.text_patterns:
                try:
                    compiled.append(re.compile(pattern, re.IGNORECASE))
                except re.error:
                    continue
            self._compiled_cache[key] = compiled
        return self._compiled_cache[key]
