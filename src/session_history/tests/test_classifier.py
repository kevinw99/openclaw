"""Tests for classifier"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from session_history.parser.jsonl_reader import JsonlReader
from session_history.classifier.composite_classifier import CompositeClassifier
from session_history.classifier.file_path_signal import FilePathSignal
from session_history.classifier.text_pattern_signal import TextPatternSignal
from session_history.classifier.keyword_signal import KeywordSignal
from session_history.models.category import Entity, EntityType
from session_history.config.settings import Settings

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_SESSION = str(FIXTURE_DIR / "sample_session.jsonl")


def _make_spec_p12_entity():
    return Entity(
        entity_type=EntityType.SPEC,
        name="P12_内部数据收集系统",
        display_name="Spec P12: 内部数据收集系统",
        directory="规格/P12_内部数据收集系统",
        keywords=["P12_内部数据收集系统", "内部数据收集系统", "内部数据收集", "spec P12", "spec #P12"],
        path_patterns=["规格/P12_内部数据收集系统/", "规格/P12_内部数据收集系统"],
        text_patterns=[r"[Ss]pec\s*#?P12\b", r"规格/P12_内部数据收集系统", r"规格.*P12"],
    )


def _make_chunked_entity():
    return Entity(
        entity_type=EntityType.SOURCE,
        name="chunked_processor",
        display_name="源代码: chunked_processor",
        directory="源代码/chunked_processor",
        keywords=["chunked_processor", "chunked", "processor"],
        path_patterns=["源代码/chunked_processor/", "源代码/chunked_processor"],
        text_patterns=[r"源代码/chunked_processor"],
    )


def _make_unrelated_entity():
    return Entity(
        entity_type=EntityType.RESEARCH,
        name="定价分析",
        display_name="研究: 定价分析",
        directory="研究/定价分析",
        keywords=["定价分析", "定价", "pricing"],
        path_patterns=["研究/定价分析/"],
        text_patterns=[r"研究/定价分析"],
    )


def test_file_path_signal_matches():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)
    signal = FilePathSignal()

    spec09 = _make_spec_p12_entity()
    score = signal.score(session.messages, spec09)
    assert score > 0, f"Expected positive score for spec P12, got {score}"


def test_file_path_signal_no_match():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)
    signal = FilePathSignal()

    unrelated = _make_unrelated_entity()
    score = signal.score(session.messages, unrelated)
    assert score == 0.0, f"Expected 0 for unrelated entity, got {score}"


def test_text_pattern_signal():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)
    signal = TextPatternSignal()

    spec09 = _make_spec_p12_entity()
    score = signal.score(session.messages, spec09)
    assert score > 0, f"Expected positive text pattern score for spec P12, got {score}"


def test_keyword_signal():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)
    signal = KeywordSignal()

    chunked = _make_chunked_entity()
    score = signal.score(session.messages, chunked)
    assert score > 0, f"Expected positive keyword score for chunked_processor, got {score}"


def test_composite_classifier():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    entities = [_make_spec_p12_entity(), _make_chunked_entity(), _make_unrelated_entity()]
    classifier = CompositeClassifier()
    classification = classifier.classify(session, entities)

    # 应该匹配 spec P12 和 chunked_processor, 不匹配定价分析
    matched_ids = {m.entity.entity_id for m in classification.matches}
    assert "spec:P12_内部数据收集系统" in matched_ids, f"Expected spec P12 match, got {matched_ids}"
    assert "source:chunked_processor" in matched_ids, f"Expected chunked match, got {matched_ids}"
    assert "research:定价分析" not in matched_ids, f"Should not match 定价分析"


def test_classification_ordering():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    entities = [_make_spec_p12_entity(), _make_chunked_entity()]
    classifier = CompositeClassifier()
    classification = classifier.classify(session, entities)

    # 结果应按置信度降序排列
    if len(classification.matches) >= 2:
        assert classification.matches[0].confidence >= classification.matches[1].confidence


def test_session_reference_building():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    entities = [_make_spec_p12_entity()]
    classifier = CompositeClassifier()
    classification = classifier.classify(session, entities)

    if classification.matches:
        ref = classifier.build_session_reference(session, classification.matches[0])
        assert ref.session_id == session.session_id
        assert ref.confidence > 0
        assert len(ref.matched_messages) > 0


if __name__ == "__main__":
    test_file_path_signal_matches()
    test_file_path_signal_no_match()
    test_text_pattern_signal()
    test_keyword_signal()
    test_composite_classifier()
    test_classification_ordering()
    test_session_reference_building()
    print("All classifier tests passed!")
