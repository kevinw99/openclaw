"""豆包 (Doubao) 浏览器自动化适配器

通过 OpenClaw 浏览器 HTTP API 提取豆包对话历史。
使用 Chrome 扩展 relay 复用用户已登录的 Chrome 会话。

豆包是字节跳动的 AI 助手, 有较强的反爬虫措施, 因此:
  - 使用更长的随机延迟
  - 通过 Chrome 扩展复用真实浏览器指纹
  - 优先使用 JavaScript evaluate 而非 DOM 选择器

使用方式:
  1. 确保 OpenClaw 网关已启动
  2. 确保 Chrome 扩展已安装并已连接
  3. 确保用户已在 Chrome 中登录 doubao.com
  4. python3 -m knowledge_harvester scrape-doubao
"""

import json
import re
import time
from typing import Iterator, List, Optional

from .base import BaseAdapter
from ..browser_client import BrowserClient, BrowserError
from ..models import Conversation, Message


DOUBAO_URL = "https://www.doubao.com"

# 已知有效的 DOM 选择器 (用于版本检测)
DOUBAO_EXPECTED_SELECTORS = {
    "sidebar_items": 'a[href*="/chat/"], [class*="session-item"], [class*="conversation"]',
    "message_containers": '[data-testid*="message"], [class*="message-item"], [class*="chat-message"]',
    "chat_area": '[class*="chat-content"], [class*="ChatContent"], main',
}


class DoubaoAdapter(BaseAdapter):
    """通过浏览器自动化提取豆包对话"""

    def __init__(self, browser: BrowserClient = None):
        self._browser = browser or BrowserClient()

    @property
    def platform(self) -> str:
        return "doubao"

    def check_compatibility(self) -> list:
        """检查豆包页面结构是否与预期匹配"""
        browser = self._browser
        if not browser.is_ready():
            return ["浏览器未就绪"]

        warnings = []
        try:
            tab = browser.open_tab(DOUBAO_URL)
            target_id = tab.get("targetId", "")
            browser.wait(target_id, load_state="networkidle", timeout_ms=25000)
            browser.human_delay(3.0, 5.0)

            result = browser.evaluate("""() => {
                const checks = {};
                checks.sidebar = document.querySelectorAll(
                    'a[href*="/chat/"], [class*="session-item"], [class*="SessionItem"], [class*="conversation"]'
                ).length;
                checks.chat_area = document.querySelectorAll(
                    '[class*="chat-content"], [class*="ChatContent"], main'
                ).length;
                checks.title = document.title;
                return checks;
            }""", target_id)

            checks = result.get("result", {})

            if not checks.get("chat_area"):
                warnings.append("未找到聊天区域 — 豆包 UI 可能已更新")
            if not checks.get("sidebar"):
                warnings.append("未找到侧边栏对话列表 — 可能未登录或 UI 已变化")

            browser.close_tab(target_id)
        except Exception as e:
            warnings.append(f"兼容性检查失败: {e}")

        return warnings

    def extract(self, source: str = "") -> Iterator[Conversation]:
        """提取豆包对话

        Args:
            source: 忽略 (通过浏览器直接访问 doubao.com)
        """
        browser = self._browser

        if not browser.is_ready():
            raise BrowserError(
                "浏览器未就绪。请确保:\n"
                "  1. OpenClaw 网关已启动 (openclaw gateway start)\n"
                "  2. Chrome 扩展已连接\n"
                "  3. 已在 Chrome 中登录 doubao.com"
            )

        tab = browser.open_tab(DOUBAO_URL)
        target_id = tab.get("targetId", "")

        try:
            browser.wait(target_id, load_state="networkidle", timeout_ms=25000)
            # 豆包加载较慢, 给更多时间
            browser.human_delay(3.0, 6.0)

            # 获取对话列表
            conversation_ids = self._get_conversation_list(target_id)
            print(f"  发现 {len(conversation_ids)} 段豆包对话")

            for i, conv_meta in enumerate(conversation_ids):
                try:
                    conv = self._extract_conversation(target_id, conv_meta, i + 1)
                    if conv and conv.messages:
                        yield conv
                except Exception as e:
                    print(f"  ✗ 提取对话失败: {conv_meta.get('title', '?')}: {e}")

                # 豆包需要更长延迟以避免触发反爬
                browser.human_delay(3.0, 7.0)

        finally:
            try:
                browser.close_tab(target_id)
            except Exception:
                pass

    def _get_conversation_list(self, target_id: str) -> List[dict]:
        """从侧边栏提取对话列表"""
        browser = self._browser

        result = browser.evaluate("""() => {
            const conversations = [];

            // 豆包侧边栏的对话链接
            const selectors = [
                'a[href*="/chat/"]',
                '[data-testid*="conversation"]',
                '[class*="session-item"]',
                '[class*="SessionItem"]',
                '[class*="chat-item"]',
                '[class*="conversation"]',
            ];

            let links = [];
            for (const sel of selectors) {
                links = document.querySelectorAll(sel);
                if (links.length > 0) break;
            }

            links.forEach(el => {
                const link = el.tagName === 'A' ? el : el.querySelector('a') || el.closest('a');
                const href = link?.href || '';
                const title = el.textContent.trim().slice(0, 100);

                // 从 URL 提取对话 ID
                const idMatch = href.match(/\\/chat\\/([^/?]+)/);
                const id = idMatch?.[1] || el.getAttribute('data-id') ||
                           el.getAttribute('data-session-id') || '';

                if (id || title) {
                    conversations.push({ id, title, href });
                }
            });

            return conversations;
        }""", target_id)

        items = result.get("result", [])

        # 去重
        seen = set()
        unique = []
        for item in items:
            key = item.get("id") or item.get("title", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(item)

        return unique

    def _extract_conversation(self, target_id: str, conv_meta: dict,
                              index: int) -> Optional[Conversation]:
        """提取单段对话的消息"""
        browser = self._browser
        conv_id = conv_meta.get("id", f"doubao-{index}")
        title = conv_meta.get("title", "")
        href = conv_meta.get("href", "")

        # 导航到对话
        if href:
            browser.navigate(href, target_id)
        elif conv_id:
            browser.navigate(f"{DOUBAO_URL}/chat/{conv_id}", target_id)
        else:
            return None

        browser.wait(target_id, load_state="networkidle", timeout_ms=20000)
        browser.human_delay(2.0, 4.0)

        # 滚动到顶部加载历史消息
        browser.scroll_to_top(target_id)
        browser.human_delay(1.0, 2.0)

        # 提取消息
        messages = self._extract_messages(target_id)

        if not title and messages:
            title = messages[0].content[:60]

        return Conversation(
            id=conv_id,
            platform="doubao",
            title=title,
            participants=["user", "豆包"],
            messages=messages,
            metadata={"source_url": href},
        )

    def _extract_messages(self, target_id: str) -> List[Message]:
        """从当前页面提取所有消息"""
        browser = self._browser

        result = browser.evaluate("""() => {
            const messages = [];

            // 豆包的消息容器选择器 (可能随版本变化)
            const selectors = [
                '[data-testid*="message"]',
                '[class*="message-item"]',
                '[class*="MessageItem"]',
                '[class*="chat-message"]',
                '[class*="turn-"]',
                '[role="article"]',
            ];

            let elements = [];
            for (const sel of selectors) {
                elements = document.querySelectorAll(sel);
                if (elements.length > 0) break;
            }

            // 备选: 查找主聊天区域的消息块
            if (elements.length === 0) {
                const chatArea = document.querySelector('[class*="chat-content"]') ||
                                 document.querySelector('[class*="ChatContent"]') ||
                                 document.querySelector('main');
                if (chatArea) {
                    elements = chatArea.querySelectorAll(':scope > div');
                }
            }

            elements.forEach((el, idx) => {
                const text = el.textContent.trim();
                if (!text || text.length < 2) return;

                // 推断角色
                let role = 'unknown';
                const cls = (el.className || '').toLowerCase();
                const dataRole = el.getAttribute('data-role') ||
                                 el.getAttribute('data-message-role') || '';

                if (dataRole) {
                    role = dataRole.includes('user') || dataRole.includes('human') ? 'user' :
                           dataRole.includes('assistant') || dataRole.includes('bot') ? 'assistant' : dataRole;
                } else if (cls.includes('user') || cls.includes('human') || cls.includes('question')) {
                    role = 'user';
                } else if (cls.includes('assistant') || cls.includes('bot') ||
                           cls.includes('answer') || cls.includes('response')) {
                    role = 'assistant';
                } else {
                    role = idx % 2 === 0 ? 'user' : 'assistant';
                }

                // 时间戳
                const timeEl = el.querySelector('time') || el.querySelector('[class*="time"]');
                const timestamp = timeEl?.getAttribute('datetime') || '';

                messages.push({
                    role: role,
                    content: text.slice(0, 50000),
                    timestamp: timestamp,
                    index: idx
                });
            });

            return messages;
        }""", target_id)

        raw_messages = result.get("result", [])

        messages = []
        for raw in raw_messages:
            role = raw.get("role", "unknown")
            if role == "unknown":
                continue

            content = raw.get("content", "").strip()
            if not content:
                continue

            messages.append(Message(
                role=role,
                content=content,
                timestamp=raw.get("timestamp", ""),
            ))

        return messages
