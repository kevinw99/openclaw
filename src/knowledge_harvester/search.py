"""全文搜索 - 跨平台对话搜索"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from .config import Config
from .models import Message


class SearchResult:
    """搜索结果"""
    __slots__ = ("platform", "conversation_id", "title", "message", "score")

    def __init__(self, platform: str, conversation_id: str, title: str,
                 message: Message, score: float = 1.0):
        self.platform = platform
        self.conversation_id = conversation_id
        self.title = title
        self.message = message
        self.score = score


class SearchEngine:
    """跨平台对话全文搜索"""

    def __init__(self, config: Config = None):
        self.config = config or Config()

    def search(self, query: str, platform: str = None,
               max_results: int = 50) -> List[SearchResult]:
        """搜索所有已导入的对话

        Args:
            query: 搜索关键词 (支持空格分隔的多个关键词, 全部匹配)
            platform: 限定搜索的平台 (None = 搜索所有)
            max_results: 最大返回结果数
        """
        keywords = query.lower().split()
        if not keywords:
            return []

        results = []
        platforms = self._get_platforms(platform)

        for plat in platforms:
            index = self._load_index(plat)
            for entry in index:
                conv_id = entry["id"]
                title = entry.get("title", "")
                hits = self._search_conversation(plat, conv_id, title, keywords)
                results.extend(hits)

                if len(results) >= max_results * 3:
                    break

        # 按 score 排序
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]

    def search_by_role(self, query: str, role: str,
                       platform: str = None, max_results: int = 50) -> List[SearchResult]:
        """按角色过滤搜索"""
        results = self.search(query, platform, max_results * 2)
        filtered = [r for r in results if r.message.role == role]
        return filtered[:max_results]

    def search_recent(self, query: str, days: int = 30,
                      platform: str = None, max_results: int = 50) -> List[SearchResult]:
        """搜索最近 N 天的对话"""
        from datetime import datetime, timedelta, timezone
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()

        results = self.search(query, platform, max_results * 2)
        filtered = [r for r in results if r.message.timestamp >= cutoff]
        return filtered[:max_results]

    def list_all(self, platform: str = None) -> List[Dict[str, Any]]:
        """列出所有对话的索引信息"""
        all_entries = []
        for plat in self._get_platforms(platform):
            index = self._load_index(plat)
            for entry in index:
                entry["platform"] = plat
                all_entries.append(entry)
        return all_entries

    def stats(self) -> Dict[str, Any]:
        """统计信息"""
        platforms = self._get_platforms()
        total_conversations = 0
        total_messages = 0
        platform_stats = {}

        for plat in platforms:
            index = self._load_index(plat)
            count = len(index)
            msgs = sum(e.get("message_count", 0) for e in index)
            total_conversations += count
            total_messages += msgs
            platform_stats[plat] = {"conversations": count, "messages": msgs}

        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "platforms": platform_stats,
        }

    def _get_platforms(self, platform: str = None) -> List[str]:
        """获取要搜索的平台列表"""
        if platform:
            return [platform]
        output_dir = self.config.output_dir
        if not output_dir.exists():
            return []
        return sorted(
            d.name for d in output_dir.iterdir()
            if d.is_dir() and (d / "index.json").exists()
        )

    def _load_index(self, platform: str) -> List[dict]:
        """加载平台索引"""
        index_path = self.config.index_path(platform)
        if not index_path.exists():
            return []
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _search_conversation(self, platform: str, conv_id: str,
                             title: str, keywords: List[str]) -> List[SearchResult]:
        """搜索单段对话"""
        conv_path = self.config.conversation_path(platform, conv_id)
        if not conv_path.exists():
            return []

        results = []

        # 标题匹配加分
        title_bonus = 0.5 if all(kw in title.lower() for kw in keywords) else 0.0

        with open(conv_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                content_lower = data.get("content", "").lower()

                # 也搜索媒体文件名和描述
                media_text = ""
                for m in data.get("media", []):
                    fn = m.get("filename", "")
                    desc = m.get("description", "")
                    if fn:
                        media_text += " " + fn
                    if desc:
                        media_text += " " + desc
                media_lower = media_text.lower()
                searchable = content_lower + media_lower

                if all(kw in searchable for kw in keywords):
                    msg = Message.from_dict(data)
                    # 计算简单相关度分数
                    score = sum(searchable.count(kw) for kw in keywords)
                    score = min(score / 10.0, 1.0) + title_bonus

                    results.append(SearchResult(
                        platform=platform,
                        conversation_id=conv_id,
                        title=title,
                        message=msg,
                        score=score,
                    ))

        return results
