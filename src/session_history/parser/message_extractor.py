"""Message Extractor - 从消息中提取文本和文件路径"""

import re
from typing import List, Set

from ..models.session import SessionMessage


class MessageExtractor:
    """从会话消息中提取分类相关信息"""

    # 项目根路径的可能前缀
    PROJECT_PREFIXES = [
        "/Users/kweng/AI/Enpack_CCC/",
        "/Users/kweng/AI/Enpack-CCC/",
    ]

    def extract_file_paths(self, msg: SessionMessage) -> List[str]:
        """提取消息中引用的所有文件路径 (归一化为项目相对路径)"""
        raw_paths = msg.file_paths
        normalized = []
        for p in raw_paths:
            rel = self._normalize_path(p)
            if rel:
                normalized.append(rel)

        # 也从文本内容中提取路径
        text = msg.text_content
        if text:
            for match in re.finditer(
                r'(?:规格|源代码|研究|知识库|工具)/[^\s\'"`,;)\]}>]+', text
            ):
                path = match.group(0).rstrip(".,;:)")
                normalized.append(path)

        return list(dict.fromkeys(normalized))  # 去重保序

    def extract_text(self, msg: SessionMessage) -> str:
        """提取消息的纯文本内容 (用于关键词和模式匹配)"""
        parts = []

        # 用户或助手的文本
        text = msg.text_content
        if text:
            parts.append(text)

        # 系统消息 content
        if msg.msg_type == "system":
            for block in msg.content_blocks:
                if block.block_type == "text":
                    parts.append(block.text)

        return "\n".join(parts)

    def extract_keywords(self, msg: SessionMessage) -> Set[str]:
        """提取消息中的关键词 (用于模糊匹配)"""
        text = self.extract_text(msg)
        if not text:
            return set()

        # 提取中文词汇 (连续中文字符)
        chinese_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', text))

        # 提取英文词汇
        english_words = set(
            w.lower() for w in re.findall(r'[a-zA-Z_]{3,}', text)
        )

        return chinese_words | english_words

    def _normalize_path(self, path: str) -> str:
        """将绝对路径归一化为项目相对路径"""
        for prefix in self.PROJECT_PREFIXES:
            if path.startswith(prefix):
                return path[len(prefix):]

        # 已经是相对路径
        if path.startswith(("规格/", "源代码/", "研究/", "知识库/", "工具/")):
            return path

        return ""
