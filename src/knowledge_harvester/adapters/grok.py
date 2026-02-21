"""Grok (grok.com) 浏览器自动化适配器

通过 OpenClaw 浏览器 HTTP API 提取 Grok 对话历史。
使用 Chrome 扩展 relay 复用用户已登录的 Chrome 会话。

使用方式:
  1. 确保 OpenClaw 网关已启动
  2. 确保 Chrome 扩展已安装并已连接
  3. 确保用户已在 Chrome 中登录 grok.com
  4. python3 -m knowledge_harvester scrape-grok
"""

import json
import re
import time
from datetime import datetime, timezone
from typing import Iterator, List, Optional

from .base import BaseAdapter
from ..browser_client import BrowserClient, BrowserError
from ..models import Conversation, Message


GROK_URL = "https://grok.com"

# 已知有效的 DOM 选择器 (用于版本检测)
GROK_EXPECTED_SELECTORS = {
    "sidebar_links": 'a[href*="/chat/"]',
    "message_containers": '[data-testid*="message"], [class*="message-row"], [role="article"]',
    "main_area": 'main, [role="main"]',
}


class GrokAdapter(BaseAdapter):
    """通过浏览器自动化提取 Grok 对话"""

    def __init__(self, browser: BrowserClient = None):
        self._browser = browser or BrowserClient()

    @property
    def platform(self) -> str:
        return "grok"

    def check_compatibility(self) -> list:
        """检查 Grok 页面结构是否与预期匹配"""
        browser = self._browser
        if not browser.is_ready():
            return ["浏览器未就绪"]

        warnings = []
        try:
            tab = browser.open_tab(GROK_URL)
            target_id = tab.get("targetId", "")
            browser.wait(target_id, load_state="networkidle", timeout_ms=20000)
            browser.human_delay(2.0, 3.0)

            # 检查各关键选择器
            result = browser.evaluate("""() => {
                const checks = {};
                checks.sidebar_links = document.querySelectorAll('a[href*="/chat/"]').length;
                checks.message_area = document.querySelectorAll(
                    '[data-testid*="message"], [class*="message-row"], [role="article"]'
                ).length;
                checks.main = document.querySelectorAll('main, [role="main"]').length;
                checks.title = document.title;
                return checks;
            }""", target_id)

            checks = result.get("result", {})

            if not checks.get("main"):
                warnings.append("未找到主内容区域 (main) — Grok UI 可能已更新")
            if not checks.get("sidebar_links"):
                warnings.append("未找到侧边栏对话链接 — 可能未登录或 UI 已变化")

            browser.close_tab(target_id)
        except Exception as e:
            warnings.append(f"兼容性检查失败: {e}")

        return warnings

    def extract(self, source: str = "") -> Iterator[Conversation]:
        """提取 Grok 对话

        Args:
            source: 忽略 (通过浏览器直接访问 grok.com)
        """
        browser = self._browser

        if not browser.is_ready():
            raise BrowserError(
                "浏览器未就绪。请确保:\n"
                "  1. OpenClaw 网关已启动 (openclaw gateway start)\n"
                "  2. Chrome 扩展已连接\n"
                "  3. 已在 Chrome 中登录 grok.com"
            )

        # 打开 Grok
        tab = browser.open_tab(GROK_URL)
        target_id = tab.get("targetId", "")

        try:
            browser.wait(target_id, load_state="networkidle", timeout_ms=20000)
            browser.human_delay(2.0, 4.0)

            # 获取对话列表
            conversation_ids = self._get_conversation_list(target_id)
            print(f"  发现 {len(conversation_ids)} 段 Grok 对话")

            for i, conv_meta in enumerate(conversation_ids):
                try:
                    conv = self._extract_conversation(target_id, conv_meta, i + 1)
                    if conv and conv.messages:
                        yield conv
                except Exception as e:
                    print(f"  ✗ 提取对话失败: {conv_meta.get('title', '?')}: {e}")

                browser.human_delay(2.0, 5.0)

        finally:
            try:
                browser.close_tab(target_id)
            except Exception:
                pass

    def _get_conversation_list(self, target_id: str) -> List[dict]:
        """从侧边栏提取对话列表"""
        browser = self._browser

        # 用 JS 提取侧边栏对话链接
        result = browser.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/chat/"]');
            return Array.from(links).map(a => ({
                href: a.href,
                title: a.textContent.trim(),
                id: a.href.match(/\\/chat\\/([^/?]+)/)?.[1] || ''
            })).filter(item => item.id);
        }""", target_id)

        items = result.get("result", [])
        if not items:
            # 备选: 尝试其他选择器
            result = browser.evaluate("""() => {
                const items = document.querySelectorAll('[data-testid*="conversation"], [class*="conversation"]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a') || el.closest('a');
                    const href = link?.href || '';
                    return {
                        href: href,
                        title: el.textContent.trim().slice(0, 100),
                        id: href.match(/\\/chat\\/([^/?]+)/)?.[1] || el.getAttribute('data-id') || ''
                    };
                }).filter(item => item.id || item.title);
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
        conv_id = conv_meta.get("id", f"grok-{index}")
        title = conv_meta.get("title", "")
        href = conv_meta.get("href", "")

        # 导航到对话
        if href:
            browser.navigate(href, target_id)
        else:
            browser.navigate(f"{GROK_URL}/chat/{conv_id}", target_id)

        browser.wait(target_id, load_state="networkidle", timeout_ms=15000)
        browser.human_delay(1.5, 3.0)

        # 滚动到顶部加载全部消息
        browser.scroll_to_top(target_id)
        browser.human_delay(1.0, 2.0)

        # 提取消息
        messages = self._extract_messages(target_id)

        if not title and messages:
            title = messages[0].content[:60]

        return Conversation(
            id=conv_id,
            platform="grok",
            title=title,
            participants=["user", "grok"],
            messages=messages,
            metadata={"source_url": href},
        )

    def _extract_messages(self, target_id: str) -> List[Message]:
        """从当前页面提取所有消息"""
        browser = self._browser

        result = browser.evaluate("""() => {
            const messages = [];

            // 尝试多种选择器 (Grok UI 可能更新)
            const selectors = [
                '[data-testid*="message"]',
                '[class*="message-row"]',
                '[class*="MessageRow"]',
                '.message',
                '[role="article"]',
            ];

            let elements = [];
            for (const sel of selectors) {
                elements = document.querySelectorAll(sel);
                if (elements.length > 0) break;
            }

            // 备选: 按结构特征查找对话消息
            if (elements.length === 0) {
                // Grok 的消息通常在 main 区域内, 交替的 user/assistant 块
                const main = document.querySelector('main') || document.querySelector('[role="main"]');
                if (main) {
                    // 查找 turn 容器 — 通常是直接子级 div
                    const turns = main.querySelectorAll(':scope > div > div');
                    elements = turns;
                }
            }

            elements.forEach((el, idx) => {
                const text = el.textContent.trim();
                if (!text) return;

                // 推断角色: 检查类名、data 属性、或位置 (偶数=user, 奇数=assistant)
                let role = 'unknown';
                const cls = el.className || '';
                const dataRole = el.getAttribute('data-role') || el.getAttribute('data-message-author-role') || '';

                if (dataRole) {
                    role = dataRole.includes('user') ? 'user' :
                           dataRole.includes('assistant') || dataRole.includes('grok') ? 'assistant' : dataRole;
                } else if (cls.includes('user') || cls.includes('human')) {
                    role = 'user';
                } else if (cls.includes('assistant') || cls.includes('bot') || cls.includes('grok')) {
                    role = 'assistant';
                } else {
                    // 按位置交替推断
                    role = idx % 2 === 0 ? 'user' : 'assistant';
                }

                // 提取时间戳 (如果存在 time 或 datetime 元素)
                const timeEl = el.querySelector('time');
                const timestamp = timeEl?.getAttribute('datetime') || timeEl?.textContent || '';

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

            timestamp = raw.get("timestamp", "")
            if timestamp and not timestamp.startswith("20"):
                timestamp = ""

            messages.append(Message(
                role=role,
                content=content,
                timestamp=timestamp,
            ))

        return messages
