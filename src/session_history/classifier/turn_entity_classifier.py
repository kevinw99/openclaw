"""Turn Entity Classifier - 按轮次检测实体边界, 拆分多实体 session"""

import re
from typing import Dict, List, Optional, Tuple

from ..models.category import Entity, EntityType
from ..models.turn import Turn


class TurnEntityClassifier:
    """按轮次识别实体, 将 session 分割为连续的实体段落"""

    def __init__(self):
        self._compiled_cache: Dict[str, list] = {}

    def classify_turns(
        self, turns: List[Turn], entities: List[Entity],
    ) -> List[Tuple[Optional[Entity], List[Turn]]]:
        """将轮次按连续实体分组

        只检查 SPEC 类型实体. 返回 (entity_or_None, turns) 段落列表.
        None 段落稍后会被吸收到相邻的已分类段落中.
        """
        spec_entities = [e for e in entities if e.entity_type == EntityType.SPEC]
        if not spec_entities or not turns:
            return [(None, turns)] if turns else []

        # 1. 逐轮次分类
        turn_entities: List[Optional[Entity]] = []
        for turn in turns:
            entity = self._classify_single_turn(turn, spec_entities)
            turn_entities.append(entity)

        # 2. 分组连续的相同实体
        raw_segments = self._group_consecutive(turns, turn_entities)

        # 3. 吸收 None 段落
        segments = self._absorb_none_segments(raw_segments)

        return segments

    def _classify_single_turn(
        self, turn: Turn, entities: List[Entity],
    ) -> Optional[Entity]:
        """对单个轮次进行实体分类

        优先级:
        1. tool_narrative 中的 path_patterns
        2. user_prompt + assistant_response 中的 text_patterns
        """
        # 1. 检查 tool_narrative 中的路径模式
        if turn.tool_narrative:
            for entity in entities:
                for pattern in entity.path_patterns:
                    clean = pattern.rstrip("/")
                    if clean in turn.tool_narrative:
                        return entity

        # 2. 检查文本中的正则模式
        combined_text = (turn.user_prompt or "") + "\n" + (turn.assistant_response or "")
        if combined_text.strip():
            for entity in entities:
                compiled = self._get_compiled(entity)
                for pat in compiled:
                    if pat.search(combined_text):
                        return entity

        return None

    def _get_compiled(self, entity: Entity) -> list:
        """缓存编译后的正则表达式"""
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

    def _group_consecutive(
        self,
        turns: List[Turn],
        turn_entities: List[Optional[Entity]],
    ) -> List[Tuple[Optional[Entity], List[Turn]]]:
        """将连续相同实体的轮次分组"""
        if not turns:
            return []

        segments: List[Tuple[Optional[Entity], List[Turn]]] = []
        current_entity = turn_entities[0]
        current_turns = [turns[0]]

        for i in range(1, len(turns)):
            entity = turn_entities[i]
            if self._same_entity(entity, current_entity):
                current_turns.append(turns[i])
            else:
                segments.append((current_entity, current_turns))
                current_entity = entity
                current_turns = [turns[i]]

        segments.append((current_entity, current_turns))
        return segments

    def _same_entity(self, a: Optional[Entity], b: Optional[Entity]) -> bool:
        """判断两个实体是否相同"""
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        return a.entity_id == b.entity_id

    def _absorb_none_segments(
        self,
        segments: List[Tuple[Optional[Entity], List[Turn]]],
    ) -> List[Tuple[Optional[Entity], List[Turn]]]:
        """将 None 段落吸收到相邻的已分类段落中

        规则:
        - 优先吸收到前面的已分类段落
        - 如果前面没有已分类段落, 吸收到后面的
        - 如果全是 None, 返回单个 (None, all_turns) 段落
        """
        if not segments:
            return segments

        # 如果只有一个段落, 直接返回
        if len(segments) == 1:
            return segments

        # 标记哪些段落需要吸收
        result: List[Tuple[Optional[Entity], List[Turn]]] = []

        for i, (entity, turns) in enumerate(segments):
            if entity is not None:
                result.append((entity, list(turns)))
            else:
                # None 段落: 尝试吸收到前一个已分类段落
                if result and result[-1][0] is not None:
                    result[-1][1].extend(turns)
                else:
                    # 暂存, 等后面有分类段落时再合并
                    result.append((None, list(turns)))

        # 第二遍: 将剩余的前置 None 段落吸收到后面的已分类段落
        final: List[Tuple[Optional[Entity], List[Turn]]] = []
        pending_none_turns: List[Turn] = []

        for entity, turns in result:
            if entity is None:
                pending_none_turns.extend(turns)
            else:
                if pending_none_turns:
                    turns = pending_none_turns + turns
                    pending_none_turns = []
                final.append((entity, turns))

        # 如果还有未吸收的 None turns (全部都是 None)
        if pending_none_turns:
            if final:
                final[-1][1].extend(pending_none_turns)
            else:
                final.append((None, pending_none_turns))

        return final
