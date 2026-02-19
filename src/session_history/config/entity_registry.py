"""Entity Registry - 自动发现项目实体

Supports multiple directory naming conventions so the same tool works
across projects without per-project configuration:

  Specs:      规格/, spec/, specs/, RESTRICTED/规格/
  Source:     源代码/, src/, extensions/
  Research:   研究/, research/
  Knowledge:  知识库/, knowledge/, docs/
  Tools:      工具/, tools/

Numbering patterns: P##_name, R##_name, ##_name (plain number prefix)
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..models.category import Entity, EntityType


# Directory name alternatives for each entity type.
# First existing match wins per type; all are scanned for specs.
_SPEC_DIRS = ["规格", "spec", "specs"]
_SPEC_RESTRICTED_PARENTS = ["RESTRICTED"]
_SOURCE_DIRS = ["源代码", "src", "extensions"]
_RESEARCH_DIRS = ["研究", "research"]
_KNOWLEDGE_DIRS = ["知识库", "knowledge", "docs"]
_TOOL_DIRS = ["工具", "tools"]

# Directories to skip when scanning
_SKIP_NAMES = {
    "README.md", "session_history", "__pycache__", ".git",
    "node_modules", "dist", "build", ".DS_Store",
    "00_template", "00_project-template.md",
}

# Spec numbering patterns: P##_name, R##_name, or plain ##_name
_SPEC_NUMBER_RE = re.compile(r"^([PR]?\d+)_(.+)$")


class EntityRegistry:
    """自动从项目目录结构发现实体"""

    # Legacy directory names from Enpack-CCC project (before P##/R## renumbering).
    # Used to match old references in JSONL session data. Projects that don't
    # have these names simply ignore them — no harm.
    LEGACY_ALIASES: Dict[str, List[str]] = {
        "P01_文档管理系统": ["01_文档管理系统"],
        "P02_电池材料关键绩效指标研究": ["01_电池材料关键绩效指标研究"],
        "P03_聊天会话持久化": ["01_聊天会话持久化"],
        "P04_AI机会研究": ["02_AI机会研究"],
        "P05_复合箔制造研究": ["03_复合箔制造研究"],
        "P06_定价利润分析": ["03_定价利润分析"],
        "P07_电池集流体技术标准": ["04_电池集流体技术标准"],
        "P08_复合集流体公司档案研究": ["05_复合集流体公司档案研究"],
        "P09_技术路线图固态电池": ["06_技术路线图固态电池"],
        "P10_内容本地化策略": ["07_内容本地化策略"],
        "P11_实验数据分析建模系统": ["08_实验数据分析建模系统"],
        "P12_内部数据收集系统": ["09_内部数据收集系统"],
        "P13_大文档分块处理系统": ["10_大文档分块处理系统"],
        "R14_知识库权限管理系统": ["11_知识库权限管理系统"],
        "R15_英联股份AI应用子公司设立构想计划": ["12_英联股份AI应用子公司设立构想计划"],
        "P16_会话历史分类系统": ["11_会话历史分类系统"],
    }

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def discover_all(self) -> List[Entity]:
        """发现所有实体"""
        entities: List[Entity] = []
        specs = self._discover_specs()
        sources = self._discover_sources()
        entities.extend(specs)
        entities.extend(sources)
        entities.extend(self._discover_research())
        entities.extend(self._discover_knowledge())
        entities.extend(self._discover_tools())

        # Cross-reference: link spec entities to related source directories
        # so turn-level classification can match implementation code to specs
        self._link_specs_to_sources(specs, sources)

        return entities

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_existing_dirs(self, candidates: List[str]) -> List[Path]:
        """Return all candidate directories that actually exist."""
        found = []
        for name in candidates:
            d = self.project_root / name
            if d.is_dir():
                found.append(d)
        return found

    def _find_first_existing_dir(self, candidates: List[str]) -> Optional[Path]:
        """Return the first candidate directory that exists, or None."""
        for name in candidates:
            d = self.project_root / name
            if d.is_dir():
                return d
        return None

    @staticmethod
    def _parse_spec_number(dirname: str) -> Optional[Tuple[str, str]]:
        """Parse a spec directory name into (number, description).

        Supports: P01_name, R14_name, 02_name
        Returns None if the name doesn't match.
        """
        m = _SPEC_NUMBER_RE.match(dirname)
        if m:
            return m.group(1), m.group(2)
        return None

    @staticmethod
    def _should_skip(name: str) -> bool:
        return name in _SKIP_NAMES or name.startswith(".")

    @staticmethod
    def _link_specs_to_sources(
        specs: List[Entity], sources: List[Entity],
    ) -> None:
        """Add source path/text patterns to specs whose keywords overlap.

        When a source directory name appears in a spec's keywords, the
        source's implementation paths are added to the spec entity.  This
        lets the turn-level classifier match implementation code (e.g.
        ``extensions/wechat/``) to its spec (e.g. ``spec/02_wechat-channel``).
        """
        kw_lower: Dict[str, set] = {}
        for spec in specs:
            kw_lower[spec.entity_id] = {k.lower() for k in spec.keywords}

        for source in sources:
            source_name_lower = source.name.lower()
            for spec in specs:
                if source_name_lower in kw_lower[spec.entity_id]:
                    for pp in source.path_patterns:
                        if pp not in spec.path_patterns:
                            spec.path_patterns.append(pp)
                    for tp in source.text_patterns:
                        if tp not in spec.text_patterns:
                            spec.text_patterns.append(tp)

    # ------------------------------------------------------------------
    # Entity type discovery
    # ------------------------------------------------------------------

    def _discover_specs(self) -> List[Entity]:
        """Discover spec entities from all spec directory conventions."""
        entities: List[Entity] = []

        # Collect all spec directories (main + restricted)
        spec_dirs: List[Path] = []
        for name in _SPEC_DIRS:
            d = self.project_root / name
            if d.is_dir():
                spec_dirs.append(d)
            for parent in _SPEC_RESTRICTED_PARENTS:
                rd = self.project_root / parent / name
                if rd.is_dir():
                    spec_dirs.append(rd)

        for specs_dir in spec_dirs:
            parent_rel = str(specs_dir.relative_to(self.project_root))

            for d in sorted(specs_dir.iterdir()):
                if not d.is_dir() or self._should_skip(d.name):
                    continue

                parsed = self._parse_spec_number(d.name)
                if not parsed:
                    continue

                num, desc = parsed
                # Normalize: strip P/R prefix for display number
                display_num = num.lstrip("PR") if num[0] in "PR" else num
                rel_dir = str(d.relative_to(self.project_root))

                # Build keywords from directory name parts
                keywords = [
                    d.name, desc,
                    f"spec {num}", f"spec #{num}", f"Spec {num}", f"Spec #{num}",
                    f"spec {display_num}", f"spec #{display_num}",
                    f"{parent_rel}/{d.name}",
                ]
                for part in re.split(r"[_\-]", desc):
                    if part:
                        keywords.append(part)

                path_patterns = [f"{rel_dir}/", rel_dir]
                text_patterns = [
                    rf"[Ss]pec\s*#?{re.escape(num)}\b",
                    rf"[Ss]pec\s*#?{re.escape(display_num)}\b",
                    rf"{re.escape(parent_rel)}/{re.escape(d.name)}",
                ]

                # Add legacy aliases (Enpack-CCC backward compat)
                for old_name in self.LEGACY_ALIASES.get(d.name, []):
                    old_match = re.match(r"(\d+)_(.+)", old_name)
                    if old_match:
                        old_num = old_match.group(1)
                        keywords.extend([
                            old_name,
                            f"spec {old_num}", f"spec #{old_num}",
                        ])
                        path_patterns.extend([
                            f"规格/{old_name}/",
                            f"规格/{old_name}",
                        ])
                        text_patterns.extend([
                            rf"[Ss]pec\s*#?{old_num}\b",
                            rf"规格/{re.escape(old_name)}",
                        ])

                entities.append(Entity(
                    entity_type=EntityType.SPEC,
                    name=d.name,
                    display_name=f"Spec {display_num}: {desc}",
                    directory=rel_dir,
                    keywords=keywords,
                    path_patterns=path_patterns,
                    text_patterns=text_patterns,
                ))

        return entities

    def _discover_sources(self) -> List[Entity]:
        """Discover source code entities."""
        entities: List[Entity] = []
        skip = _SKIP_NAMES | {"session_history", "plugin-sdk"}

        for src_dir in self._find_existing_dirs(_SOURCE_DIRS):
            parent_rel = str(src_dir.relative_to(self.project_root))

            for d in sorted(src_dir.iterdir()):
                if not d.is_dir() or d.name in skip or d.name.startswith("."):
                    continue

                name = d.name
                rel_dir = f"{parent_rel}/{name}"
                keywords = [name]
                for part in re.split(r"[-_]", name):
                    if part and len(part) > 2:
                        keywords.append(part)

                entities.append(Entity(
                    entity_type=EntityType.SOURCE,
                    name=name,
                    display_name=f"Source: {name}",
                    directory=rel_dir,
                    keywords=keywords,
                    path_patterns=[f"{rel_dir}/", rel_dir],
                    text_patterns=[rf"{re.escape(rel_dir)}"],
                ))

        return entities

    def _discover_research(self) -> List[Entity]:
        """Discover research topic entities."""
        entities: List[Entity] = []
        skip = _SKIP_NAMES | {"研究说明-EN.md", "指南"}

        for res_dir in self._find_existing_dirs(_RESEARCH_DIRS):
            parent_rel = str(res_dir.relative_to(self.project_root))

            for d in sorted(res_dir.iterdir()):
                if not d.is_dir() or d.name in skip or d.name.startswith("."):
                    continue

                name = d.name
                rel_dir = f"{parent_rel}/{name}"
                keywords = [name]
                for part in re.split(r"[-_]", name):
                    if part and len(part) > 1:
                        keywords.append(part)

                entities.append(Entity(
                    entity_type=EntityType.RESEARCH,
                    name=name,
                    display_name=f"Research: {name}",
                    directory=rel_dir,
                    keywords=keywords,
                    path_patterns=[f"{rel_dir}/", rel_dir],
                    text_patterns=[rf"{re.escape(rel_dir)}"],
                ))

        return entities

    def _discover_knowledge(self) -> List[Entity]:
        """Discover knowledge base entities."""
        entities: List[Entity] = []
        skip = _SKIP_NAMES | {"知识库导航索引.md", "数据收集指南.md", "战略重点-EN.md"}

        for kb_dir in self._find_existing_dirs(_KNOWLEDGE_DIRS):
            parent_rel = str(kb_dir.relative_to(self.project_root))

            for d in sorted(kb_dir.iterdir()):
                if not d.is_dir() or d.name in skip or d.name.startswith("."):
                    continue

                name = d.name
                rel_dir = f"{parent_rel}/{name}"
                keywords = [name]
                parsed = self._parse_spec_number(name)
                if parsed:
                    for part in re.split(r"[-_]", parsed[1]):
                        if part:
                            keywords.append(part)

                entities.append(Entity(
                    entity_type=EntityType.KNOWLEDGE,
                    name=name,
                    display_name=f"Knowledge: {name}",
                    directory=rel_dir,
                    keywords=keywords,
                    path_patterns=[f"{rel_dir}/", rel_dir],
                    text_patterns=[rf"{re.escape(rel_dir)}"],
                ))

        return entities

    def _discover_tools(self) -> List[Entity]:
        """Discover tool entities."""
        entities: List[Entity] = []

        for tools_dir in self._find_existing_dirs(_TOOL_DIRS):
            parent_rel = str(tools_dir.relative_to(self.project_root))
            entities.append(Entity(
                entity_type=EntityType.TOOL,
                name=parent_rel,
                display_name=f"Tools: {parent_rel}",
                directory=parent_rel,
                keywords=[parent_rel, "tool", "tools"],
                path_patterns=[f"{parent_rel}/"],
                text_patterns=[rf"{re.escape(parent_rel)}/"],
            ))

        return entities
