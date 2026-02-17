"""Composite Classifier - 组合多个信号进行会话分类"""

from typing import Dict, List

from ..config.settings import Settings
from ..models.category import Entity, EntityMatch, SessionClassification
from ..models.index import MessagePointer, SessionReference
from ..models.session import Session
from .file_path_signal import FilePathSignal
from .text_pattern_signal import TextPatternSignal
from .keyword_signal import KeywordSignal


class CompositeClassifier:
    """组合文件路径、文本模式和关键词信号进行分类"""

    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        self.file_path_signal = FilePathSignal()
        self.text_pattern_signal = TextPatternSignal()
        self.keyword_signal = KeywordSignal()

    def classify(self, session: Session, entities: List[Entity]) -> SessionClassification:
        """分类一个会话"""
        classification = SessionClassification(
            session_id=session.session_id,
            file_path=session.file_path,
            start_time=session.start_time,
            end_time=session.end_time,
            message_count=session.message_count,
            user_message_count=session.user_message_count,
        )

        messages = session.messages
        weights = self.settings.signal_weights
        threshold = self.settings.classification_threshold

        for entity in entities:
            # 计算各信号分数
            fp_score = self.file_path_signal.score(messages, entity)
            tp_score = self.text_pattern_signal.score(messages, entity)
            kw_score = self.keyword_signal.score(messages, entity)

            # 加权组合
            confidence = (
                fp_score * weights["file_path"]
                + tp_score * weights["text_pattern"]
                + kw_score * weights["keyword"]
            )

            if confidence >= threshold:
                # 收集匹配的消息
                matched_msgs = set()
                matched_msgs.update(
                    m.uuid for m in self.file_path_signal.matched_messages(messages, entity)
                )
                matched_msgs.update(
                    m.uuid for m in self.text_pattern_signal.matched_messages(messages, entity)
                )

                # 收集证据
                evidence = self._collect_evidence(messages, entity)

                match = EntityMatch(
                    entity=entity,
                    confidence=confidence,
                    file_path_score=fp_score,
                    text_pattern_score=tp_score,
                    keyword_score=kw_score,
                    matched_messages=len(matched_msgs),
                    total_messages=len(messages),
                    evidence=evidence,
                )
                classification.matches.append(match)

        # 按置信度排序
        classification.matches.sort(key=lambda m: m.confidence, reverse=True)
        return classification

    def build_session_reference(
        self, session: Session, entity_match: EntityMatch
    ) -> SessionReference:
        """为实体构建会话引用"""
        entity = entity_match.entity
        messages = session.messages

        # 收集匹配的消息指针
        matched = set()
        for msg in self.file_path_signal.matched_messages(messages, entity):
            matched.add(msg.uuid)
        for msg in self.text_pattern_signal.matched_messages(messages, entity):
            matched.add(msg.uuid)

        pointers = []
        for msg in messages:
            if msg.uuid in matched:
                preview = msg.text_content[:100] if msg.text_content else ""
                pointers.append(MessagePointer(
                    uuid=msg.uuid,
                    line_number=msg.line_number,
                    msg_type=msg.role or msg.msg_type,
                    timestamp=msg.timestamp,
                    preview=preview,
                ))

        return SessionReference(
            session_id=session.session_id,
            file_path=session.file_path,
            confidence=entity_match.confidence,
            start_time=session.start_time,
            end_time=session.end_time,
            message_count=session.message_count,
            matched_messages=pointers,
            evidence=entity_match.evidence,
        )

    def _collect_evidence(
        self, messages: List, entity: Entity, max_items: int = 5
    ) -> List[str]:
        """收集分类证据"""
        evidence = []

        # 文件路径证据
        for msg in self.file_path_signal.matched_messages(messages, entity):
            paths = msg.file_paths
            for p in paths:
                for pattern in entity.path_patterns:
                    if pattern.rstrip("/") in p:
                        evidence.append(f"File: {p}")
                        break
            if len(evidence) >= max_items:
                break

        # 文本模式证据
        for msg in self.text_pattern_signal.matched_messages(messages, entity):
            text = msg.text_content
            if text:
                preview = text[:80].replace("\n", " ")
                evidence.append(f"Text: ...{preview}...")
            if len(evidence) >= max_items:
                break

        return evidence[:max_items]
