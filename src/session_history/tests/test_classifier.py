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


def _make_test_settings():
    """Create settings pointing at the test project root."""
    s = Settings.__new__(Settings)
    s.project_root = Path("/Users/testuser/AI/base")
    s.sessions_dir = Path("/tmp/sessions")
    s.history_root = "session-history"
    s.classification_threshold = 0.15
    s.signal_weights = {"file_path": 0.50, "text_pattern": 0.35, "keyword": 0.15}
    s.exclude_thinking = True
    s.exclude_sidechains = True
    s.scan_state_file = ".scan-state.json"
    s.entity_dirs = {"spec": "specs", "source": "src", "research": "research", "knowledge": "docs", "tool": "scripts"}
    s.spec_pattern = r"(\d+)_(.+)"
    s.spec_display = "Spec {num}: {desc}"
    s.restricted_spec_dir = None
    s.legacy_aliases = {}
    s.skip_files = {}
    return s


def _make_spec_01_entity():
    return Entity(
        entity_type=EntityType.SPEC,
        name="01_data-pipeline",
        display_name="Spec 01: data-pipeline",
        directory="specs/01_data-pipeline",
        keywords=["01_data-pipeline", "data-pipeline", "data", "pipeline", "spec 01", "spec #01"],
        path_patterns=["specs/01_data-pipeline/", "specs/01_data-pipeline"],
        text_patterns=[r"[Ss]pec\s*#?01\b", r"specs/01_data-pipeline", r"specs.*01"],
    )


def _make_source_entity():
    return Entity(
        entity_type=EntityType.SOURCE,
        name="data_processor",
        display_name="src: data_processor",
        directory="src/data_processor",
        keywords=["data_processor", "data", "processor"],
        path_patterns=["src/data_processor/", "src/data_processor"],
        text_patterns=[r"src/data_processor"],
    )


def _make_unrelated_entity():
    return Entity(
        entity_type=EntityType.RESEARCH,
        name="pricing-analysis",
        display_name="research: pricing-analysis",
        directory="research/pricing-analysis",
        keywords=["pricing-analysis", "pricing", "analysis"],
        path_patterns=["research/pricing-analysis/"],
        text_patterns=[r"research/pricing-analysis"],
    )


def test_file_path_signal_matches():
    settings = _make_test_settings()
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)
    signal = FilePathSignal(settings=settings)

    spec01 = _make_spec_01_entity()
    score = signal.score(session.messages, spec01)
    assert score > 0, f"Expected positive score for spec 01, got {score}"


def test_file_path_signal_no_match():
    settings = _make_test_settings()
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)
    signal = FilePathSignal(settings=settings)

    unrelated = _make_unrelated_entity()
    score = signal.score(session.messages, unrelated)
    assert score == 0.0, f"Expected 0 for unrelated entity, got {score}"


def test_text_pattern_signal():
    settings = _make_test_settings()
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)
    signal = TextPatternSignal(settings=settings)

    spec01 = _make_spec_01_entity()
    score = signal.score(session.messages, spec01)
    assert score > 0, f"Expected positive text pattern score for spec 01, got {score}"


def test_keyword_signal():
    settings = _make_test_settings()
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)
    signal = KeywordSignal(settings=settings)

    source = _make_source_entity()
    score = signal.score(session.messages, source)
    assert score > 0, f"Expected positive keyword score for data_processor, got {score}"


def test_composite_classifier():
    settings = _make_test_settings()
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    entities = [_make_spec_01_entity(), _make_source_entity(), _make_unrelated_entity()]
    classifier = CompositeClassifier(settings)
    classification = classifier.classify(session, entities)

    matched_ids = {m.entity.entity_id for m in classification.matches}
    assert "spec:01_data-pipeline" in matched_ids, f"Expected spec 01 match, got {matched_ids}"
    assert "source:data_processor" in matched_ids, f"Expected data_processor match, got {matched_ids}"
    assert "research:pricing-analysis" not in matched_ids, f"Should not match pricing-analysis"


def test_classification_ordering():
    settings = _make_test_settings()
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    entities = [_make_spec_01_entity(), _make_source_entity()]
    classifier = CompositeClassifier(settings)
    classification = classifier.classify(session, entities)

    if len(classification.matches) >= 2:
        assert classification.matches[0].confidence >= classification.matches[1].confidence


def test_session_reference_building():
    settings = _make_test_settings()
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    entities = [_make_spec_01_entity()]
    classifier = CompositeClassifier(settings)
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
