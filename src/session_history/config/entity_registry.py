"""Entity Registry - auto-discover project entities from directory structure"""

import re
from pathlib import Path
from typing import List

from ..models.category import Entity, EntityType
from .settings import Settings


class EntityRegistry:
    """Auto-discover entities from project directory structure, driven by Settings."""

    def __init__(self, project_root: Path, settings: Settings = None):
        self.project_root = project_root
        self.settings = settings or Settings()

    def discover_all(self) -> List[Entity]:
        """Discover all entities."""
        entities = []
        entities.extend(self._discover_specs())
        entities.extend(self._discover_sources())
        entities.extend(self._discover_research())
        entities.extend(self._discover_knowledge())
        entities.extend(self._discover_tools())
        return entities

    def _discover_specs(self) -> List[Entity]:
        """Discover spec entities from configured spec directories."""
        entities = []
        spec_dir_name = self.settings.entity_dirs.get("spec", "specs")
        skip_list = set(self.settings.skip_files.get("spec", []))

        # Build list of spec directories to scan
        spec_dirs = [self.project_root / spec_dir_name]
        if self.settings.restricted_spec_dir:
            spec_dirs.append(self.project_root / self.settings.restricted_spec_dir)

        for specs_dir in spec_dirs:
            if not specs_dir.exists():
                continue
            for d in sorted(specs_dir.iterdir()):
                if not d.is_dir():
                    continue
                name = d.name
                if name in skip_list:
                    continue

                match = re.match(self.settings.spec_pattern, name)
                if match:
                    num = match.group(1)
                    desc = match.group(2)
                    rel_dir = str(d.relative_to(self.project_root))
                    display = self.settings.spec_display.format(num=num, desc=desc)

                    keywords = [
                        name, desc,
                        f"spec {num}", f"spec #{num}", f"Spec {num}", f"Spec #{num}",
                        f"{spec_dir_name}/{name}",
                        f"project {num}", f"project #{num}",
                    ]
                    # Split description into keyword parts
                    for part in re.split(r"[_\-]", desc):
                        if part:
                            keywords.append(part)

                    path_patterns = [
                        f"{rel_dir}/",
                        f"{rel_dir}",
                    ]
                    text_patterns = [
                        rf"[Ss]pec\s*#?{re.escape(num)}\b",
                        rf"{re.escape(spec_dir_name)}/{re.escape(name)}",
                        rf"{re.escape(spec_dir_name)}.*{re.escape(num)}",
                        rf"project\s*#?{re.escape(num)}\b",
                    ]

                    # Add legacy aliases for old directory names
                    for old_name in self.settings.legacy_aliases.get(name, []):
                        old_match = re.match(r"(\d+)_(.+)", old_name)
                        if old_match:
                            old_num = old_match.group(1)
                            keywords.extend([
                                old_name,
                                f"spec {old_num}", f"spec #{old_num}",
                                f"Spec {old_num}", f"Spec #{old_num}",
                            ])
                            path_patterns.extend([
                                f"{spec_dir_name}/{old_name}/",
                                f"{spec_dir_name}/{old_name}",
                            ])
                            text_patterns.extend([
                                rf"[Ss]pec\s*#?{old_num}\b",
                                rf"{re.escape(spec_dir_name)}/{re.escape(old_name)}",
                                rf"{re.escape(spec_dir_name)}.*{re.escape(old_num)}",
                            ])

                    entities.append(Entity(
                        entity_type=EntityType.SPEC,
                        name=name,
                        display_name=display,
                        directory=rel_dir,
                        keywords=keywords,
                        path_patterns=path_patterns,
                        text_patterns=text_patterns,
                    ))
        return entities

    def _discover_sources(self) -> List[Entity]:
        """Discover source code project entities."""
        src_dir_name = self.settings.entity_dirs.get("source", "src")
        src_dir = self.project_root / src_dir_name
        if not src_dir.exists():
            return []

        entities = []
        skip = {"README.md", "session_history", "__pycache__"}
        skip.update(self.settings.skip_files.get("source", []))

        for d in sorted(src_dir.iterdir()):
            if not d.is_dir() or d.name in skip or d.name.startswith("."):
                continue
            name = d.name
            keywords = [name]
            for part in re.split(r"[-_]", name):
                if part and len(part) > 2:
                    keywords.append(part)

            entities.append(Entity(
                entity_type=EntityType.SOURCE,
                name=name,
                display_name=f"{src_dir_name}: {name}",
                directory=f"{src_dir_name}/{name}",
                keywords=keywords,
                path_patterns=[
                    f"{src_dir_name}/{name}/",
                    f"{src_dir_name}/{name}",
                ],
                text_patterns=[
                    rf"{re.escape(src_dir_name)}/{re.escape(name)}",
                ],
            ))
        return entities

    def _discover_research(self) -> List[Entity]:
        """Discover research topic entities."""
        res_dir_name = self.settings.entity_dirs.get("research", "research")
        res_dir = self.project_root / res_dir_name
        if not res_dir.exists():
            return []

        entities = []
        skip = {"__pycache__"}
        skip.update(self.settings.skip_files.get("research", []))

        for d in sorted(res_dir.iterdir()):
            if not d.is_dir() or d.name in skip or d.name.startswith("."):
                continue
            name = d.name
            keywords = [name]
            for part in re.split(r"[-_]", name):
                if part and len(part) > 1:
                    keywords.append(part)

            entities.append(Entity(
                entity_type=EntityType.RESEARCH,
                name=name,
                display_name=f"{res_dir_name}: {name}",
                directory=f"{res_dir_name}/{name}",
                keywords=keywords,
                path_patterns=[f"{res_dir_name}/{name}/", f"{res_dir_name}/{name}"],
                text_patterns=[rf"{re.escape(res_dir_name)}/{re.escape(name)}"],
            ))
        return entities

    def _discover_knowledge(self) -> List[Entity]:
        """Discover knowledge base entities."""
        kb_dir_name = self.settings.entity_dirs.get("knowledge", "docs")
        kb_dir = self.project_root / kb_dir_name
        if not kb_dir.exists():
            return []

        entities = []
        skip = {"__pycache__"}
        skip.update(self.settings.skip_files.get("knowledge", []))

        for d in sorted(kb_dir.iterdir()):
            if not d.is_dir() or d.name in skip or d.name.startswith("."):
                continue
            name = d.name
            keywords = [name]
            match = re.match(r"(\d+)_(.+)", name)
            if match:
                for part in re.split(r"[-_]", match.group(2)):
                    if part:
                        keywords.append(part)

            entities.append(Entity(
                entity_type=EntityType.KNOWLEDGE,
                name=name,
                display_name=f"{kb_dir_name}: {name}",
                directory=f"{kb_dir_name}/{name}",
                keywords=keywords,
                path_patterns=[f"{kb_dir_name}/{name}/", f"{kb_dir_name}/{name}"],
                text_patterns=[rf"{re.escape(kb_dir_name)}/{re.escape(name)}"],
            ))
        return entities

    def _discover_tools(self) -> List[Entity]:
        """Discover tool entities."""
        tools_dir_name = self.settings.entity_dirs.get("tool", "scripts")
        tools_dir = self.project_root / tools_dir_name
        if not tools_dir.exists():
            return []

        return [Entity(
            entity_type=EntityType.TOOL,
            name=tools_dir_name,
            display_name=tools_dir_name,
            directory=tools_dir_name,
            keywords=[tools_dir_name, "tool", "script"],
            path_patterns=[f"{tools_dir_name}/"],
            text_patterns=[rf"{re.escape(tools_dir_name)}/"],
        )]
