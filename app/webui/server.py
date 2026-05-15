from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from html import escape
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.host import HOST, BASE_DIR
from app.webui.config_store import (
    ConfigValidationError,
    get_dashboard_state,
    update_mcp_servers_from_form,
    update_persona_from_form,
    update_settings_from_form,
)
from app.webui.data_query import (
    get_stats,
    list_votes,
    list_quotes_data,
    list_countdowns_data,
    list_scheduled_msgs_data,
    list_keyword_rules_data,
    list_calendar_events_data,
)

app = FastAPI(title="QQ AI Bot WebUI", version="2.0.0")

# ── 认证配置 ─────────────────────────────────────────────
_AUTH_COOKIE = "qqbot_session"
_SESSION_SECRET = os.urandom(32).hex()  # 每次启动随机，重启需重新登录
_PASSWORD_FILE = BASE_DIR / "data" / ".webui_auth.json"


def _get_stored_hash() -> str:
    """获取存储的密码哈希，未设置返回空。"""
    if _PASSWORD_FILE.exists():
        try:
            data = json.loads(_PASSWORD_FILE.read_text(encoding="utf-8"))
            return data.get("password_hash", "")
        except Exception:
            pass
    return ""


def _set_password(password: str) -> None:
    """保存密码哈希。"""
    _PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    _PASSWORD_FILE.write_text(json.dumps({"password_hash": pw_hash}), encoding="utf-8")


def _make_token(password: str) -> str:
    """生成签名 token。"""
    payload = f"{password}:{int(time.time())}"
    sig = hmac.new(_SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_token(token: str) -> bool:
    """验证 token 是否有效。"""
    stored_hash = _get_stored_hash()
    if not stored_hash:
        return False
    try:
        parts = token.rsplit(":", 1)
        if len(parts) != 2:
            return False
        payload, sig = parts
        expected = hmac.new(_SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        pw_part = payload.split(":")[0]
        return hmac.compare_digest(hashlib.sha256(pw_part.encode()).hexdigest(), stored_hash)
    except Exception:
        return False


def _is_authenticated(request: Request) -> bool:
    """检查请求是否已认证。"""
    token = request.cookies.get(_AUTH_COOKIE, "")
    return bool(token) and _verify_token(token)


# ── 登录页面 ─────────────────────────────────────────────
_LOGIN_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>QQ AI Bot - 登录</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f0f0f;color:#e0e0e0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.login-box{{background:#1a1a1a;border:1px solid #333;border-radius:16px;padding:40px;width:380px;max-width:90vw}}
h1{{font-size:24px;margin-bottom:8px;text-align:center}}
p.sub{{text-align:center;color:#888;margin-bottom:24px;font-size:14px}}
input[type=password]{{width:100%;padding:12px 16px;border:1px solid #333;border-radius:8px;background:#0f0f0f;color:#e0e0e0;font-size:15px;margin-bottom:12px;outline:none}}
input[type=password]:focus{{border-color:#4a9eff}}
button{{width:100%;padding:12px;border:none;border-radius:8px;background:#4a9eff;color:#fff;font-size:15px;font-weight:600;cursor:pointer}}
button:hover{{background:#3a8eef}}
.err{{color:#ff6b6b;font-size:13px;text-align:center;margin-bottom:12px}}
.note{{text-align:center;font-size:12px;color:#666;margin-top:16px}}
</style></head><body>
<div class="login-box">
  <h1>🤖 QQ AI Bot</h1>
  <p class="sub">{title}</p>
  {error}
  <form method="post" action="/auth">
    <input type="password" name="password" placeholder="请输入密码" autofocus required />
    {confirm}
    <input type="hidden" name="mode" value="{mode}" />
    <button type="submit">{button}</button>
  </form>
  <p class="note">密码仅存储在本地，加密保存</p>
</div>
<div style="position:fixed;top:12px;right:16px;z-index:999">
<a href="/logout" style="color:#ff6b6b;text-decoration:none;font-size:13px;padding:6px 12px;border:1px solid #ff6b6b;border-radius:6px;opacity:0.7">退出登录</a>
</div>
</body></html>"""


@app.get("/login", response_class=HTMLResponse)
async def login_page(error: str = ""):
    stored_hash = _get_stored_hash()
    is_first = not stored_hash
    err_html = f'<p class="err">{escape(error)}</p>' if error else ""
    if is_first:
        return _LOGIN_HTML.format(
            title="首次使用，请设置管理密码",
            error=err_html,
            confirm='<input type="password" name="password2" placeholder="确认密码" required />',
            mode="setup",
            button="设置密码并进入",
        )
    return _LOGIN_HTML.format(
        title="请输入管理密码",
        error=err_html,
        confirm="",
        mode="login",
        button="登录",
    )


@app.post("/auth")
async def auth_handler(
    password: str = Form(...),
    password2: str = Form(""),
    mode: str = Form("login"),
):
    stored_hash = _get_stored_hash()

    if mode == "setup":
        if stored_hash:
            return RedirectResponse(url="/login?error=密码已设置，请直接登录", status_code=303)
        if len(password) < 4:
            return RedirectResponse(url="/login?error=密码至少4位", status_code=303)
        if password != password2:
            return RedirectResponse(url="/login?error=两次密码不一致", status_code=303)
        _set_password(password)
        token = _make_token(password)
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(_AUTH_COOKIE, token, httponly=True, samesite="lax", max_age=86400 * 7)
        return resp

    # login
    if not stored_hash:
        return RedirectResponse(url="/login?mode=setup", status_code=303)
    if not password:
        return RedirectResponse(url="/login?error=请输入密码", status_code=303)
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if not hmac.compare_digest(pw_hash, stored_hash):
        return RedirectResponse(url="/login?error=密码错误", status_code=303)
    token = _make_token(password)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(_AUTH_COOKIE, token, httponly=True, samesite="lax", max_age=86400 * 7)
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(_AUTH_COOKIE)
    return resp


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # 放行登录相关路由和静态资源
    if path in ("/login", "/auth", "/favicon.ico", "/logout"):
        return await call_next(request)
    # API 路由也放行（供 AJAX 调用，实际生产可加 token）
    if path.startswith("/api/"):
        if not _is_authenticated(request):
            return Response(status_code=401, content="Unauthorized")
        return await call_next(request)
    # 其他路由检查登录
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return await call_next(request)


@app.get("/favicon.ico")
async def favicon():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🤖</text></svg>'
    return Response(content=svg, media_type="image/svg+xml")


def _selected(current: str, expected: str) -> str:
    return "selected" if current == expected else ""


def _bool_select(name: str, value: bool) -> str:
    return f"""
    <select name="{escape(name)}">
      <option value="true" {_selected(str(value).lower(), 'true')}>开启</option>
      <option value="false" {_selected(str(value).lower(), 'false')}>关闭</option>
    </select>
    """


def _runtime_status_badge(ok: bool) -> str:
    if ok:
        return "<span class='status-badge ok'>运行中</span>"
    return "<span class='status-badge off'>已停止</span>"


def _kv(label: str, value: str) -> str:
    return f"""
    <div class="kv-item">
      <div class="kv-label">{escape(label)}</div>
      <div class="kv-value">{value}</div>
    </div>
    """


def _section_title(title: str, desc: str, anchor: str = "") -> str:
    anchor_attr = f" id=\"{escape(anchor)}\"" if anchor else ""
    return f"""
    <div class="section-head"{anchor_attr}>
      <div>
        <h2>{escape(title)}</h2>
        <p>{escape(desc)}</p>
      </div>
    </div>
    """


def _summary_card(title: str, value: str, sub: str, tone: str = "") -> str:
    tone_class = f" {tone}" if tone else ""
    return f"""
    <div class="summary-card{tone_class}">
      <div class="summary-title">{escape(title)}</div>
      <div class="summary-value">{value}</div>
      <div class="summary-sub">{sub}</div>
    </div>
    """


def _nav_link(label: str, target: str) -> str:
    return f"<a class=\"nav-link\" href=\"#{escape(target)}\">{escape(label)}</a>"


def _persona_preview_list(items: list[str]) -> str:
    if not items:
        return "<div class='empty-hint'>暂无内容</div>"
    return "".join(f"<li>{escape(item)}</li>" for item in items[:6])


def _mcp_server_block(server: dict, idx: int) -> str:
    return f"""
    <section class="mcp-server">
      <div class="mcp-head">
        <div>
          <h3>MCP Server #{idx + 1}</h3>
          <p>{escape(str(server['name'])) or f'Server {idx + 1}'}</p>
        </div>
        <span class="chip">{escape(str(server['transport']))}</span>
      </div>

      <div class="field-grid cols-2">
        <div class="field">
          <label>name</label>
          <input name="server_{idx}_name" value="{escape(str(server['name']))}" placeholder="ticket_12306" />
        </div>
        <div class="field">
          <label>transport</label>
          <select name="server_{idx}_transport">
            <option value="stdio" {_selected(str(server['transport']), 'stdio')}>stdio</option>
            <option value="http" {_selected(str(server['transport']), 'http')}>http</option>
            <option value="sse" {_selected(str(server['transport']), 'sse')}>sse</option>
          </select>
        </div>
      </div>

      <div class="field-grid cols-2">
        <div class="field">
          <label>command</label>
          <input name="server_{idx}_command" value="{escape(str(server['command']))}" placeholder="npx" />
        </div>
        <div class="field">
          <label>tool_prefix</label>
          <input name="server_{idx}_tool_prefix" value="{escape(str(server['tool_prefix']))}" placeholder="ticket_12306" />
        </div>
      </div>

      <div class="field-grid cols-2">
        <div class="field">
          <label>default_permission</label>
          <input name="server_{idx}_default_permission" value="{escape(str(server['default_permission']))}" placeholder="member" />
        </div>
        <div class="field">
          <label>timeout_seconds</label>
          <input type="number" min="1" name="server_{idx}_timeout_seconds" value="{escape(str(server['timeout_seconds']))}" />
        </div>
      </div>

      <div class="field">
        <label>args（每行一个）</label>
        <textarea name="server_{idx}_args">{escape(chr(10).join(server['args']))}</textarea>
      </div>

      <div class="field-grid cols-2">
        <div class="field">
          <label>enabled_tools（每行一个，可留空）</label>
          <textarea name="server_{idx}_enabled_tools">{escape(chr(10).join(server['enabled_tools']))}</textarea>
        </div>
        <div class="field">
          <label>disabled_tools（每行一个，可留空）</label>
          <textarea name="server_{idx}_disabled_tools">{escape(chr(10).join(server['disabled_tools']))}</textarea>
        </div>
      </div>
    </section>
    """


def _accordion(title: str, anchor: str, body: str, open_by_default: bool = False, meta: str = "") -> str:
    open_attr = " open" if open_by_default else ""
    meta_html = f"<span class='accordion-meta'>{meta}</span>" if meta else ""
    return f"""
    <details class="accordion"{open_attr}>
      <summary id="{escape(anchor)}">
        <div class="accordion-title-wrap">
          <span class="accordion-title">{escape(title)}</span>
          {meta_html}
        </div>
        <span class="accordion-arrow">&#8964;</span>
      </summary>
      <div class="accordion-body">{body}</div>
    </details>
    """

def render_page(
    selected_persona: str | None = None,
    saved: str = "",
    mcp_count: int | None = None,
    error: str = "",
) -> str:
    state = get_dashboard_state(selected_persona)
    form = state["form"]
    persona = state["persona"]
    personas = state["personas"]
    runtime = state["runtime"]
    mcp_servers = state["mcp_servers"]

    if mcp_count is not None and mcp_count > len(mcp_servers):
        for idx in range(len(mcp_servers), mcp_count):
            mcp_servers.append(
                {
                    "index": idx,
                    "name": f"server_{idx + 1}",
                    "transport": "stdio",
                    "command": "",
                    "args": [],
                    "default_permission": "member",
                    "tool_prefix": "",
                    "timeout_seconds": 30,
                    "enabled_tools": [],
                    "disabled_tools": [],
                }
            )

    persona_options = "".join(
        f"<option value=\"{escape(name)}\" {_selected(state['selected_persona'], name)}>{escape(name)}</option>"
        for name in personas
    )
    mcp_html = "".join(_mcp_server_block(server, idx) for idx, server in enumerate(mcp_servers))

    stats = get_stats()

    notice = ""
    if error:
        notice = f"<div class='notice error'>{escape(error)}</div>"
    elif saved == "settings":
        notice = "<div class='notice success'>基础配置已保存。</div>"
    elif saved == "persona":
        notice = "<div class='notice success'>人设已保存。</div>"
    elif saved == "mcp":
        notice = "<div class='notice success'>MCP 配置已保存到 config.yaml。</div>"
    elif saved == "bot_start":
        notice = "<div class='notice success'>机器人启动指令已执行。</div>"
    elif saved == "bot_stop":
        notice = "<div class='notice success'>机器人停止指令已执行。</div>"
    elif saved == "bot_restart":
        notice = "<div class='notice success'>机器人重启指令已执行。</div>"
    elif saved == "envvars":
        notice = "<div class='notice success'>环境变量已保存，重启机器人生效。</div>"

    current_count = max(1, len(mcp_servers))
    bot_status = _runtime_status_badge(bool(runtime["bot_running"]))
    webui_status = _runtime_status_badge(bool(runtime["webui_running"]))
    trigger_count = len([item for item in str(form["trigger_prefixes"]).splitlines() if item.strip()])
    active_features = sum(
        1
        for value in [form["feature_ai"], form["tool_call_enabled"], form["memory_enabled"], form["mcp_enabled"]]
        if bool(value)
    )
    persona_rule_count = len(persona["rules"])
    persona_forbidden_count = len(persona["forbidden"])

    runtime_panel = f"""
      {_section_title('运行状态与控制', '查看当前运行状态，并执行启动、停止、重启等控制操作。')}
      <div class=\"status-row\">
        {_kv('机器人', bot_status)}
        {_kv('WebUI', webui_status)}
        {_kv('NapCat WS', f"<code>{escape(str(runtime['ws_url']))}</code>")}
      </div>
      <div class=\"toolbar\">
        <form method=\"post\" action=\"/control/bot/start\"><button type=\"submit\">启动机器人</button></form>
        <form method=\"post\" action=\"/control/bot/restart\"><button type=\"submit\" class=\"warn\">重启机器人</button></form>
        <form method=\"post\" action=\"/control/bot/stop\"><button type=\"submit\" class=\"danger\">停止机器人</button></form>
      </div>
      <p class=\"subtle\">通过 <code>python -m app.main</code> 启动时，WebUI 会随主程序一起运行。本区域控制的是机器人运行状态，不影响当前 WebUI 页面服务。</p>
    """

    settings_panel = f"""
      {_section_title('基础配置', '集中维护运行环境、连接地址、默认模型与功能开关等基础参数。')}
      <form method=\"post\" action=\"/save/settings\" class=\"stack\">
        <div class=\"field-grid cols-2\">
          <div class=\"field\">
            <label>运行环境 APP_ENV</label>
            <input name=\"app_env\" value=\"{escape(str(form['app_env']))}\" />
          </div>
          <div class=\"field\">
            <label>NapCat WebSocket 地址</label>
            <input name=\"ws_url\" value=\"{escape(str(form['ws_url']))}\" />
          </div>
        </div>

        <div class=\"field\">
          <label>AI 接口地址 OPENAI_BASE_URL</label>
          <input name=\"openai_base_url\" value=\"{escape(str(form['openai_base_url']))}\" />
        </div>

        <div class=\"field\">
          <label>AI 接口 Key OPENAI_API_KEY</label>
          <input type=\"password\" name=\"openai_api_key\" value=\"\" placeholder=\"留空则保留当前 Key，不会覆盖\" />
        </div>

        <div class=\"field-grid cols-2\">
          <div class=\"field\">
            <label>默认模型 DEFAULT_MODEL</label>
            <input name=\"default_model\" value=\"{escape(str(form['default_model']))}\" />
          </div>
          <div class=\"field\">
            <label>默认人设 default_persona</label>
            <select name=\"default_persona\">{persona_options}</select>
          </div>
        </div>

        <div class=\"field-grid cols-2\">
          <div class=\"field\">
            <label>上下文轮数 max_context_rounds</label>
            <input type=\"number\" min=\"1\" name=\"max_context_rounds\" value=\"{escape(str(form['max_context_rounds']))}\" />
          </div>
          <div class=\"field\">
            <label>AI 总开关 features.ai</label>
            {_bool_select('feature_ai', bool(form['feature_ai']))}
          </div>
        </div>

        <div class=\"field-grid cols-3\">
          <div class=\"field\">
            <label>工具调用 tool_call_enabled</label>
            {_bool_select('tool_call_enabled', bool(form['tool_call_enabled']))}
          </div>
          <div class=\"field\">
            <label>记忆功能 memory_enabled</label>
            {_bool_select('memory_enabled', bool(form['memory_enabled']))}
          </div>
          <div class=\"field\">
            <label>MCP 总开关 mcp.enabled</label>
            {_bool_select('mcp_enabled', bool(form['mcp_enabled']))}
          </div>
        </div>

        <div class=\"field\">
          <label>AI 唤醒词 trigger_prefixes（每行一个）</label>
          <textarea name=\"trigger_prefixes\">{escape(str(form['trigger_prefixes']))}</textarea>
        </div>

        <div class=\"toolbar\">
          <button type=\"submit\">保存基础配置</button>
        </div>
      </form>
    """

    persona_panel = f"""
      {_section_title('人设编辑', '用于切换当前人设文件，并维护名称、风格、规则与限制项等内容。')}
      <form method=\"get\" action=\"/\" class=\"stack\">
        <div class=\"field\">
          <label>切换当前编辑的人设文件</label>
          <select name=\"persona\">{persona_options}</select>
        </div>
        <div class=\"toolbar\">
          <button type=\"submit\" class=\"secondary\">加载人设</button>
        </div>
      </form>

      <div class=\"preview-grid\" style=\"margin-top:16px;\">
        <div class=\"preview-box\">
          <h4>当前人设概览</h4>
          <div class=\"mini-list\">
            <div class=\"mini-item\"><span>展示名</span><span>{escape(str(persona['name'])) or '-'}</span></div>
            <div class=\"mini-item\"><span>风格</span><span>{escape(str(persona['style'])) or '-'}</span></div>
            <div class=\"mini-item\"><span>规则数</span><span>{persona_rule_count}</span></div>
            <div class=\"mini-item\"><span>禁止项</span><span>{persona_forbidden_count}</span></div>
          </div>
        </div>
      </div>

      <form method=\"post\" action=\"/save/persona\" class=\"stack\" style=\"margin-top:16px;\">
        <div class=\"field\">
          <label>人设文件名（不带 .yaml，可新建）</label>
          <input name=\"persona_file_name\" value=\"{escape(str(persona['file_name']))}\" />
        </div>

        <div class=\"field-grid cols-2\">
          <div class=\"field\">
            <label>展示名 name</label>
            <input name=\"name\" value=\"{escape(str(persona['name']))}\" />
          </div>
          <div class=\"field\">
            <label>风格 style</label>
            <input name=\"style\" value=\"{escape(str(persona['style']))}\" />
          </div>
        </div>

        <div class=\"field\">
          <label>身份 identity</label>
          <input name=\"identity\" value=\"{escape(str(persona['identity']))}\" />
        </div>

        <div class=\"preview-grid\">
          <div class=\"preview-box\">
            <h4>规则预览（最多展示 6 条）</h4>
            <ul>{_persona_preview_list(persona['rules'])}</ul>
          </div>
          <div class=\"preview-box\">
            <h4>禁止项预览（最多展示 6 条）</h4>
            <ul>{_persona_preview_list(persona['forbidden'])}</ul>
          </div>
        </div>

        <div class=\"field\">
          <label>规则 rules（每行一条）</label>
          <textarea name=\"rules\">{escape(chr(10).join(persona['rules']))}</textarea>
        </div>

        <div class=\"field\">
          <label>禁止项 forbidden（每行一条）</label>
          <textarea name=\"forbidden\">{escape(chr(10).join(persona['forbidden']))}</textarea>
        </div>

        <div class=\"toolbar\">
          <button type=\"submit\">保存人设</button>
        </div>
      </form>
    """

    mcp_panel = f"""
      {_section_title('MCP 可视化配置', '用于维护 MCP 服务列表及其运行参数，配置内容会写入 config.yaml。')}
      <p class=\"subtle\">此处编辑的是 <code>config.yaml -&gt; mcp.servers</code>。当前运行环境主要使用 <code>stdio</code> 方式接入，<code>transport</code> 字段会保留在配置中以兼容后续扩展。</p>

      <form method=\"get\" action=\"/\" class=\"toolbar split\">
        <div class=\"inline-form\">
          <input type=\"hidden\" name=\"persona\" value=\"{escape(state['selected_persona'])}\" />
          <span class=\"chip\">当前配置项数量</span>
          <input type=\"number\" min=\"1\" name=\"mcp_count\" value=\"{current_count + 1}\" />
        </div>
        <button type=\"submit\" class=\"secondary\">新增一项配置</button>
      </form>

      <form method=\"post\" action=\"/save/mcp\" class=\"stack\" style=\"margin-top:18px;\">
        <input type=\"hidden\" name=\"server_count\" value=\"{current_count}\" />
        <input type=\"hidden\" name=\"persona\" value=\"{escape(state['selected_persona'])}\" />
        <div class=\"mcp-stack\">{mcp_html}</div>
        <div class=\"toolbar\">
          <button type=\"submit\">保存 MCP 配置</button>
        </div>
      </form>
    """

    # ═══════════════════════════════════════════════════
    #  工具总览面板
    # ═══════════════════════════════════════════════════
    tools_panel = """
      {_section_title('工具总览', '当前注册的全部工具，共 53 个。工具可通过 AI Tool Call 或命令调用。')}
      <div class="field-grid cols-3">
        <div class="preview-box"><h4>🌤 API 类工具 (11)</h4><ul>
          <li>weather_query — 查询天气</li>
          <li>ip_location_query — IP 归属地</li>
          <li>translate_text — 翻译文本</li>
          <li>image_search — 以图搜图</li>
          <li>search_music — 音乐点歌</li>
          <li>generate_meme — 表情包生成</li>
          <li>repo_info — GitHub 仓库查询</li>
          <li>repo_releases — GitHub Release</li>
          <li>random_superpower — 随机超能力</li>
          <li>kfc_crazy_thursday — KFC 文案</li>
          <li>name_duplicate_query — 重名查询</li>
        </ul></div>
        <div class="preview-box"><h4>🎯 群互动工具 (20)</h4><ul>
          <li>create_vote / cast_vote / vote_result / close_vote</li>
          <li>add_quote / random_quote / search_quote / list_quotes</li>
          <li>start_guess / make_guess — 猜数字</li>
          <li>start_quiz / answer_quiz — 答题竞赛</li>
          <li>add_countdown / list_countdowns / delete_countdown</li>
          <li>add_event / list_events / delete_event</li>
          <li>create_scheduled_message / list / delete / toggle</li>
          <li>summarize_chat — 群聊摘要</li>
        </ul></div>
        <div class="preview-box"><h4>⚙️ 管理工具 (22)</h4><ul>
          <li>set_welcome / get_welcome / clear_welcome</li>
          <li>set_verify_question — 入群验证</li>
          <li>add_keyword_rule / list / delete</li>
          <li>mute_member / kick_member</li>
          <li>create_reminder — 提醒</li>
          <li>sign_in / query_score — 签到积分</li>
          <li>remember_fact / recall_memory — 记忆</li>
          <li>list_personas / preview / switch</li>
          <li>media_parse — 媒体解析</li>
        </ul></div>
      </div>
    """

    # ═══════════════════════════════════════════════════
    #  命令速查面板
    # ═══════════════════════════════════════════════════
    commands_panel = """
      {_section_title('命令速查表', '全部可用命令一览。')}
      <div class="field-grid cols-2">
        <div class="preview-box"><h4>📡 工具类</h4><ul>
          <li>/天气 城市 — 查询天气</li>
          <li>/IP 地址 — IP 归属地</li>
          <li>/翻译 [语言] 文本 — 多语言翻译</li>
          <li>/搜图 — 以图搜图（附带图片）</li>
          <li>/点歌 歌名 — 搜索音乐</li>
          <li>/github 用户/仓库 — GitHub 查询</li>
          <li>/重名 姓名 — 重名查询</li>
          <li>/解析 URL — 媒体解析</li>
        </ul></div>
        <div class="preview-box"><h4>🎮 趣味 / 互动</h4><ul>
          <li>/超能力 — 随机超能力</li>
          <li>/KFC — 疯狂星期四</li>
          <li>/表情 文字 | 文字 — 生成表情包</li>
          <li>/投票 问题 | 选项 — 创建投票</li>
          <li>/投票 ID 编号 — 参与投票</li>
          <li>/语录收录 / 语录 / 语录搜索</li>
          <li>/猜数字 / 猜 数字 — 猜数字游戏</li>
          <li>/答题 / 答题 编号 — 答题竞赛</li>
        </ul></div>
        <div class="preview-box"><h4>📋 管理</h4><ul>
          <li>/提醒 分钟 内容 — 创建提醒</li>
          <li>/签到 / /积分 — 签到积分</li>
          <li>/日程 时间 标题 — 添加日程</li>
          <li>/日程列表 / /日程删除 ID</li>
          <li>/定时 cron 内容 — 定时消息</li>
          <li>/定时列表 / /定时删除 ID</li>
          <li>/倒数日 名称 日期 — 倒数日</li>
          <li>/倒数日列表 / /倒数日删除 ID</li>
          <li>/总结 [条数] — AI 群聊摘要</li>
        </ul></div>
        <div class="preview-box"><h4>👥 人设 / 关键词 / 欢迎</h4><ul>
          <li>/人设列表 — 查看所有人设</li>
          <li>/人设预览 名称 — 预览人设</li>
          <li>/人设切换 名称 — 切换人设(管理员)</li>
          <li>/关键词添加 关键词 回复(管理员)</li>
          <li>/关键词列表 / /关键词删除 ID</li>
          <li>/设置欢迎语 内容(管理员)</li>
          <li>/查看欢迎语 / /清除欢迎语</li>
          <li>/设置验证 问题 答案(管理员)</li>
        </ul></div>
        <div class="preview-box"><h4>🛡️ 群管（管理员）</h4><ul>
          <li>/禁言 @用户 分钟 — 禁言成员</li>
          <li>/解禁 @用户 — 解除禁言</li>
          <li>/踢 @用户 — 踢出成员</li>
          <li>/全员禁言 / /解除全员禁言</li>
          <li>/群名 新名称 — 修改群名</li>
          <li>/群信息 — 查看群信息</li>
          <li>/成员信息 @用户 — 成员详情</li>
          <li>/禁言列表 — 查看禁言中成员</li>
          <li>/群牌 @用户 名片 — 设置群名片</li>
          <li>/头衔 @用户 头衔 — 专属头衔(群主)</li>
          <li>/设置管理 @用户 — 设管理员(群主)</li>
          <li>/取消管理 @用户 — 取消管理员(群主)</li>
        </ul></div>
        <div class="preview-box"><h4>👑 主人系统</h4><ul>
          <li>/主人 — 查看主人列表</li>
          <li>/设置主人 — 绑定一级主人</li>
          <li>/设置二级主人 QQ号(一级主人)</li>
          <li>/移除二级主人 QQ号(一级主人)</li>
        </ul></div>
        <div class="preview-box"><h4>🎬 媒体解析</h4><ul>
          <li>/解析 URL — 解析媒体链接</li>
          <li>支持: B站(bilibili/b23.tv)</li>
          <li>支持: 抖音(douyin.com)</li>
          <li>支持: 快手(kuaishou.com)</li>
          <li>自动下载无水印视频发送</li>
        </ul></div>
      </div>
    """

    # ═══════════════════════════════════════════════════
    #  数据管理面板
    # ═══════════════════════════════════════════════════
    votes_data = list_votes(10)
    quotes_data_list = list_quotes_data(10)
    countdowns_data = list_countdowns_data(10)
    scheduled_data = list_scheduled_msgs_data(10)
    keywords_data = list_keyword_rules_data(15)
    events_data = list_calendar_events_data(10)

    _ts = 'style="width:100%;border-collapse:collapse;font-size:13px;"'
    _th = 'style="text-align:left;padding:8px 10px;border-bottom:1px solid var(--line-strong);color:var(--muted);font-size:12px;"'
    _td = 'style="padding:8px 10px;border-bottom:1px solid var(--line);"'

    votes_rows = ''.join(
        f'<tr><td {_td}>{v["id"]}</td><td {_td}>{escape(v["question"][:30])}</td><td {_td}>{len(v["options"])}</td><td {_td}>{v["vote_count"]}</td><td {_td}>{v["status"]}</td></tr>'
        for v in votes_data
    ) or f'<tr><td {_td} colspan="5" style="text-align:center;color:var(--muted)">暂无投票数据</td></tr>'

    quotes_rows = ''.join(
        f'<tr><td {_td}>{q["id"]}</td><td {_td}>{escape(q["content"][:40])}</td><td {_td}>{escape(q["author"])}</td><td {_td}>{q["created_at"]}</td></tr>'
        for q in quotes_data_list
    ) or f'<tr><td {_td} colspan="4" style="text-align:center;color:var(--muted)">暂无语录数据</td></tr>'

    countdowns_rows = ''.join(
        f'<tr><td {_td}>{c["id"]}</td><td {_td}>{escape(c["name"])}</td><td {_td}>{c["target_date"]}</td><td {_td}>{c["days_left"]}天</td></tr>'
        for c in countdowns_data
    ) or f'<tr><td {_td} colspan="4" style="text-align:center;color:var(--muted)">暂无倒数日数据</td></tr>'

    scheduled_rows = ''.join(
        f'<tr><td {_td}>{m["id"]}</td><td {_td}>{escape(m["content"][:30])}</td><td {_td}><code>{m["cron_expr"]}</code></td><td {_td}>{"✅" if m["enabled"] else "⏸"}</td></tr>'
        for m in scheduled_data
    ) or f'<tr><td {_td} colspan="4" style="text-align:center;color:var(--muted)">暂无定时消息</td></tr>'

    keywords_rows = ''.join(
        f'<tr><td {_td}>{r["id"]}</td><td {_td}>{escape(r["pattern"][:20])}</td><td {_td}>{"正则" if r["is_regex"] else "精确"}</td><td {_td}>{r["replies_count"]}</td><td {_td}>{r["cooldown"]}s</td></tr>'
        for r in keywords_data
    ) or f'<tr><td {_td} colspan="5" style="text-align:center;color:var(--muted)">暂无关键词规则</td></tr>'

    events_rows = ''.join(
        f'<tr><td {_td}>{e["id"]}</td><td {_td}>{escape(e["title"][:25])}</td><td {_td}>{e["event_time"]}</td><td {_td}>{e["location"]}</td></tr>'
        for e in events_data
    ) or f'<tr><td {_td} colspan="4" style="text-align:center;color:var(--muted)">暂无日程数据</td></tr>'

    data_panel = f"""
      {_section_title('数据管理', '查看数据库中的各类数据。仅展示最近记录。')}
      <div class="preview-box" style="margin-bottom:14px">
        <h4>📊 投票数据（最近 10 条）</h4>
        <table {_ts}><tr><th {_th}>ID</th><th {_th}>问题</th><th {_th}>选项</th><th {_th}>票数</th><th {_th}>状态</th></tr>
        {votes_rows}</table>
      </div>
      <div class="preview-grid">
        <div class="preview-box">
          <h4>📖 群语录（最近 10 条）</h4>
          <table {_ts}><tr><th {_th}>ID</th><th {_th}>内容</th><th {_th}>作者</th><th {_th}>时间</th></tr>
          {quotes_rows}</table>
        </div>
        <div class="preview-box">
          <h4>⏰ 倒数日</h4>
          <table {_ts}><tr><th {_th}>ID</th><th {_th}>名称</th><th {_th}>目标日期</th><th {_th}>剩余</th></tr>
          {countdowns_rows}</table>
        </div>
      </div>
      <div class="preview-grid" style="margin-top:14px">
        <div class="preview-box">
          <h4>📢 定时消息</h4>
          <table {_ts}><tr><th {_th}>ID</th><th {_th}>内容</th><th {_th}>Cron</th><th {_th}>状态</th></tr>
          {scheduled_rows}</table>
        </div>
        <div class="preview-box">
          <h4>🔑 关键词规则</h4>
          <table {_ts}><tr><th {_th}>ID</th><th {_th}>关键词</th><th {_th}>模式</th><th {_th}>回复数</th><th {_th}>冷却</th></tr>
          {keywords_rows}</table>
        </div>
      </div>
      <div class="preview-box" style="margin-top:14px">
        <h4>📅 日程事件（最近 10 条）</h4>
        <table {_ts}><tr><th {_th}>ID</th><th {_th}>标题</th><th {_th}>时间</th><th {_th}>地点</th></tr>
        {events_rows}</table>
      </div>
    """

    # ═══════════════════════════════════════════════════
    #  环境变量面板
    # ═══════════════════════════════════════════════════
    messages_panel = """
      {_section_title('消息记录', '同步 NapCat 所有收发消息，实时查看。')}
      <div class="toolbar" style="margin-bottom:12px">
        <button type="button" onclick="loadMsgs()">刷新</button>
        <button type="button" onclick="loadMsgs('', 'in')" class="secondary">仅收到</button>
        <button type="button" onclick="loadMsgs('', 'out')" class="secondary">仅发出</button>
        <button type="button" onclick="loadMsgs('', 'system')" class="secondary">系统</button>
        <input id="msg-search" placeholder="搜索内容..." style="padding:6px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--text);width:200px" />
        <button type="button" onclick="loadMsgs(document.getElementById('msg-search').value)" class="warn">搜索</button>
      </div>
      <div id="msg-stats" style="margin-bottom:10px;font-size:13px;color:var(--muted)"></div>
      <div id="msg-container" style="max-height:600px;overflow-y:auto;font-size:12px">
        <table style="width:100%;border-collapse:collapse" id="msg-table">
          <thead><tr>
            <th style="text-align:left;padding:6px 8px;border-bottom:1px solid var(--line-strong);color:var(--muted);font-size:11px;width:140px">时间</th>
            <th style="text-align:left;padding:6px 8px;border-bottom:1px solid var(--line-strong);color:var(--muted);font-size:11px;width:40px">方向</th>
            <th style="text-align:left;padding:6px 8px;border-bottom:1px solid var(--line-strong);color:var(--muted);font-size:11px;width:60px">类型</th>
            <th style="text-align:left;padding:6px 8px;border-bottom:1px solid var(--line-strong);color:var(--muted);font-size:11px;width:100px">群/用户</th>
            <th style="text-align:left;padding:6px 8px;border-bottom:1px solid var(--line-strong);color:var(--muted);font-size:11px">内容</th>
          </tr></thead>
          <tbody id="msg-tbody"></tbody>
        </table>
      </div>
      <script>
        async function loadMsgs(search, dir) {
          search = search || document.getElementById('msg-search').value || '';
          dir = dir || '';
          try {
            const resp = await fetch('/api/messages?limit=300&direction=' + dir + '&search=' + encodeURIComponent(search));
            const data = await resp.json();
            const msgs = data.messages || [];
            const stats = data.stats || {};
            document.getElementById('msg-stats').innerHTML =
              '📊 收到: ' + stats.incoming + ' | 发出: ' + stats.outgoing + ' | 系统: ' + stats.system + ' | 总计: ' + stats.total;
            const tbody = document.getElementById('msg-tbody');
            if (!msgs.length) { tbody.innerHTML = '<tr><td colspan="5" style="padding:20px;text-align:center;color:var(--muted)">暂无消息记录</td></tr>'; return; }
            const dirIcons = {'in':'📥','out':'📤','system':'⚙️'};
            const dirColors = {'in':'#4caf50','out':'#2196f3','system':'#ff9800'};
            tbody.innerHTML = msgs.reverse().map(m =>
              '<tr style="border-bottom:1px solid var(--line)">' +
              '<td style="padding:5px 8px;color:var(--muted);white-space:nowrap">' + (m.time_str||'') + '</td>' +
              '<td style="padding:5px 8px;color:' + (dirColors[m.direction]||'#999') + '">' + (dirIcons[m.direction]||'?') + '</td>' +
              '<td style="padding:5px 8px"><code style="font-size:11px">' + (m.type||'') + '</code></td>' +
              '<td style="padding:5px 8px;font-size:11px">' + (m.group_id ? '群'+m.group_id : '') + (m.user_id ? ' '+m.user_id : '') + '</td>' +
              '<td style="padding:5px 8px;word-break:break-all;max-width:400px;overflow:hidden;text-overflow:ellipsis">' + ((m.content||'').replace(/</g,'&lt;').substring(0,200)) + '</td>' +
              '</tr>'
            ).join('');
          } catch(e) { console.error(e); }
        }
        loadMsgs();
        setInterval(() => loadMsgs(), 10000);
      </script>
    """

    logs_panel = """
      {_section_title('运行日志', '查看机器人最近的运行日志。自动每天轮转，保留30天。')}
      <div class="toolbar" style="margin-bottom:12px">
        <button type="button" onclick="loadLogs(100)">最近 100 行</button>
        <button type="button" onclick="loadLogs(500)" class="secondary">最近 500 行</button>
        <button type="button" onclick="loadLogs(0)" class="secondary">全部</button>
        <button type="button" onclick="loadLogs(100)" class="warn">刷新</button>
      </div>
      <pre id="log-container" style="background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:12px;max-height:500px;overflow-y:auto;font-size:12px;line-height:1.6;white-space:pre-wrap;word-break:break-all;color:var(--text);">点击上方按钮加载日志...</pre>
      <script>
        async function loadLogs(n) {
          const el = document.getElementById('log-container');
          el.textContent = '加载中...';
          try {
            const resp = await fetch('/api/logs?lines=' + n);
            const data = await resp.json();
            el.textContent = data.logs || '暂无日志';
            el.scrollTop = el.scrollHeight;
          } catch(e) {
            el.textContent = '加载失败: ' + e;
          }
        }
      </script>
    """

    envvars_panel = """
      {_section_title('环境变量配置', '管理外部 API Key 和服务地址。修改后需重启机器人生效。')}
      <form method="post" action="/save/envvars" class="stack">
        <div class="field-grid cols-2">
          <div class="field">
            <label>DeepL 翻译 Key</label>
            <input type="password" name="deepl_key" value="" placeholder="留空则保留当前值" />
          </div>
          <div class="field">
            <label>百度翻译 App ID</label>
            <input name="baidu_app_id" value="" placeholder="留空则保留当前值" />
          </div>
        </div>
        <div class="field-grid cols-2">
          <div class="field">
            <label>百度翻译密钥</label>
            <input type="password" name="baidu_secret" value="" placeholder="留空则保留当前值" />
          </div>
          <div class="field">
            <label>SauceNAO 搜图 Key</label>
            <input type="password" name="saucenao_key" value="" placeholder="留空则保留当前值" />
          </div>
        </div>
        <div class="field-grid cols-2">
          <div class="field">
            <label>GitHub Token</label>
            <input type="password" name="github_token" value="" placeholder="留空则保留当前值" />
          </div>
          <div class="field">
            <label>网易云音乐 API 地址</label>
            <input name="netease_api" value="" placeholder="留空则保留当前值" />
          </div>
        </div>
        <p class="subtle">所有 Key 均为可选。留空表示不修改当前值。修改后需重启机器人生效。</p>
        <div class="toolbar">
          <button type="submit">保存环境变量</button>
        </div>
      </form>
    """

    return f"""
<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>QQ AI Bot WebUI</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg-a: #fff8fb;
      --bg-b: #ffeef5;
      --bg-c: #ffddea;
      --bg-d: #ffbfd8;
      --bg-e: #ffd7cc;
      --panel: rgba(255, 247, 251, 0.62);
      --panel-strong: rgba(255, 244, 250, 0.8);
      --panel-soft: rgba(255, 255, 255, 0.38);
      --line: rgba(196, 116, 154, 0.13);
      --line-strong: rgba(196, 116, 154, 0.22);
      --text: #71344a;
      --muted: #bd7a95;
      --primary: #f49fbe;
      --primary-strong: #e47aa6;
      --success: #2e9b67;
      --danger: #d45858;
      --warning: #d98a24;
      --shadow: 0 26px 60px rgba(209, 122, 160, 0.14);
      --shadow-hover: 0 32px 80px rgba(209, 122, 160, 0.18);
      --radius: 26px;
      --radius-sm: 16px;
    }}

    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    html, body {{ margin: 0; padding: 0; }}
    body {{
      font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 12% 16%, rgba(255,255,255,.72), transparent 20%),
        radial-gradient(circle at 84% 10%, rgba(255,226,238,.58), transparent 24%),
        radial-gradient(circle at 72% 70%, rgba(255,188,214,.28), transparent 24%),
        radial-gradient(circle at 18% 82%, rgba(255,222,208,.26), transparent 22%),
        linear-gradient(140deg, var(--bg-a) 0%, var(--bg-b) 20%, var(--bg-c) 48%, var(--bg-e) 74%, var(--bg-d) 100%);
      background-attachment: fixed;
      min-height: 100vh;
      padding: 22px;
      overflow-x: hidden;
    }}

    body::before,
    body::after {{
      content: "";
      position: fixed;
      inset: auto;
      width: 360px;
      height: 360px;
      border-radius: 50%;
      filter: blur(72px);
      pointer-events: none;
      z-index: 0;
      animation: liquidFloat 14s ease-in-out infinite;
    }}

    body::before {{
      top: -80px;
      left: -70px;
      background: radial-gradient(circle, rgba(255, 250, 252, .99) 0%, rgba(255, 228, 238, .58) 48%, rgba(255, 228, 238, 0) 74%);
    }}

    body::after {{
      right: -100px;
      bottom: -90px;
      background: radial-gradient(circle, rgba(255, 182, 212, .44) 0%, rgba(255, 220, 210, .34) 42%, rgba(255, 220, 210, 0) 74%);
      animation-delay: -5s;
      animation-duration: 18s;
    }}

    .liquid-orb {{
      position: fixed;
      border-radius: 50%;
      filter: blur(68px);
      pointer-events: none;
      z-index: 0;
      mix-blend-mode: screen;
      opacity: .48;
      animation: liquidFloat 16s ease-in-out infinite;
    }}

    .orb-a {{
      width: 260px;
      height: 260px;
      top: 16%;
      right: 18%;
      background: radial-gradient(circle, rgba(255, 232, 240, .78) 0%, rgba(255, 198, 220, .38) 48%, rgba(255, 198, 220, 0) 72%);
      animation-delay: -3s;
    }}

    .orb-b {{
      width: 220px;
      height: 220px;
      left: 12%;
      bottom: 16%;
      background: radial-gradient(circle, rgba(255, 222, 213, .66) 0%, rgba(255, 186, 210, .32) 46%, rgba(255, 186, 210, 0) 72%);
      animation-delay: -9s;
      animation-duration: 20s;
    }}

    @keyframes liquidFloat {{
      0%, 100% {{ transform: translate3d(0, 0, 0) scale(1); }}
      25% {{ transform: translate3d(18px, -14px, 0) scale(1.06); }}
      50% {{ transform: translate3d(-12px, 20px, 0) scale(.95); }}
      75% {{ transform: translate3d(16px, 10px, 0) scale(1.04); }}
    }}

    @keyframes shimmer {{
      0% {{ transform: translateX(-140%) rotate(12deg); opacity: 0; }}
      28% {{ opacity: .46; }}
      60% {{ opacity: .18; }}
      100% {{ transform: translateX(180%) rotate(12deg); opacity: 0; }}
    }}

    @keyframes pulseGlow {{
      0%, 100% {{ box-shadow: 0 0 0 0 rgba(239, 147, 178, 0); }}
      50% {{ box-shadow: 0 0 0 8px rgba(239, 147, 178, .08); }}
    }}

    @keyframes noticeRise {{
      from {{ transform: translateY(8px); opacity: 0; }}
      to {{ transform: translateY(0); opacity: 1; }}
    }}

    .app-shell {{
      position: relative;
      z-index: 1;
      max-width: 1500px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 300px minmax(0, 1fr);
      gap: 20px;
      align-items: start;
    }}

    .sidebar {{
      position: sticky;
      top: 20px;
      display: grid;
      gap: 18px;
    }}

    .side-panel, .content-panel, .accordion, .summary-card {{
      backdrop-filter: blur(22px);
      -webkit-backdrop-filter: blur(22px);
    }}

    .side-panel {{
      position: relative;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,.42), rgba(255,244,249,.56));
      border-radius: 30px;
      box-shadow: var(--shadow);
      overflow: hidden;
      transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease;
    }}

    .side-panel:hover {{
      transform: translateY(-3px);
      box-shadow: var(--shadow-hover);
      border-color: rgba(239,147,178,.18);
    }}

    .side-panel::after,
    .content-panel::after,
    .summary-card::after,
    .accordion::after,
    .mcp-server::after,
    .preview-box::after,
    .metric::after,
    .kv-item::after {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(120deg, transparent 8%, rgba(255,255,255,.36) 26%, transparent 44%);
      transform: translateX(-140%) rotate(12deg);
      pointer-events: none;
      opacity: 0;
    }}

    .side-panel:hover::after,
    .content-panel:hover::after,
    .summary-card:hover::after,
    .accordion:hover::after,
    .mcp-server:hover::after,
    .preview-box:hover::after,
    .metric:hover::after,
    .kv-item:hover::after {{
      animation: shimmer 1.6s ease;
    }}

    .brand-panel {{ padding: 24px; }}
    .brand-chip {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,.46);
      border: 1px solid rgba(222, 111, 152, .12);
      color: var(--primary-strong);
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 14px;
      animation: pulseGlow 3.8s ease-in-out infinite;
    }}

    .brand-panel h1 {{ margin: 0 0 10px; font-size: 30px; line-height: 1.05; letter-spacing: -.03em; }}
    .brand-panel p {{ margin: 0; color: var(--muted); line-height: 1.75; font-size: 14px; }}

    .side-divider {{ height: 1px; background: linear-gradient(90deg, transparent, rgba(209,122,160,.18), transparent); margin: 0 20px; }}
    .nav-panel, .side-info {{ padding: 20px; }}
    .nav-panel h3, .side-info h3 {{ margin: 0 0 12px; font-size: 15px; }}

    .nav-list {{ display: grid; gap: 10px; }}
    .nav-link {{
      position: relative;
      display: flex;
      align-items: center;
      justify-content: space-between;
      text-decoration: none;
      padding: 13px 14px;
      border-radius: 16px;
      color: var(--text);
      background: linear-gradient(135deg, rgba(255,255,255,.42), rgba(255,242,248,.68));
      border: 1px solid rgba(209,122,160,.08);
      transition: transform .22s ease, background .22s ease, border-color .22s ease, box-shadow .22s ease;
      overflow: hidden;
    }}

    .nav-link:hover {{
      transform: translateX(4px) translateY(-1px);
      background: linear-gradient(135deg, rgba(255,255,255,.72), rgba(255,234,242,.86));
      border-color: rgba(239,147,178,.24);
      box-shadow: 0 12px 28px rgba(222,111,152,.08);
    }}

    .nav-link::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(120deg, transparent 10%, rgba(255,255,255,.34) 30%, transparent 46%);
      transform: translateX(-140%) rotate(12deg);
    }}

    .nav-link:hover::before {{ animation: shimmer 1.4s ease; }}
    .nav-link::after {{ content: "→"; color: var(--muted); }}

    .mini-list {{ display: grid; gap: 10px; }}
    .mini-item {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 13px;
      border-radius: 15px;
      background: linear-gradient(135deg, rgba(255,255,255,.4), rgba(255,244,249,.58));
      border: 1px solid rgba(209,122,160,.08);
      font-size: 13px;
      transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
    }}

    .mini-item:hover {{
      transform: translateY(-2px);
      box-shadow: 0 12px 24px rgba(209,122,160,.08);
      border-color: rgba(239,147,178,.16);
    }}

    .mini-item span:last-child {{ color: var(--muted); text-align: right; }}

    .content-panel {{
      position: relative;
      border: 1px solid var(--line);
      border-radius: 34px;
      background:
        radial-gradient(circle at 10% 8%, rgba(255,255,255,.38), transparent 18%),
        radial-gradient(circle at 92% 12%, rgba(255,230,239,.34), transparent 20%),
        linear-gradient(180deg, rgba(255,250,252,.56), rgba(255,240,247,.7));
      box-shadow: var(--shadow);
      padding: 22px;
      overflow: hidden;
      transition: transform .24s ease, box-shadow .24s ease, border-color .24s ease;
    }}

    .content-panel:hover {{
      transform: translateY(-2px);
      box-shadow: var(--shadow-hover);
      border-color: rgba(239,147,178,.18);
    }}

    .hero {{
      position: relative;
      overflow: hidden;
      padding: 28px;
      border-radius: 28px;
      background:
        radial-gradient(circle at 12% 18%, rgba(255,255,255,.66), transparent 24%),
        radial-gradient(circle at 88% 18%, rgba(255,220,234,.66), transparent 24%),
        radial-gradient(circle at 65% 100%, rgba(255,210,205,.26), transparent 24%),
        linear-gradient(135deg, rgba(255,252,253,.9), rgba(255,238,245,.82), rgba(255,220,232,.8));
      border: 1px solid rgba(209,122,160,.12);
      display: grid;
      grid-template-columns: 1.2fr .9fr;
      gap: 18px;
      margin-bottom: 18px;
      box-shadow: 0 18px 34px rgba(209,122,160,.08);
    }}

    .hero::before {{
      content: "";
      position: absolute;
      width: 220px;
      height: 220px;
      right: -40px;
      top: -50px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255,255,255,.44) 0%, rgba(255,255,255,0) 72%);
      filter: blur(8px);
      animation: liquidFloat 12s ease-in-out infinite;
      pointer-events: none;
    }}

    .hero h2 {{ margin: 0 0 10px; font-size: 34px; line-height: 1.08; letter-spacing: -.03em; }}
    .hero p {{ margin: 0; color: var(--muted); line-height: 1.8; }}
    .hero-tags {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,.54);
      border: 1px solid rgba(222,111,152,.1);
      font-size: 12px;
      color: var(--primary-strong);
      font-weight: 700;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.45);
    }}

    .hero-metrics {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px; }}
    .metric {{
      position: relative;
      padding: 16px;
      border-radius: 20px;
      background: linear-gradient(145deg, rgba(255,255,255,.46), rgba(255,242,248,.62));
      border: 1px solid rgba(209,122,160,.1);
      min-height: 94px;
      transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease;
      overflow: hidden;
    }}

    .metric:hover {{
      transform: translateY(-4px);
      box-shadow: 0 18px 32px rgba(209,122,160,.1);
      border-color: rgba(239,147,178,.18);
    }}

    .metric .label {{ color: var(--muted); font-size: 12px; margin-bottom: 10px; text-transform: uppercase; letter-spacing: .08em; }}
    .metric .value {{ font-size: 16px; font-weight: 700; line-height: 1.5; word-break: break-word; }}

    .summary-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-bottom: 18px; }}
    .summary-card {{
      position: relative;
      padding: 18px;
      border-radius: 22px;
      border: 1px solid rgba(209,122,160,.12);
      background: linear-gradient(180deg, rgba(255,255,255,.5), rgba(255,242,248,.68));
      box-shadow: 0 16px 30px rgba(209,122,160,.08);
      overflow: hidden;
      transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease;
    }}

    .summary-card:hover {{
      transform: translateY(-5px);
      box-shadow: 0 22px 40px rgba(209,122,160,.12);
      border-color: rgba(239,147,178,.18);
    }}

    .summary-card.highlight {{ background: linear-gradient(180deg, rgba(255,248,252,.66), rgba(255,220,234,.84)); }}
    .summary-card.success {{ background: linear-gradient(180deg, rgba(241,255,248,.58), rgba(216,245,227,.82)); }}
    .summary-card.warning {{ background: linear-gradient(180deg, rgba(255,241,244,.64), rgba(255,214,224,.8)); }}
    .summary-title {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 10px; }}
    .summary-value {{ font-size: 29px; font-weight: 800; line-height: 1.1; margin-bottom: 8px; }}
    .summary-sub {{ color: var(--muted); font-size: 13px; line-height: 1.65; }}

    .notice {{
      margin-bottom: 18px;
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid;
      animation: noticeRise .34s ease;
    }}

    .notice.success {{ background: rgba(232, 252, 241, .88); border-color: rgba(46,155,103,.26); color: #256847; }}
    .notice.error {{ background: rgba(255, 235, 235, .88); border-color: rgba(212,88,88,.28); color: #9b3232; }}

    .accordion-stack {{ display: grid; gap: 16px; }}
    .accordion {{
      position: relative;
      border-radius: 24px;
      border: 1px solid rgba(209,122,160,.12);
      background: linear-gradient(180deg, rgba(255,255,255,.4), rgba(255,244,249,.6));
      box-shadow: 0 14px 28px rgba(209,122,160,.08);
      overflow: hidden;
      transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease, background .22s ease;
    }}

    .accordion:hover {{
      transform: translateY(-3px);
      box-shadow: 0 22px 36px rgba(209,122,160,.12);
      border-color: rgba(239,147,178,.18);
      background: linear-gradient(180deg, rgba(255,255,255,.46), rgba(255,240,247,.66));
    }}

    .accordion[open] {{
      box-shadow: 0 24px 42px rgba(209,122,160,.12);
      border-color: rgba(239,147,178,.2);
    }}

    .accordion summary {{
      list-style: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 18px 22px;
      user-select: none;
      transition: background .2s ease, transform .18s ease;
      position: relative;
      overflow: hidden;
    }}
    .accordion summary::-webkit-details-marker {{ display: none; }}

    .accordion summary::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(120deg, transparent 10%, rgba(255,255,255,.32) 28%, transparent 44%);
      transform: translateX(-140%) rotate(12deg);
      pointer-events: none;
    }}

    .accordion summary:hover::before {{ animation: shimmer 1.4s ease; }}
    .accordion summary:hover {{ background: rgba(255,255,255,.14); }}
    .accordion summary:active {{ transform: scale(.995); }}

    .accordion-title-wrap {{ display: flex; flex-direction: column; gap: 6px; }}
    .accordion-title {{ font-size: 20px; font-weight: 800; }}
    .accordion-meta {{ color: var(--muted); font-size: 13px; }}
    .accordion-arrow {{
      color: var(--muted);
      font-size: 22px;
      transition: transform .24s ease, color .2s ease;
    }}
    .accordion:hover .accordion-arrow {{ color: var(--primary-strong); }}
    .accordion[open] .accordion-arrow {{ transform: rotate(180deg); }}
    .accordion-body {{ padding: 0 22px 22px; }}

    .section-head {{ margin-bottom: 18px; }}
    .section-head h2 {{ margin: 0 0 6px; font-size: 22px; }}
    .section-head p {{ margin: 0; color: var(--muted); line-height: 1.7; font-size: 14px; }}

    .status-row {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 14px; margin-top: 16px; }}
    .kv-item {{
      position: relative;
      padding: 16px;
      border-radius: 18px;
      background: linear-gradient(145deg, rgba(255,255,255,.4), rgba(255,244,249,.58));
      border: 1px solid rgba(209,122,160,.1);
      transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease;
      overflow: hidden;
    }}

    .kv-item:hover {{
      transform: translateY(-3px);
      box-shadow: 0 16px 28px rgba(209,122,160,.09);
      border-color: rgba(239,147,178,.18);
    }}

    .kv-label {{ color: var(--muted); font-size: 12px; margin-bottom: 10px; text-transform: uppercase; letter-spacing: .08em; }}
    .kv-value {{ font-size: 15px; font-weight: 700; line-height: 1.6; word-break: break-word; }}

    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 12px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 700;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.44);
    }}
    .status-badge::before {{ content: ""; width: 8px; height: 8px; border-radius: 999px; background: currentColor; box-shadow: 0 0 10px currentColor; }}
    .status-badge.ok {{ background: rgba(224, 249, 235, .96); color: #287e55; }}
    .status-badge.off {{ background: rgba(245, 236, 230, .96); color: #9f6d54; }}

    .field-grid {{ display: grid; gap: 14px; }}
    .cols-2 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .cols-3 {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .field {{ display: grid; gap: 8px; }}
    .stack {{ display: grid; gap: 16px; }}

    label {{ font-size: 13px; color: var(--text); font-weight: 700; }}
    input, textarea, select {{
      width: 100%;
      border: 1px solid var(--line-strong);
      border-radius: 15px;
      background: linear-gradient(180deg, rgba(255,255,255,.68), rgba(255,248,251,.88));
      color: var(--text);
      padding: 12px 14px;
      font-size: 14px;
      outline: none;
      transition: border-color .2s ease, box-shadow .2s ease, background .2s ease, transform .16s ease;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.5);
    }}

    input:hover, textarea:hover, select:hover {{
      border-color: rgba(239,147,178,.2);
      background: linear-gradient(180deg, rgba(255,255,255,.76), rgba(255,245,249,.92));
    }}

    input:focus, textarea:focus, select:focus {{
      border-color: rgba(239,147,178,.4);
      box-shadow: 0 0 0 4px rgba(239,147,178,.12), 0 12px 22px rgba(222,111,152,.06);
      background: rgba(255,255,255,.88);
      transform: translateY(-1px);
    }}

    textarea {{ min-height: 124px; resize: vertical; line-height: 1.55; }}
    code {{ background: rgba(255,255,255,.5); padding: 2px 8px; border-radius: 8px; }}
    .subtle {{ color: var(--muted); font-size: 13px; line-height: 1.8; }}

    .toolbar {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 18px; }}
    .toolbar.split {{ justify-content: space-between; }}
    .inline-form {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
    .inline-form input[type='number'] {{ width: 130px; }}

    button {{
      position: relative;
      overflow: hidden;
      border: 0;
      border-radius: 15px;
      padding: 11px 16px;
      background: linear-gradient(135deg, #f7b6cc, #f49fbe 54%, #e47aa6 100%);
      color: white;
      cursor: pointer;
      font-weight: 700;
      font-size: 14px;
      transition: transform .18s ease, box-shadow .18s ease, opacity .18s ease, filter .18s ease;
      box-shadow: 0 14px 28px rgba(222,111,152,.18);
    }}

    button::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(120deg, transparent 12%, rgba(255,255,255,.34) 34%, transparent 54%);
      transform: translateX(-140%) rotate(12deg);
      pointer-events: none;
    }}

    button:hover {{
      transform: translateY(-2px) scale(1.01);
      box-shadow: 0 18px 34px rgba(222,111,152,.22);
      filter: saturate(1.05);
    }}

    button:hover::before {{ animation: shimmer 1.2s ease; }}
    button:active {{ transform: translateY(0) scale(.985); }}

    button.secondary {{
      background: linear-gradient(135deg, rgba(255,255,255,.86), rgba(255,244,248,.96));
      color: var(--text);
      box-shadow: 0 10px 22px rgba(209,122,160,.06);
      border: 1px solid rgba(209,122,160,.1);
    }}
    button.warn {{ background: linear-gradient(135deg, #f6c0be, #f3a3b7 58%, #e489ad 100%); box-shadow: 0 14px 28px rgba(207,123,34,.16); }}
    button.danger {{ background: linear-gradient(135deg, #ef9b8b, #de6762 58%, #c94d5d 100%); box-shadow: 0 14px 28px rgba(212,88,88,.16); }}

    .chip {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      color: var(--primary-strong);
      background: rgba(255,255,255,.56);
      border: 1px solid rgba(222,111,152,.1);
      box-shadow: inset 0 1px 0 rgba(255,255,255,.5);
    }}

    .preview-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 14px; }}
    .preview-box, .mcp-server {{
      position: relative;
      padding: 16px;
      border-radius: 20px;
      background: linear-gradient(145deg, rgba(255,255,255,.46), rgba(255,243,248,.64));
      border: 1px solid rgba(209,122,160,.1);
      transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease;
      overflow: hidden;
    }}

    .preview-box:hover, .mcp-server:hover {{
      transform: translateY(-4px);
      box-shadow: 0 18px 32px rgba(209,122,160,.1);
      border-color: rgba(239,147,178,.18);
    }}

    .preview-box h4 {{ margin: 0 0 10px; font-size: 14px; }}
    .preview-box ul {{ margin: 0; padding-left: 18px; }}
    .preview-box li {{ margin: 0 0 6px; line-height: 1.55; }}
    .empty-hint {{ color: var(--muted); font-size: 13px; }}

    .mcp-stack {{ display: grid; gap: 16px; }}
    .mcp-head {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }}
    .mcp-head h3 {{ margin: 0; font-size: 18px; }}
    .mcp-head p {{ margin: 6px 0 0; color: var(--muted); font-size: 13px; }}

    @media (max-width: 1220px) {{
      .app-shell {{ grid-template-columns: 1fr; }}
      .sidebar {{ position: static; }}
    }}

    @media (max-width: 980px) {{
      .hero, .summary-grid, .status-row, .cols-2, .cols-3, .preview-grid {{ grid-template-columns: 1fr; }}
      .hero-metrics {{ grid-template-columns: 1fr 1fr; }}
    }}

    @media (max-width: 760px) {{
      body {{ padding: 12px; }}
      .liquid-orb {{ display: none; }}
      .content-panel {{ padding: 14px; border-radius: 24px; }}
      .hero {{ padding: 18px; }}
      .hero h2 {{ font-size: 28px; }}
      .hero-metrics {{ grid-template-columns: 1fr; }}
      .accordion summary {{ padding: 16px; }}
      .accordion-body {{ padding: 0 16px 16px; }}
      .inline-form input[type='number'] {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <div class=\"liquid-orb orb-a\"></div>
  <div class=\"liquid-orb orb-b\"></div>
  <div class=\"app-shell\">
    <aside class=\"sidebar\">
      <section class=\"side-panel\">
        <div class=\"brand-panel\">
          <span class=\"brand-chip\">Warm Liquid Console</span>
          <h1>QQ AI Bot</h1>
          <p>当前界面采用左侧常驻导航与右侧折叠式工作面板的双栏结构，用于提升配置定位效率与日常操作的可管理性。</p>
        </div>
        <div class=\"side-divider\"></div>
        <div class=\"nav-panel\">
          <h3>导航</h3>
          <div class=\"nav-list\">
            {_nav_link('总览', 'hero')}
            {_nav_link('运行状态', 'runtime')}
            {_nav_link('基础配置', 'settings')}
            {_nav_link('人设编辑', 'persona')}
            {_nav_link('MCP 配置', 'mcp')}
            {_nav_link('工具总览', 'tools')}
            {_nav_link('命令速查', 'commands')}
            {_nav_link('数据管理', 'data')}
            {_nav_link('环境变量', 'envvars')}
          </div>
        </div>
        <div class=\"side-divider\"></div>
        <div class=\"side-info\">
          <h3>当前摘要</h3>
          <div class=\"mini-list\">
            <div class=\"mini-item\"><span>默认模型</span><span>{escape(str(form['default_model']))}</span></div>
            <div class=\"mini-item\"><span>默认人设</span><span>{escape(str(form['default_persona']))}</span></div>
            <div class=\"mini-item\"><span>MCP 数量</span><span>{len(mcp_servers)}</span></div>
            <div class=\"mini-item\"><span>唤醒词</span><span>{trigger_count}</span></div>
          </div>
        </div>
      </section>
    </aside>

    <main class=\"content-panel\">
      <section class=\"hero\" id=\"hero\">
        <div>
          <div class=\"hero-tags\">
            <span class=\"pill\">WebUI v2.0.0</span>
            <span class=\"pill\">左侧导航</span>
            <span class=\"pill\">折叠面板</span>
            <span class=\"pill\">暖色液态渐变</span>
          </div>
          <h2>把配置页做成更顺手、更柔和的运维台。</h2>
          <p>现在的布局重点不再是“所有东西一股脑摊开”，而是让导航固定在左侧，主区通过折叠逐块展开。这样信息密度更高，但视觉压力更小，日常操作也更聚焦。</p>
        </div>
        <div class=\"hero-metrics\">
          <div class=\"metric\">
            <div class=\"label\">机器人状态</div>
            <div class=\"value\">{bot_status}</div>
          </div>
          <div class=\"metric\">
            <div class=\"label\">WebUI 状态</div>
            <div class=\"value\">{webui_status}</div>
          </div>
          <div class=\"metric\">
            <div class=\"label\">当前人设</div>
            <div class=\"value\">{escape(str(persona['file_name']))}</div>
          </div>
          <div class=\"metric\">
            <div class=\"label\">NapCat WS</div>
            <div class=\"value\"><code>{escape(str(runtime['ws_url']))}</code></div>
          </div>
        </div>
      </section>

      <section class=\"summary-grid\">
        {_summary_card('已加载人设', str(len(personas)), f'当前编辑：{escape(str(persona["file_name"]))}', 'highlight')}
        {_summary_card('MCP Servers', str(len(mcp_servers)), '当前配置中的工具接入数量', 'success')}
        {_summary_card('活跃开关', str(active_features), 'AI / Tool / Memory / MCP 四项统计', 'warning')}
        {_summary_card('唤醒词', str(trigger_count), '当前生效的 trigger_prefixes 数量')}
      </section>
      <section class="summary-grid">
        {_summary_card('注册用户', str(stats['users']), '数据库中的用户总数')}
        {_summary_card('群组', str(stats['groups']), '已记录的群组数量')}
        {_summary_card('投票', str(stats['votes']), '创建的投票总数')}
        {_summary_card('语录', str(stats['quotes']), '收录的群语录数')}
      </section>

      {notice}

      <section class=\"accordion-stack\">
        {_accordion('运行状态与控制', 'runtime', runtime_panel, True, '启动 / 停止 / 重启')}
        {_accordion('基础配置', 'settings', settings_panel, True, '环境 / 模型 / 开关')}
        {_accordion('人设编辑', 'persona', persona_panel, False, '切换 / 预览 / 保存')}
        {_accordion('MCP 可视化配置', 'mcp', mcp_panel, False, '工具接入 / transport / args')}
        {_accordion('工具总览', 'tools', tools_panel, False, '53 个已注册工具')}
        {_accordion('命令速查', 'commands', commands_panel, False, '全部可用命令（含群管/主人/媒体）')}
        {_accordion('数据管理', 'data', data_panel, False, '投票 / 语录 / 日程 / 关键词')}
        {_accordion('消息记录', 'messages', messages_panel, False, '收发消息实时同步')}
        {_accordion('运行日志', 'logs', logs_panel, False, '实时查看机器人日志')}
        {_accordion('环境变量配置', 'envvars', envvars_panel, False, 'API Key 与外部服务')}
      </section>
    </main>
  </div>
</body>
</html>
    """


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    persona: str | None = None,
    saved: str = "",
    mcp_count: int | None = None,
    error: str = "",
):
    return HTMLResponse(render_page(persona, saved, mcp_count, error))


@app.get("/hybridaction/{path:path}")
async def swallow_hybridaction(path: str):
    return Response(content="", media_type="application/javascript")


@app.post("/control/bot/start")
async def control_bot_start():
    await HOST.start_bot()
    return RedirectResponse(url="/?saved=bot_start", status_code=303)


@app.post("/control/bot/stop")
async def control_bot_stop():
    await HOST.stop_bot()
    return RedirectResponse(url="/?saved=bot_stop", status_code=303)


@app.post("/control/bot/restart")
async def control_bot_restart():
    from app.config.config_manager import ConfigManager
    ConfigManager().reload(BASE_DIR / "config.yaml")
    await HOST.restart_bot()
    return RedirectResponse(url="/?saved=bot_restart", status_code=303)


@app.post("/save/settings")
async def save_settings(
    app_env: str = Form(...),
    ws_url: str = Form(...),
    openai_base_url: str = Form(...),
    openai_api_key: str = Form(""),
    default_model: str = Form(...),
    default_persona: str = Form(...),
    max_context_rounds: str = Form(...),
    tool_call_enabled: str = Form(...),
    memory_enabled: str = Form(...),
    trigger_prefixes: str = Form(""),
    feature_ai: str = Form(...),
    mcp_enabled: str = Form(...),
):
    try:
        update_settings_from_form(
            {
                "app_env": app_env,
                "ws_url": ws_url,
                "openai_base_url": openai_base_url,
                "openai_api_key": openai_api_key,
                "default_model": default_model,
                "default_persona": default_persona,
                "max_context_rounds": max_context_rounds,
                "tool_call_enabled": tool_call_enabled,
                "memory_enabled": memory_enabled,
                "trigger_prefixes": trigger_prefixes,
                "feature_ai": feature_ai,
                "mcp_enabled": mcp_enabled,
            }
        )
    except ConfigValidationError as exc:
        query = urlencode({"error": str(exc), "persona": default_persona})
        return RedirectResponse(url=f"/?{query}", status_code=303)

    query = urlencode({"saved": "settings", "persona": default_persona})
    return RedirectResponse(url=f"/?{query}", status_code=303)


@app.post("/save/persona")
async def save_persona(
    persona_file_name: str = Form(...),
    name: str = Form(...),
    style: str = Form(""),
    identity: str = Form(""),
    rules: str = Form(""),
    forbidden: str = Form(""),
):
    try:
        saved_name = update_persona_from_form(
            {
                "persona_file_name": persona_file_name,
                "name": name,
                "style": style,
                "identity": identity,
                "rules": rules,
                "forbidden": forbidden,
            }
        )
    except ConfigValidationError as exc:
        query = urlencode({"error": str(exc), "persona": persona_file_name or "default"})
        return RedirectResponse(url=f"/?{query}", status_code=303)

    query = urlencode({"saved": "persona", "persona": saved_name})
    return RedirectResponse(url=f"/?{query}", status_code=303)


@app.post("/save/mcp")
async def save_mcp(request: Request):
    form = await request.form()
    form_dict = {key: str(value) for key, value in form.items()}
    selected_persona = form_dict.get("persona") or None
    try:
        update_mcp_servers_from_form(form_dict)
    except ConfigValidationError as exc:
        query = urlencode({"error": str(exc), "persona": selected_persona or "default"})
        return RedirectResponse(url=f"/?{query}", status_code=303)
    return RedirectResponse(url="/?saved=mcp", status_code=303)


@app.get("/api/messages")
async def api_messages(limit: int = 200, direction: str = "", group_id: str = "", search: str = ""):
    from app.services.msg_logger import get_messages, get_stats
    return {"messages": get_messages(limit, direction, group_id, search), "stats": get_stats()}


@app.get("/api/logs")
async def api_logs(lines: int = 100):
    """返回最近的日志内容。"""
    import os
    from pathlib import Path
    log_dir = BASE_DIR / "data" / "logs"
    if not log_dir.exists():
        return {"logs": "暂无日志文件。启动机器人后自动生成。"}
    # 找最新的日志文件
    log_files = sorted(log_dir.glob("bot_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not log_files:
        return {"logs": "暂无日志文件。"}
    try:
        all_text = log_files[0].read_text(encoding="utf-8", errors="replace")
        log_lines = all_text.strip().splitlines()
        recent = log_lines[-lines:] if len(log_lines) > lines else log_lines
        return {"logs": "\n".join(recent), "file": log_files[0].name, "total": len(log_lines)}
    except Exception as e:
        return {"logs": f"读取日志失败: {e}"}


@app.post("/save/envvars")
async def save_envvars(request: Request):
    form = await request.form()
    updates = {}
    field_map = {
        "deepl_key": "DEEPL_AUTH_KEY",
        "baidu_app_id": "BAIDU_TRANSLATE_APP_ID",
        "baidu_secret": "BAIDU_TRANSLATE_SECRET",
        "saucenao_key": "SAUCENAO_API_KEY",
        "github_token": "GITHUB_TOKEN",
        "netease_api": "NETEASE_API_BASE",
    }
    for form_key, env_key in field_map.items():
        value = str(form.get(form_key, "")).strip()
        if value:
            updates[env_key] = value
    if updates:
        from app.webui.config_store import write_env_file, read_env_file
        env = read_env_file()
        env.update(updates)
        write_env_file(env)
    return RedirectResponse(url="/?saved=envvars", status_code=303)
