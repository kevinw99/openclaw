"""Turn Entity Classifier - detect entity boundaries by turn, split multi-entity sessions"""

import re
from typing import Dict, List, Optional, Tuple

from ..models.category import Entity, EntityType
from ..models.turn import Turn


class TurnEntityClassifier:
    """Classify turns by entity, splitting sessions into contiguous entity segments."""

    def __init__(self):
        self._compiled_cache: Dict[str, list] = {}

    def classify_turns(
        self, turns: List[Turn], entities: List[Entity],
    ) -> List[Tuple[Optional[Entity], List[Turn]]]:
        """Group turns by contiguous entity.

        Only checks SPEC-type entities. Returns (entity_or_None, turns) segment list.
        None segments are later absorbed into adjacent classified segments.
        """
        spec_entities = [e for e in entities if e.entity_type == EntityType.SPEC]
        if not spec_entities or not turns:
            return [(None, turns)] if turns else []

        turn_entities: List[Optional[Entity]] = []
        for turn in turns:
            entity = self._classify_single_turn(turn, spec_entities)
            turn_entities.append(entity)

        raw_segments = self._group_consecutive(turns, turn_entities)
        segments = self._absorb_none_segments(raw_segments)

        return segments

    def _classify_single_turn(
        self, turn: Turn, entities: List[Entity],
    ) -> Optional[Entity]:
        """Classify a single turn.

        Priority:
        1. path_patterns in tool_narrative
        2. text_patterns in user_prompt + assistant_response
        """
        if turn.tool_narrative:
            for entity in entities:
                for pattern in entity.path_patterns:
                    clean = pattern.rstrip("/")
                    if clean in turn.tool_narrative:
                        return entity

        combined_text = (turn.user_prompt or "") + "\n" + (turn.assistant_response or "")
        if combined_text.strip():
            for entity in entities:
                compiled = self._get_compiled(entity)
                for pat in compiled:
                    if pat.search(combined_text):
                        return entity

        return None

    def _get_compiled(self, entity: Entity) -> list:
        """Cache compiled regex patterns."""
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
        """Group consecutive turns with the same entity."""
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
        """Check if two entities are the same."""
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        return a.entity_id == b.entity_id

    def _absorb_none_segments(
        self,
        segments: List[Tuple[Optional[Entity], List[Turn]]],
    ) -> List[Tuple[Optional[Entity], List[Turn]]]:
        """Absorb None segments into adjacent classified segments.

        Rules:
        - Prefer absorbing into preceding classified segment
        - If no preceding segment, absorb into following
        - If all None, return single (None, all_turns) segment
        """
        if not segments:
            return segments

        if len(segments) == 1:
            return segments

        result: List[Tuple[Optional[Entity], List[Turn]]] = []

        for i, (entity, turns) in enumerate(segments):
            if entity is not None:
                result.append((entity, list(turns)))
            else:
                if result and result[-1][0] is not None:
                    result[-1][1].extend(turns)
                else:
                    result.append((None, list(turns)))

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

        if pending_none_turns:
            if final:
                final[-1][1].extend(pending_none_turns)
            else:
                final.append((None, pending_none_turns))

        return final
