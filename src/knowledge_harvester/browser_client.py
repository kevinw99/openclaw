"""OpenClaw 浏览器 HTTP 客户端

通过 OpenClaw 浏览器控制服务器 (默认 http://127.0.0.1:18791) 操作浏览器,
复用用户已登录的 Chrome 会话 (通过 Chrome 扩展 relay)。
"""

import json
import time
import random
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional


DEFAULT_BASE_URL = "http://127.0.0.1:18791"
DEFAULT_PROFILE = "chrome"  # Chrome extension relay profile


class BrowserError(Exception):
    """浏览器操作错误"""
    pass


class BrowserClient:
    """OpenClaw 浏览器 HTTP API 客户端"""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, profile: str = DEFAULT_PROFILE):
        self.base_url = base_url.rstrip("/")
        self.profile = profile

    def _request(self, method: str, path: str, data: dict = None, timeout: int = 30) -> dict:
        """发送 HTTP 请求到浏览器服务器"""
        url = f"{self.base_url}{path}"
        if "?" in url:
            url += f"&profile={self.profile}"
        else:
            url += f"?profile={self.profile}"

        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body else {},
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise BrowserError(f"HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise BrowserError(
                f"无法连接浏览器服务器 {self.base_url}: {e.reason}\n"
                "请确保 OpenClaw 网关已启动 (openclaw gateway start)"
            )

    # --- 状态 ---

    def status(self) -> dict:
        """获取浏览器状态"""
        return self._request("GET", "/")

    def is_ready(self) -> bool:
        """检查浏览器是否就绪"""
        try:
            s = self.status()
            return s.get("running", False)
        except BrowserError:
            return False

    # --- 标签页管理 ---

    def list_tabs(self) -> List[dict]:
        """列出所有标签页"""
        resp = self._request("GET", "/tabs")
        return resp.get("tabs", [])

    def open_tab(self, url: str) -> dict:
        """打开新标签页"""
        return self._request("POST", "/tabs/open", {"url": url})

    def close_tab(self, target_id: str):
        """关闭标签页"""
        self._request("DELETE", f"/tabs/{target_id}")

    # --- 导航 ---

    def navigate(self, url: str, target_id: str) -> dict:
        """导航到指定 URL"""
        return self._request("POST", "/navigate", {"url": url, "targetId": target_id})

    # --- 快照 ---

    def snapshot(self, target_id: str, format: str = "ai",
                 max_chars: int = 80000, compact: bool = True) -> dict:
        """获取页面快照"""
        params = f"format={format}&targetId={target_id}&maxChars={max_chars}"
        if compact:
            params += "&compact=true"
        return self._request("GET", f"/snapshot?{params}")

    # --- 动作 ---

    def act(self, action: dict, target_id: str = None, timeout_ms: int = 15000) -> dict:
        """执行浏览器动作"""
        if target_id:
            action["targetId"] = target_id
        if "timeoutMs" not in action:
            action["timeoutMs"] = timeout_ms
        return self._request("POST", "/act", action, timeout=max(30, timeout_ms // 1000 + 5))

    def click(self, ref: str, target_id: str, timeout_ms: int = 10000) -> dict:
        return self.act({"kind": "click", "ref": ref}, target_id, timeout_ms)

    def type_text(self, ref: str, text: str, target_id: str,
                  submit: bool = False, timeout_ms: int = 10000) -> dict:
        return self.act({"kind": "type", "ref": ref, "text": text, "submit": submit},
                        target_id, timeout_ms)

    def scroll_into_view(self, ref: str, target_id: str, timeout_ms: int = 10000) -> dict:
        return self.act({"kind": "scrollIntoView", "ref": ref}, target_id, timeout_ms)

    def wait(self, target_id: str, text: str = None, text_gone: str = None,
             selector: str = None, load_state: str = None,
             time_ms: int = None, timeout_ms: int = 30000) -> dict:
        action = {"kind": "wait"}
        if text:
            action["text"] = text
        if text_gone:
            action["textGone"] = text_gone
        if selector:
            action["selector"] = selector
        if load_state:
            action["loadState"] = load_state
        if time_ms:
            action["timeMs"] = time_ms
        return self.act(action, target_id, timeout_ms)

    def evaluate(self, fn: str, target_id: str, ref: str = None,
                 timeout_ms: int = 15000) -> dict:
        """执行 JavaScript (需要 evaluateEnabled=true)"""
        action = {"kind": "evaluate", "fn": fn}
        if ref:
            action["ref"] = ref
        return self.act(action, target_id, timeout_ms)

    def press_key(self, key: str, target_id: str) -> dict:
        return self.act({"kind": "press", "key": key}, target_id)

    # --- 截图 ---

    def screenshot(self, target_id: str, full_page: bool = False) -> dict:
        return self._request("POST", "/screenshot", {
            "targetId": target_id,
            "fullPage": full_page,
        })

    # --- 辅助方法 ---

    def human_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """模拟人类操作延迟"""
        time.sleep(random.uniform(min_sec, max_sec))

    def scroll_page_down(self, target_id: str):
        """向下滚动一页"""
        self.press_key("PageDown", target_id)

    def scroll_to_bottom(self, target_id: str, max_scrolls: int = 50):
        """滚动到底部, 返回滚动次数"""
        for i in range(max_scrolls):
            prev_height = self.evaluate(
                "() => document.documentElement.scrollHeight", target_id
            )
            self.press_key("End", target_id)
            self.human_delay(0.5, 1.5)
            new_height = self.evaluate(
                "() => document.documentElement.scrollHeight", target_id
            )
            if prev_height == new_height:
                return i + 1
        return max_scrolls

    def scroll_to_top(self, target_id: str):
        """滚动到顶部"""
        self.press_key("Home", target_id)
        self.human_delay(0.5, 1.0)
