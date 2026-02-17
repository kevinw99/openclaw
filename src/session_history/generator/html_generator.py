"""HTML Generator - 生成交互式单文件 HTML 会话回放"""

import html
import json
from pathlib import Path
from typing import List

from ..models.index import EntityIndex
from ..models.session import Session, SessionMessage
from ..parser.jsonl_reader import JsonlReader


class HtmlGenerator:
    """生成交互式 HTML 回放 (单文件, 内联 CSS+JS)"""

    def __init__(self, exclude_thinking: bool = True):
        self.reader = JsonlReader(exclude_thinking=exclude_thinking)

    def generate(self, entity_index: EntityIndex, output_path: Path):
        """根据实体索引生成 HTML 回放"""
        sessions_html = []
        session_options = []

        for ref in entity_index.sessions:
            if not Path(ref.file_path).exists():
                continue
            session = self.reader.read_session(ref.file_path)
            sid_short = ref.session_id[:8]
            time_str = session.start_time[:10] if session.start_time else "N/A"

            session_options.append({
                "id": ref.session_id,
                "label": f"{time_str} ({sid_short}...) - {session.message_count} msgs",
            })
            sessions_html.append(self._render_session_html(session))

        page = self._build_page(
            title=entity_index.display_name,
            sessions_html=sessions_html,
            session_options=session_options,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(page)

    def generate_from_sessions(self, sessions: List[Session], title: str, output_path: Path):
        """从 Session 列表直接生成"""
        sessions_html = []
        session_options = []

        for session in sessions:
            sid_short = session.session_id[:8]
            time_str = session.start_time[:10] if session.start_time else "N/A"
            session_options.append({
                "id": session.session_id,
                "label": f"{time_str} ({sid_short}...) - {session.message_count} msgs",
            })
            sessions_html.append(self._render_session_html(session))

        page = self._build_page(
            title=title,
            sessions_html=sessions_html,
            session_options=session_options,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(page)

    def _render_session_html(self, session: Session) -> str:
        """渲染单个会话为 HTML 片段"""
        parts = [
            f'<div class="session" data-session-id="{html.escape(session.session_id)}">',
            f'  <div class="session-header">',
            f'    <h2>Session: {html.escape(session.session_id[:8])}...</h2>',
            f'    <span class="session-meta">'
            f'{html.escape(session.start_time[:19] if session.start_time else "N/A")} | '
            f'{session.message_count} messages</span>',
            f'  </div>',
            f'  <div class="session-messages">',
        ]

        for msg in session.messages:
            msg_html = self._render_message_html(msg)
            if msg_html:
                parts.append(msg_html)

        parts.append('  </div>')
        parts.append('</div>')
        return "\n".join(parts)

    def _render_message_html(self, msg: SessionMessage) -> str:
        """渲染单条消息为 HTML"""
        if msg.msg_type in ("progress", "file-history-snapshot"):
            return ""
        if msg.msg_type == "system" and msg.subtype in ("local_command",):
            return ""

        role = msg.role or msg.msg_type
        css_class = role
        timestamp = msg.timestamp[:19] if msg.timestamp else ""
        icon = {"user": "👤", "assistant": "🤖", "system": "⚙️"}.get(role, "📌")

        parts = [
            f'<div class="message {html.escape(css_class)}" data-type="{html.escape(role)}" data-uuid="{html.escape(msg.uuid)}">',
            f'  <div class="message-header">',
            f'    <span class="message-type">{icon} {html.escape(role.title())}</span>',
            f'    <span class="message-time">{html.escape(timestamp)}</span>',
            f'  </div>',
            f'  <div class="message-content">',
        ]

        for block in msg.content_blocks:
            if block.block_type == "text" and block.text:
                escaped = html.escape(block.text)
                # 简单 Markdown 渲染: 代码块, 加粗, 链接
                escaped = self._simple_markdown(escaped)
                parts.append(f'    <div class="text-block">{escaped}</div>')

            elif block.block_type == "tool_use":
                input_json = json.dumps(block.tool_input, ensure_ascii=False, indent=2)
                if len(input_json) > 500:
                    input_json = input_json[:500] + "\n..."
                parts.append(f'    <details class="tool-block">')
                parts.append(f'      <summary>🔧 {html.escape(block.tool_name)}</summary>')
                parts.append(f'      <pre class="tool-input">{html.escape(input_json)}</pre>')
                parts.append(f'    </details>')

            elif block.block_type == "tool_result":
                if block.text:
                    preview = block.text[:500]
                    parts.append(f'    <details class="tool-result-block">')
                    parts.append(f'      <summary>📋 Result ({len(block.text)} chars)</summary>')
                    parts.append(f'      <pre class="tool-output">{html.escape(preview)}</pre>')
                    parts.append(f'    </details>')

        parts.append('  </div>')
        parts.append('</div>')
        return "\n".join(parts)

    def _simple_markdown(self, text: str) -> str:
        """简单 Markdown 到 HTML 转换"""
        import re
        # 代码块
        text = re.sub(
            r'```(\w*)\n(.*?)```',
            r'<pre class="code-block"><code>\2</code></pre>',
            text, flags=re.DOTALL
        )
        # 行内代码
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        # 加粗
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        # 换行
        text = text.replace("\n", "<br>\n")
        return text

    def _build_page(self, title: str, sessions_html: list, session_options: list) -> str:
        """构建完整的 HTML 页面"""
        options_json = json.dumps(session_options, ensure_ascii=False)
        sessions_joined = "\n".join(sessions_html)

        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)} - 会话回放</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
    background-color: #1e1e1e;
    color: #d4d4d4;
    line-height: 1.6;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
header {{
    background-color: #2d2d30;
    padding: 20px;
    border-bottom: 2px solid #007acc;
    margin-bottom: 20px;
}}
header h1 {{ color: #569cd6; font-size: 1.5em; }}
header .subtitle {{ color: #858585; font-size: 0.9em; margin-top: 5px; }}

/* Controls */
.controls {{
    display: flex; gap: 10px; flex-wrap: wrap;
    padding: 10px 20px; background: #252526;
    border-bottom: 1px solid #3e3e42; margin-bottom: 20px;
    align-items: center;
}}
.controls input[type="text"] {{
    flex: 1; min-width: 200px; padding: 8px 12px;
    background: #3c3c3c; border: 1px solid #3e3e42;
    color: #d4d4d4; font-family: inherit; font-size: 0.9em;
    border-radius: 3px;
}}
.controls input[type="text"]:focus {{
    outline: none; border-color: #007acc;
}}
.controls select {{
    padding: 8px 12px; background: #3c3c3c; border: 1px solid #3e3e42;
    color: #d4d4d4; font-family: inherit; font-size: 0.9em;
    border-radius: 3px;
}}
.controls button {{
    padding: 8px 16px; background: #0e639c; border: none;
    color: #fff; cursor: pointer; font-family: inherit;
    border-radius: 3px;
}}
.controls button:hover {{ background: #1177bb; }}

/* Session */
.session {{
    margin-bottom: 30px;
    border: 1px solid #3e3e42;
    border-radius: 4px;
}}
.session-header {{
    background: #2d2d30; padding: 12px 16px;
    border-bottom: 1px solid #3e3e42;
    display: flex; justify-content: space-between; align-items: center;
    cursor: pointer;
}}
.session-header h2 {{ color: #569cd6; font-size: 1.1em; }}
.session-meta {{ color: #858585; font-size: 0.85em; }}
.session-messages {{ padding: 10px; }}

/* Messages */
.message {{
    margin: 8px 0; padding: 10px 14px;
    border-left: 4px solid #444;
    background-color: #252526;
    border-radius: 0 4px 4px 0;
}}
.message.user {{ border-left-color: #4ec9b0; }}
.message.assistant {{ border-left-color: #9cdcfe; }}
.message.system {{ border-left-color: #c586c0; }}
.message-header {{
    display: flex; justify-content: space-between;
    margin-bottom: 6px;
}}
.message-type {{ font-weight: bold; font-size: 0.9em; }}
.message.user .message-type {{ color: #4ec9b0; }}
.message.assistant .message-type {{ color: #9cdcfe; }}
.message.system .message-type {{ color: #c586c0; }}
.message-time {{ color: #858585; font-size: 0.8em; }}
.message-content {{ font-size: 0.9em; }}

/* Text */
.text-block {{ margin: 4px 0; white-space: pre-wrap; word-break: break-word; }}

/* Tool blocks */
.tool-block, .tool-result-block {{
    margin: 6px 0;
}}
.tool-block summary, .tool-result-block summary {{
    cursor: pointer; color: #dcdcaa; font-size: 0.85em;
    padding: 4px 0;
}}
.tool-result-block summary {{ color: #808080; }}
.tool-input, .tool-output {{
    background: #1e1e1e; padding: 8px;
    border: 1px solid #3e3e42; border-radius: 3px;
    font-size: 0.8em; overflow-x: auto;
    max-height: 300px; overflow-y: auto;
    white-space: pre-wrap;
}}

/* Code */
.code-block {{
    background: #1e1e1e; padding: 8px;
    border: 1px solid #3e3e42; border-radius: 3px;
    font-size: 0.85em; overflow-x: auto;
}}
code {{
    background: #3c3c3c; padding: 2px 4px;
    border-radius: 2px; font-size: 0.9em;
}}

/* Search highlight */
.highlight {{ background: #515c28; padding: 1px 2px; border-radius: 2px; }}

/* Hidden */
.hidden {{ display: none; }}

/* Stats bar */
.stats-bar {{
    padding: 8px 20px; background: #252526;
    border-bottom: 1px solid #3e3e42;
    color: #858585; font-size: 0.85em;
    margin-bottom: 10px;
}}
</style>
</head>
<body>
<header>
    <h1>{html.escape(title)} - 会话回放</h1>
    <div class="subtitle">Interactive Session Replay</div>
</header>
<div class="controls">
    <input type="text" id="searchInput" placeholder="Search messages..." onkeyup="handleSearch(event)">
    <select id="typeFilter" onchange="filterByType()">
        <option value="all">All Types</option>
        <option value="user">User Only</option>
        <option value="assistant">Assistant Only</option>
        <option value="system">System Only</option>
    </select>
    <select id="sessionFilter" onchange="filterBySession()">
        <option value="all">All Sessions</option>
    </select>
    <button onclick="expandAll()">Expand All</button>
    <button onclick="collapseAll()">Collapse All</button>
</div>
<div class="stats-bar" id="statsBar">Loading...</div>
<div class="container" id="content">
{sessions_joined}
</div>
<script>
const sessionOptions = {options_json};

// 初始化
document.addEventListener('DOMContentLoaded', function() {{
    const sel = document.getElementById('sessionFilter');
    sessionOptions.forEach(opt => {{
        const o = document.createElement('option');
        o.value = opt.id;
        o.textContent = opt.label;
        sel.appendChild(o);
    }});
    updateStats();
}});

function handleSearch(e) {{
    if (e.key === 'Enter' || e.target.value === '') {{
        doSearch();
    }}
}}

function doSearch() {{
    const query = document.getElementById('searchInput').value.trim().toLowerCase();
    const messages = document.querySelectorAll('.message');

    // 清除旧高亮
    document.querySelectorAll('.highlight').forEach(el => {{
        el.outerHTML = el.textContent;
    }});

    if (!query) {{
        messages.forEach(m => m.classList.remove('hidden'));
        updateStats();
        return;
    }}

    messages.forEach(msg => {{
        const text = msg.textContent.toLowerCase();
        if (text.includes(query)) {{
            msg.classList.remove('hidden');
            // 高亮匹配文本
            const textBlocks = msg.querySelectorAll('.text-block');
            textBlocks.forEach(tb => {{
                const regex = new RegExp('(' + query.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
                tb.innerHTML = tb.innerHTML.replace(regex, '<span class="highlight">$1</span>');
            }});
        }} else {{
            msg.classList.add('hidden');
        }}
    }});
    updateStats();
}}

function filterByType() {{
    const type = document.getElementById('typeFilter').value;
    const messages = document.querySelectorAll('.message');
    messages.forEach(msg => {{
        if (type === 'all' || msg.dataset.type === type) {{
            msg.classList.remove('hidden');
        }} else {{
            msg.classList.add('hidden');
        }}
    }});
    updateStats();
}}

function filterBySession() {{
    const sid = document.getElementById('sessionFilter').value;
    const sessions = document.querySelectorAll('.session');
    sessions.forEach(s => {{
        if (sid === 'all' || s.dataset.sessionId === sid) {{
            s.classList.remove('hidden');
        }} else {{
            s.classList.add('hidden');
        }}
    }});
    updateStats();
}}

function expandAll() {{
    document.querySelectorAll('details').forEach(d => d.open = true);
}}

function collapseAll() {{
    document.querySelectorAll('details').forEach(d => d.open = false);
}}

function updateStats() {{
    const total = document.querySelectorAll('.message').length;
    const visible = document.querySelectorAll('.message:not(.hidden)').length;
    const sessions = document.querySelectorAll('.session:not(.hidden)').length;
    document.getElementById('statsBar').textContent =
        `Showing ${{visible}}/${{total}} messages across ${{sessions}} session(s)`;
}}
</script>
</body>
</html>'''
