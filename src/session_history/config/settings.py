"""Settings - configuration management"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


CONFIG_FILENAME = ".session-history.json"


@dataclass
class Settings:
    """Global settings with auto-detection and optional JSON config override."""

    # Auto-detected from module location (4 levels up: config/ -> session_history/ -> src/ -> project_root/)
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)

    # Auto-computed from project_root (see __post_init__)
    sessions_dir: Path = field(default=None)

    # Session history output root directory name
    history_root: str = "session-history"

    # Classification threshold
    classification_threshold: float = 0.15

    # Signal weights
    signal_weights: Dict[str, float] = field(default_factory=lambda: {
        "file_path": 0.50,
        "text_pattern": 0.35,
        "keyword": 0.15,
    })

    # Exclude thinking blocks
    exclude_thinking: bool = True

    # Exclude sidechain messages
    exclude_sidechains: bool = True

    # Incremental scan state file
    scan_state_file: str = ".scan-state.json"

    # Entity directory mapping (logical name -> actual directory name)
    entity_dirs: Dict[str, str] = field(default_factory=lambda: {
        "spec": "specs",
        "source": "src",
        "research": "research",
        "knowledge": "docs",
        "tool": "scripts",
    })

    # Spec naming pattern (regex with groups: group(1)=number, group(2)=description)
    spec_pattern: str = r"(\d+)_(.+)"

    # Format string for spec display name ({num} and {desc} are substituted)
    spec_display: str = "Spec {num}: {desc}"

    # Optional restricted spec directory (relative to project_root), e.g. "RESTRICTED/specs"
    restricted_spec_dir: Optional[str] = None

    # Legacy aliases: current_name -> [old_name, ...]
    legacy_aliases: Dict[str, List[str]] = field(default_factory=dict)

    # Per entity-type skip lists (files/dirs to skip during discovery)
    skip_files: Dict[str, List[str]] = field(default_factory=lambda: {
        "spec": ["00_template"],
    })

    def __post_init__(self):
        # Auto-compute sessions_dir from project_root if not set
        if self.sessions_dir is None:
            self.sessions_dir = self._compute_sessions_dir()

        # Load config overrides from .session-history.json if present
        config_path = self.project_root / CONFIG_FILENAME
        if config_path.exists():
            self._load_config(config_path)

    def _compute_sessions_dir(self) -> Path:
        """Compute Claude Code sessions directory from project_root.

        Claude stores sessions at ~/.claude/projects/-<path-with-dashes>/
        e.g. /Users/kweng/AI/base -> ~/.claude/projects/-Users-kweng-AI-base/
        """
        # Convert absolute path to dash-separated format
        # Claude Code replaces both / and _ with - in the mangled path
        path_str = str(self.project_root)
        if path_str.startswith("/"):
            path_str = path_str[1:]  # Remove leading /
        mangled = "-" + path_str.replace("/", "-").replace("_", "-")
        return Path.home() / ".claude" / "projects" / mangled

    def _load_config(self, config_path: Path):
        """Load and merge config from JSON file."""
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        if "entity_dirs" in config:
            self.entity_dirs = config["entity_dirs"]
        if "history_root" in config:
            self.history_root = config["history_root"]
        if "spec_pattern" in config:
            self.spec_pattern = config["spec_pattern"]
        if "spec_display" in config:
            self.spec_display = config["spec_display"]
        if "restricted_spec_dir" in config:
            self.restricted_spec_dir = config["restricted_spec_dir"]
        if "legacy_aliases" in config:
            self.legacy_aliases = config["legacy_aliases"]
        if "skip_files" in config:
            self.skip_files = config["skip_files"]
        if "classification_threshold" in config:
            self.classification_threshold = config["classification_threshold"]
        if "signal_weights" in config:
            self.signal_weights = config["signal_weights"]
        if "sessions_dir" in config:
            self.sessions_dir = Path(config["sessions_dir"])

    @property
    def history_dir(self) -> Path:
        return self.project_root / self.history_root

    @property
    def scan_state_path(self) -> Path:
        return self.history_dir / self.scan_state_file
