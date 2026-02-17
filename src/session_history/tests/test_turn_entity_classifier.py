"""Tests for TurnEntityClassifier"""

import unittest

from session_history.models.category import Entity, EntityType
from session_history.models.turn import Turn
from session_history.classifier.turn_entity_classifier import TurnEntityClassifier


def _make_entity(name: str, directory: str = None, path_patterns=None, text_patterns=None) -> Entity:
    dir_path = directory or f"specs/{name}"
    return Entity(
        entity_type=EntityType.SPEC,
        name=name,
        display_name=f"Spec {name}",
        directory=dir_path,
        path_patterns=path_patterns or [f"{dir_path}/"],
        text_patterns=text_patterns or [rf"Spec.*{name}"],
    )


def _make_turn(
    num: int, tool_narrative: str = "", user_prompt: str = "",
    assistant_response: str = "", timestamp: str = "",
) -> Turn:
    return Turn(
        turn_number=num,
        timestamp=timestamp or f"2026-02-04T09:{num:02d}:00",
        title=f"Turn {num}",
        user_prompt=user_prompt,
        assistant_response=assistant_response,
        tool_narrative=tool_narrative,
    )


class TestTurnEntityClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = TurnEntityClassifier()
        self.spec02 = _make_entity(
            "02_auth-system",
            path_patterns=[
                "specs/02_auth-system/",
            ],
            text_patterns=[
                r"[Ss]pec\s*#?02\b",
                r"auth.system",
            ],
        )
        self.spec03 = _make_entity(
            "03_api-redesign",
            path_patterns=[
                "specs/03_api-redesign/",
            ],
            text_patterns=[
                r"[Ss]pec\s*#?03\b",
                r"api.redesign",
            ],
        )
        self.entities = [self.spec02, self.spec03]

    def test_single_entity_session(self):
        """Single entity session -> one segment."""
        turns = [
            _make_turn(1, tool_narrative="specs/02_auth-system/design.md"),
            _make_turn(2, tool_narrative="specs/02_auth-system/tasks.md"),
            _make_turn(3, user_prompt="Update the auth system design"),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        self.assertEqual(len(segments), 1)
        entity, seg_turns = segments[0]
        self.assertEqual(entity.entity_id, self.spec02.entity_id)
        self.assertEqual(len(seg_turns), 3)

    def test_multi_entity_session_splits(self):
        """Multi-entity session -> split into multiple segments."""
        turns = [
            _make_turn(1, tool_narrative="specs/02_auth-system/design.md"),
            _make_turn(2, tool_narrative="specs/02_auth-system/tasks.md"),
            _make_turn(3, tool_narrative="specs/03_api-redesign/requirements.md"),
            _make_turn(4, user_prompt="Continue working on api redesign plan"),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        self.assertEqual(len(segments), 2)

        entity1, turns1 = segments[0]
        self.assertEqual(entity1.entity_id, self.spec02.entity_id)
        self.assertEqual(len(turns1), 2)

        entity2, turns2 = segments[1]
        self.assertEqual(entity2.entity_id, self.spec03.entity_id)
        self.assertEqual(len(turns2), 2)

    def test_none_turns_absorbed_into_preceding(self):
        """Unclassified turns absorbed into preceding classified segment."""
        turns = [
            _make_turn(1, tool_narrative="specs/02_auth-system/design.md"),
            _make_turn(2),  # no entity signals
            _make_turn(3, tool_narrative="specs/03_api-redesign/requirements.md"),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        self.assertEqual(len(segments), 2)

        entity1, turns1 = segments[0]
        self.assertEqual(entity1.entity_id, self.spec02.entity_id)
        self.assertEqual(len(turns1), 2)  # turn 1 + absorbed turn 2

        entity2, turns2 = segments[1]
        self.assertEqual(entity2.entity_id, self.spec03.entity_id)
        self.assertEqual(len(turns2), 1)

    def test_leading_none_turns_absorbed_into_following(self):
        """Leading unclassified turns absorbed into following classified segment."""
        turns = [
            _make_turn(1),  # no entity signals
            _make_turn(2),  # no entity signals
            _make_turn(3, tool_narrative="specs/03_api-redesign/requirements.md"),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        self.assertEqual(len(segments), 1)

        entity, seg_turns = segments[0]
        self.assertEqual(entity.entity_id, self.spec03.entity_id)
        self.assertEqual(len(seg_turns), 3)

    def test_all_none_turns(self):
        """All unclassified -> single None segment."""
        turns = [
            _make_turn(1),
            _make_turn(2),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        self.assertEqual(len(segments), 1)
        entity, seg_turns = segments[0]
        self.assertIsNone(entity)
        self.assertEqual(len(seg_turns), 2)

    def test_empty_turns(self):
        """Empty turns list."""
        segments = self.classifier.classify_turns([], self.entities)
        self.assertEqual(len(segments), 0)

    def test_text_pattern_matching(self):
        """Match entity via text patterns."""
        turns = [
            _make_turn(1, user_prompt="Let's work on Spec 02"),
            _make_turn(2, assistant_response="I'll update the auth system"),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        self.assertEqual(len(segments), 1)
        entity, _ = segments[0]
        self.assertEqual(entity.entity_id, self.spec02.entity_id)

    def test_path_pattern_takes_priority(self):
        """Path patterns take priority over text patterns."""
        turns = [
            _make_turn(
                1,
                tool_narrative="specs/02_auth-system/design.md",
                user_prompt="Spec 03 related text",  # text says 03 but path says 02
            ),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        entity, _ = segments[0]
        self.assertEqual(entity.entity_id, self.spec02.entity_id)

    def test_only_spec_entities_participate(self):
        """Non-SPEC entities don't participate in turn splitting."""
        source_entity = Entity(
            entity_type=EntityType.SOURCE,
            name="data_processor",
            display_name="src: data_processor",
            directory="src/data_processor",
            path_patterns=["src/data_processor/"],
            text_patterns=[r"src/data_processor"],
        )
        turns = [
            _make_turn(1, tool_narrative="src/data_processor/cli.py"),
        ]
        segments = self.classifier.classify_turns(turns, [source_entity])
        self.assertEqual(len(segments), 1)
        entity, _ = segments[0]
        self.assertIsNone(entity)


if __name__ == "__main__":
    unittest.main()
