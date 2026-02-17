"""Entity Registry - 自动发现项目实体"""

import re
from pathlib import Path
from typing import List

from ..models.category import Entity, EntityType


class EntityRegistry:
    """自动从项目目录结构发现实体"""

    # Legacy directory names before P##/R## renumbering (2026-02-15)
    # Used to match old references in JSONL session data
    LEGACY_ALIASES = {
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
        entities = []
        entities.extend(self._discover_specs())
        entities.extend(self._discover_sources())
        entities.extend(self._discover_research())
        entities.extend(self._discover_knowledge())
        entities.extend(self._discover_tools())
        return entities

    def _discover_specs(self) -> List[Entity]:
        """发现规格实体 (public P## and restricted R##)"""
        entities = []
        # Discover from both public and RESTRICTED spec directories
        spec_dirs = [
            self.project_root / "规格",
            self.project_root / "RESTRICTED" / "规格",
        ]
        for specs_dir in spec_dirs:
            if not specs_dir.exists():
                continue
            for d in sorted(specs_dir.iterdir()):
                if not d.is_dir():
                    continue
                name = d.name
                # 跳过模板
                if name == "00_project-template.md":
                    continue
                # 提取编号和名称 (P## or R## prefix)
                match = re.match(r"([PR]\d+)_(.+)", name)
                if match:
                    num = match.group(1)
                    desc = match.group(2)
                    rel_dir = str(d.relative_to(self.project_root))
                    # 生成关键词: 目录名, 中文名, 编号形式
                    keywords = [
                        name, desc,
                        f"spec {num}", f"spec #{num}", f"Spec {num}", f"Spec #{num}",
                        f"规格/{name}", f"规格{num}",
                        f"project {num}", f"project #{num}",
                    ]
                    # 从名称中提取中文关键词
                    for part in re.split(r"[_\-]", desc):
                        if part:
                            keywords.append(part)

                    path_patterns = [
                        f"{rel_dir}/",
                        f"{rel_dir}",
                    ]
                    text_patterns = [
                        rf"[Ss]pec\s*#?{re.escape(num)}\b",
                        rf"规格/{re.escape(name)}",
                        rf"规格.*{re.escape(num)}",
                        rf"project\s*#?{re.escape(num)}\b",
                    ]

                    # Add legacy aliases for old directory names
                    for old_name in self.LEGACY_ALIASES.get(name, []):
                        old_match = re.match(r"(\d+)_(.+)", old_name)
                        if old_match:
                            old_num = old_match.group(1)
                            keywords.extend([
                                old_name,
                                f"spec {old_num}", f"spec #{old_num}",
                                f"Spec {old_num}", f"Spec #{old_num}",
                            ])
                            path_patterns.extend([
                                f"规格/{old_name}/",
                                f"规格/{old_name}",
                            ])
                            text_patterns.extend([
                                rf"[Ss]pec\s*#?{old_num}\b",
                                rf"规格/{re.escape(old_name)}",
                                rf"规格.*{re.escape(old_num)}",
                            ])

                    entities.append(Entity(
                        entity_type=EntityType.SPEC,
                        name=name,
                        display_name=f"Spec {num}: {desc}",
                        directory=rel_dir,
                        keywords=keywords,
                        path_patterns=path_patterns,
                        text_patterns=text_patterns,
                    ))
        return entities

    def _discover_sources(self) -> List[Entity]:
        """发现源代码项目实体"""
        src_dir = self.project_root / "源代码"
        if not src_dir.exists():
            return []

        entities = []
        # 跳过非项目目录和本模块自身
        skip = {"README.md", "session_history", "__pycache__"}
        for d in sorted(src_dir.iterdir()):
            if not d.is_dir() or d.name in skip or d.name.startswith("."):
                continue
            name = d.name
            keywords = [name]
            # 将连字符/下划线分词
            for part in re.split(r"[-_]", name):
                if part and len(part) > 2:
                    keywords.append(part)

            entities.append(Entity(
                entity_type=EntityType.SOURCE,
                name=name,
                display_name=f"源代码: {name}",
                directory=f"源代码/{name}",
                keywords=keywords,
                path_patterns=[
                    f"源代码/{name}/",
                    f"源代码/{name}",
                ],
                text_patterns=[
                    rf"源代码/{re.escape(name)}",
                ],
            ))
        return entities

    def _discover_research(self) -> List[Entity]:
        """发现研究主题实体"""
        res_dir = self.project_root / "研究"
        if not res_dir.exists():
            return []

        entities = []
        skip = {"研究说明-EN.md", "指南", "__pycache__"}
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
                display_name=f"研究: {name}",
                directory=f"研究/{name}",
                keywords=keywords,
                path_patterns=[f"研究/{name}/", f"研究/{name}"],
                text_patterns=[rf"研究/{re.escape(name)}"],
            ))
        return entities

    def _discover_knowledge(self) -> List[Entity]:
        """发现知识库实体"""
        kb_dir = self.project_root / "知识库"
        if not kb_dir.exists():
            return []

        entities = []
        skip = {"知识库导航索引.md", "数据收集指南.md", "战略重点-EN.md", "__pycache__"}
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
                display_name=f"知识库: {name}",
                directory=f"知识库/{name}",
                keywords=keywords,
                path_patterns=[f"知识库/{name}/", f"知识库/{name}"],
                text_patterns=[rf"知识库/{re.escape(name)}"],
            ))
        return entities

    def _discover_tools(self) -> List[Entity]:
        """发现工具实体"""
        tools_dir = self.project_root / "工具"
        if not tools_dir.exists():
            return []

        # 工具目录没有子目录结构，作为单个实体处理
        return [Entity(
            entity_type=EntityType.TOOL,
            name="工具",
            display_name="工具",
            directory="工具",
            keywords=["工具", "tool", "session persistence", "聊天会话持久化"],
            path_patterns=["工具/"],
            text_patterns=[r"工具/"],
        )]
