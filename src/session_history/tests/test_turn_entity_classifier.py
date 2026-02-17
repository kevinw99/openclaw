"""Tests for TurnEntityClassifier"""

import unittest

from session_history.models.category import Entity, EntityType
from session_history.models.turn import Turn
from session_history.classifier.turn_entity_classifier import TurnEntityClassifier


def _make_entity(name: str, path_patterns=None, text_patterns=None) -> Entity:
    return Entity(
        entity_type=EntityType.SPEC,
        name=name,
        display_name=f"Spec {name}",
        directory=f"RESTRICTED/规格/{name}",
        path_patterns=path_patterns or [f"RESTRICTED/规格/{name}/"],
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
        self.r14 = _make_entity(
            "R14_知识库权限管理系统",
            path_patterns=[
                "RESTRICTED/规格/R14_知识库权限管理系统/",
                "规格/11_知识库权限管理系统/",
            ],
            text_patterns=[
                r"[Ss]pec\s*#?R14\b",
                r"知识库权限管理",
            ],
        )
        self.r15 = _make_entity(
            "R15_英联股份AI应用子公司设立构想计划",
            path_patterns=[
                "RESTRICTED/规格/R15_英联股份AI应用子公司设立构想计划/",
                "规格/12_英联股份AI应用子公司设立构想计划/",
            ],
            text_patterns=[
                r"[Ss]pec\s*#?R15\b",
                r"英联股份AI应用子公司",
            ],
        )
        self.entities = [self.r14, self.r15]

    def test_single_entity_session(self):
        """单实体 session → 一个段落"""
        turns = [
            _make_turn(1, tool_narrative="RESTRICTED/规格/R14_知识库权限管理系统/design.md"),
            _make_turn(2, tool_narrative="RESTRICTED/规格/R14_知识库权限管理系统/tasks.md"),
            _make_turn(3, user_prompt="Update the 知识库权限管理 design"),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        self.assertEqual(len(segments), 1)
        entity, seg_turns = segments[0]
        self.assertEqual(entity.entity_id, self.r14.entity_id)
        self.assertEqual(len(seg_turns), 3)

    def test_multi_entity_session_splits(self):
        """多实体 session → 拆分为多个段落"""
        turns = [
            _make_turn(1, tool_narrative="RESTRICTED/规格/R14_知识库权限管理系统/design.md"),
            _make_turn(2, tool_narrative="RESTRICTED/规格/R14_知识库权限管理系统/tasks.md"),
            _make_turn(3, tool_narrative="RESTRICTED/规格/R15_英联股份AI应用子公司设立构想计划/requirements.md"),
            _make_turn(4, user_prompt="Continue working on 英联股份AI应用子公司 plan"),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        self.assertEqual(len(segments), 2)

        entity1, turns1 = segments[0]
        self.assertEqual(entity1.entity_id, self.r14.entity_id)
        self.assertEqual(len(turns1), 2)

        entity2, turns2 = segments[1]
        self.assertEqual(entity2.entity_id, self.r15.entity_id)
        self.assertEqual(len(turns2), 2)

    def test_none_turns_absorbed_into_preceding(self):
        """未分类轮次吸收到前面的已分类段落"""
        turns = [
            _make_turn(1, tool_narrative="RESTRICTED/规格/R14_知识库权限管理系统/design.md"),
            _make_turn(2),  # no entity signals
            _make_turn(3, tool_narrative="RESTRICTED/规格/R15_英联股份AI应用子公司设立构想计划/requirements.md"),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        self.assertEqual(len(segments), 2)

        entity1, turns1 = segments[0]
        self.assertEqual(entity1.entity_id, self.r14.entity_id)
        self.assertEqual(len(turns1), 2)  # turn 1 + absorbed turn 2

        entity2, turns2 = segments[1]
        self.assertEqual(entity2.entity_id, self.r15.entity_id)
        self.assertEqual(len(turns2), 1)

    def test_leading_none_turns_absorbed_into_following(self):
        """开头的未分类轮次吸收到后面的已分类段落"""
        turns = [
            _make_turn(1),  # no entity signals
            _make_turn(2),  # no entity signals
            _make_turn(3, tool_narrative="RESTRICTED/规格/R15_英联股份AI应用子公司设立构想计划/requirements.md"),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        self.assertEqual(len(segments), 1)

        entity, seg_turns = segments[0]
        self.assertEqual(entity.entity_id, self.r15.entity_id)
        self.assertEqual(len(seg_turns), 3)

    def test_all_none_turns(self):
        """全部未分类 → 单个 None 段落"""
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
        """空轮次列表"""
        segments = self.classifier.classify_turns([], self.entities)
        self.assertEqual(len(segments), 0)

    def test_text_pattern_matching(self):
        """通过文本模式匹配实体"""
        turns = [
            _make_turn(1, user_prompt="Let's work on Spec R14"),
            _make_turn(2, assistant_response="I'll update the 知识库权限管理 system"),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        self.assertEqual(len(segments), 1)
        entity, _ = segments[0]
        self.assertEqual(entity.entity_id, self.r14.entity_id)

    def test_path_pattern_takes_priority(self):
        """路径模式优先于文本模式"""
        turns = [
            _make_turn(
                1,
                tool_narrative="RESTRICTED/规格/R14_知识库权限管理系统/design.md",
                user_prompt="Spec R15 related text",  # text says R15 but path says R14
            ),
        ]
        segments = self.classifier.classify_turns(turns, self.entities)
        entity, _ = segments[0]
        self.assertEqual(entity.entity_id, self.r14.entity_id)

    def test_only_spec_entities_participate(self):
        """非 SPEC 类型实体不参与轮次拆分"""
        source_entity = Entity(
            entity_type=EntityType.SOURCE,
            name="doc_indexer",
            display_name="源代码: doc_indexer",
            directory="源代码/doc_indexer",
            path_patterns=["源代码/doc_indexer/"],
            text_patterns=[r"源代码/doc_indexer"],
        )
        turns = [
            _make_turn(1, tool_narrative="源代码/doc_indexer/cli.py"),
        ]
        # With only non-spec entities, all turns are unclassified
        segments = self.classifier.classify_turns(turns, [source_entity])
        self.assertEqual(len(segments), 1)
        entity, _ = segments[0]
        self.assertIsNone(entity)


if __name__ == "__main__":
    unittest.main()
