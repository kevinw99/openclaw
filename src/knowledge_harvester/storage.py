"""存储层 - JSONL 读写和索引管理"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from .config import Config
from .models import Conversation, Message


class Storage:
    """对话的 JSONL 存储和索引管理"""

    def __init__(self, config: Config = None):
        self.config = config or Config()

    def save_conversation(self, conversation: Conversation) -> Path:
        """将对话保存为 JSONL 文件, 返回文件路径"""
        path = self.config.conversation_path(conversation.platform, conversation.id)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            for msg in conversation.messages:
                f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + "\n")

        self._update_index(conversation)
        return path

    def load_conversation(self, platform: str, conversation_id: str) -> Conversation:
        """从 JSONL 文件加载对话"""
        path = self.config.conversation_path(platform, conversation_id)

        messages = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                messages.append(Message.from_dict(json.loads(line)))

        # 从索引获取元数据
        index = self._load_index(platform)
        entry = next((e for e in index if e["id"] == conversation_id), {})

        return Conversation(
            id=conversation_id,
            platform=platform,
            title=entry.get("title", ""),
            participants=entry.get("participants", []),
            messages=messages,
            metadata=entry.get("metadata", {}),
        )

    def _update_index(self, conversation: Conversation):
        """更新平台索引文件"""
        index = self._load_index(conversation.platform)

        # 替换或追加
        entry = conversation.to_index_entry()
        found = False
        for i, existing in enumerate(index):
            if existing["id"] == conversation.id:
                index[i] = entry
                found = True
                break
        if not found:
            index.append(entry)

        index_path = self.config.index_path(conversation.platform)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def _load_index(self, platform: str) -> List[dict]:
        """加载平台索引"""
        index_path = self.config.index_path(platform)
        if not index_path.exists():
            return []
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_conversations(self, platform: str) -> List[dict]:
        """列出某平台的所有对话 (从索引)"""
        return self._load_index(platform)

    def list_platforms(self) -> List[str]:
        """列出所有已导入的平台"""
        if not self.config.output_dir.exists():
            return []
        return sorted(
            d.name for d in self.config.output_dir.iterdir()
            if d.is_dir() and (d / "index.json").exists()
        )

    # --- 增量提取状态管理 ---

    def load_state(self, platform: str) -> Dict:
        """加载平台提取状态

        返回格式:
        {
            "last_run": "2024-01-01T00:00:00+00:00",
            "conversations": {
                "conv-id": {
                    "message_count": 42,
                    "last_message_time": "2024-01-01T23:59:59+00:00"
                }
            }
        }
        """
        path = self.config.state_path(platform)
        if not path.exists():
            return {"last_run": "", "conversations": {}}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_state(self, platform: str, state: Dict):
        """保存平台提取状态"""
        path = self.config.state_path(platform)
        path.parent.mkdir(parents=True, exist_ok=True)
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def get_known_ids(self, platform: str) -> Set[str]:
        """获取已导入的对话 ID 集合"""
        state = self.load_state(platform)
        return set(state.get("conversations", {}).keys())

    def is_conversation_changed(self, platform: str, conversation: "Conversation") -> bool:
        """判断对话是否有变化 (新消息或新对话)"""
        state = self.load_state(platform)
        existing = state.get("conversations", {}).get(conversation.id)
        if existing is None:
            return True  # 新对话
        # 消息数量变化或最后消息时间变化
        last_ts = ""
        if conversation.messages:
            last_ts = conversation.messages[-1].timestamp
        return (
            conversation.message_count != existing.get("message_count", 0)
            or last_ts != existing.get("last_message_time", "")
        )

    def update_state_for_conversation(self, state: Dict, conversation: "Conversation"):
        """更新状态中单个对话的信息"""
        last_ts = ""
        if conversation.messages:
            last_ts = conversation.messages[-1].timestamp
        state.setdefault("conversations", {})[conversation.id] = {
            "message_count": conversation.message_count,
            "last_message_time": last_ts,
        }
