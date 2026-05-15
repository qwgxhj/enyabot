"""内置插件统一注册入口。"""
from __future__ import annotations

from app.plugins.base import ToolRegistry, ToolSpec

# ── API 类插件 ──────────────────────────────────────────
from app.plugins.api.entertainment import kfc_crazy_thursday, random_superpower
from app.plugins.api.identity import name_duplicate_query
from app.plugins.api.ip_lookup import ip_location_query
from app.plugins.api.media import media_parse
from app.plugins.api.weather import weather_query
from app.plugins.api.translator import translate_text
from app.plugins.api.image_search import image_search
from app.plugins.api.music import search_music, get_song_url
from app.plugins.api.meme import generate_meme
from app.plugins.api.github import repo_info, repo_releases

# ── Direct 类插件 ───────────────────────────────────────
from app.plugins.direct.group_admin import kick_member, mute_member
from app.plugins.direct.keyword import add_keyword
from app.plugins.direct.memory import recall_memory, remember_fact
from app.plugins.direct.reminder import create_reminder
from app.plugins.direct.score import query_score, sign_in
from app.plugins.direct.vote import create_vote, cast_vote, vote_result, close_vote
from app.plugins.direct.welcome import set_welcome, get_welcome, clear_welcome, set_verify_question
from app.plugins.direct.scheduler_msg import create_scheduled_message, list_scheduled_messages, delete_scheduled_message, toggle_scheduled_message
from app.plugins.direct.calendar_event import add_event, list_events, delete_event
from app.plugins.direct.keyword_plus import add_keyword_rule, list_keyword_rules, delete_keyword_rule
from app.plugins.direct.games import start_guess, make_guess, start_quiz, answer_quiz
from app.plugins.direct.quote import add_quote, random_quote, search_quote, list_quotes
from app.plugins.direct.countdown import add_countdown, list_countdowns, delete_countdown
from app.plugins.direct.chat_summary import summarize_chat
from app.plugins.direct.persona_switch import list_personas, preview_persona, switch_persona


def register_builtin_tools(registry: ToolRegistry) -> None:
    specs = [
        # ═══════════════════════════════════════════════════
        #  原有插件（保持不变）
        # ═══════════════════════════════════════════════════
        ToolSpec("weather_query", "查询天气",
                 {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
                 "member", weather_query, category="api", source="builtin.api"),
        ToolSpec("create_reminder", "创建提醒任务",
                 {"type": "object", "properties": {"content": {"type": "string"}, "minutes": {"type": "integer"}}, "required": ["content"]},
                 "member", create_reminder, category="direct", source="builtin.direct"),
        ToolSpec("sign_in", "签到",
                 {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]},
                 "member", sign_in, category="direct", source="builtin.direct"),
        ToolSpec("query_score", "查询积分",
                 {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]},
                 "member", query_score, category="direct", source="builtin.direct"),
        ToolSpec("ip_location_query", "查询 IP 归属地",
                 {"type": "object", "properties": {"ip": {"type": "string"}}, "required": ["ip"]},
                 "member", ip_location_query, category="api", source="builtin.api"),
        ToolSpec("random_superpower", "获取随机超能力文案",
                 {"type": "object", "properties": {}},
                 "member", random_superpower, category="api", source="builtin.api"),
        ToolSpec("kfc_crazy_thursday", "获取 KFC 疯狂星期四文案",
                 {"type": "object", "properties": {}},
                 "member", kfc_crazy_thursday, category="api", source="builtin.api"),
        ToolSpec("name_duplicate_query", "查询姓名重名情况",
                 {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                 "member", name_duplicate_query, category="api", source="builtin.api"),
        ToolSpec("media_parse", "解析媒体链接",
                 {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
                 "member", media_parse, category="api", source="builtin.api"),
        ToolSpec("mute_member", "禁言群成员",
                 {"type": "object", "properties": {"group_id": {"type": "string"}, "user_id": {"type": "string"}, "duration": {"type": "integer"}}, "required": ["group_id", "user_id", "duration"]},
                 "admin", mute_member, category="direct", source="builtin.direct"),
        ToolSpec("kick_member", "踢出群成员",
                 {"type": "object", "properties": {"group_id": {"type": "string"}, "user_id": {"type": "string"}}, "required": ["group_id", "user_id"]},
                 "admin", kick_member, category="direct", source="builtin.direct"),
        ToolSpec("add_keyword", "添加关键词回复",
                 {"type": "object", "properties": {"keyword": {"type": "string"}, "reply_content": {"type": "string"}}, "required": ["keyword", "reply_content"]},
                 "admin", add_keyword, category="direct", source="builtin.direct"),
        ToolSpec("remember_fact", "写入长期记忆",
                 {"type": "object", "properties": {"content": {"type": "string"}, "scope_type": {"type": "string"}, "scope_id": {"type": "string"}}, "required": ["content"]},
                 "member", remember_fact, category="direct", source="builtin.direct"),
        ToolSpec("recall_memory", "检索长期记忆",
                 {"type": "object", "properties": {"query": {"type": "string"}, "scope_type": {"type": "string"}, "scope_id": {"type": "string"}}, "required": ["query"]},
                 "member", recall_memory, category="direct", source="builtin.direct"),

        # ═══════════════════════════════════════════════════
        #  新增：翻译插件
        # ═══════════════════════════════════════════════════
        ToolSpec("translate_text", "翻译文本（支持中英日韩法德西俄等多语言互译）",
                 {"type": "object", "properties": {
                     "text": {"type": "string", "description": "待翻译文本"},
                     "target_lang": {"type": "string", "description": "目标语言代码，如 zh/en/ja/ko/fr/de/es/ru"},
                     "source_lang": {"type": "string", "description": "源语言代码，默认 auto 自动检测"},
                 }, "required": ["text"]},
                 "member", translate_text, category="api", source="builtin.api"),

        # ═══════════════════════════════════════════════════
        #  新增：搜图插件
        # ═══════════════════════════════════════════════════
        ToolSpec("image_search", "以图搜图（支持动漫截图、插画识别）",
                 {"type": "object", "properties": {
                     "image_url": {"type": "string", "description": "图片 URL"},
                 }, "required": ["image_url"]},
                 "member", image_search, category="api", source="builtin.api"),

        # ═══════════════════════════════════════════════════
        #  新增：音乐点歌
        # ═══════════════════════════════════════════════════
        ToolSpec("search_music", "搜索音乐/点歌",
                 {"type": "object", "properties": {
                     "keyword": {"type": "string", "description": "歌曲名或歌手名"},
                     "limit": {"type": "integer", "description": "返回数量，默认 3"},
                 }, "required": ["keyword"]},
                 "member", search_music, category="api", source="builtin.api"),

        # ═══════════════════════════════════════════════════
        #  新增：表情包生成
        # ═══════════════════════════════════════════════════
        ToolSpec("generate_meme", "生成表情包（文字表情包）",
                 {"type": "object", "properties": {
                     "top_text": {"type": "string", "description": "上方文字"},
                     "bottom_text": {"type": "string", "description": "下方文字"},
                 }, "required": []},
                 "member", generate_meme, category="api", source="builtin.api"),

        # ═══════════════════════════════════════════════════
        #  新增：GitHub 集成
        # ═══════════════════════════════════════════════════
        ToolSpec("repo_info", "查询 GitHub 仓库信息",
                 {"type": "object", "properties": {
                     "owner": {"type": "string", "description": "仓库所有者"},
                     "repo": {"type": "string", "description": "仓库名"},
                 }, "required": ["owner", "repo"]},
                 "member", repo_info, category="api", source="builtin.api"),
        ToolSpec("repo_releases", "查询 GitHub 仓库最近 Release",
                 {"type": "object", "properties": {
                     "owner": {"type": "string", "description": "仓库所有者"},
                     "repo": {"type": "string", "description": "仓库名"},
                     "limit": {"type": "integer", "description": "返回数量，默认 3"},
                 }, "required": ["owner", "repo"]},
                 "member", repo_releases, category="api", source="builtin.api"),

        # ═══════════════════════════════════════════════════
        #  新增：群投票
        # ═══════════════════════════════════════════════════
        ToolSpec("create_vote", "创建群投票",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "creator_platform_id": {"type": "string"},
                     "question": {"type": "string", "description": "投票问题"},
                     "options_str": {"type": "string", "description": "选项，用 | 分隔，如：选项A | 选项B | 选项C"},
                     "anonymous": {"type": "boolean", "description": "是否匿名投票"},
                 }, "required": ["group_platform_id", "creator_platform_id", "question", "options_str"]},
                 "member", create_vote, category="direct", source="builtin.direct"),
        ToolSpec("cast_vote", "参与投票",
                 {"type": "object", "properties": {
                     "vote_id": {"type": "integer", "description": "投票 ID"},
                     "voter_platform_id": {"type": "string"},
                     "option_index": {"type": "integer", "description": "选项编号（从 1 开始）"},
                 }, "required": ["vote_id", "voter_platform_id", "option_index"]},
                 "member", cast_vote, category="direct", source="builtin.direct"),
        ToolSpec("vote_result", "查看投票结果",
                 {"type": "object", "properties": {
                     "vote_id": {"type": "integer", "description": "投票 ID"},
                 }, "required": ["vote_id"]},
                 "member", vote_result, category="direct", source="builtin.direct"),
        ToolSpec("close_vote", "关闭投票",
                 {"type": "object", "properties": {
                     "vote_id": {"type": "integer"},
                     "creator_platform_id": {"type": "string"},
                 }, "required": ["vote_id", "creator_platform_id"]},
                 "admin", close_vote, category="direct", source="builtin.direct"),

        # ═══════════════════════════════════════════════════
        #  新增：入群欢迎
        # ═══════════════════════════════════════════════════
        ToolSpec("set_welcome", "设置入群欢迎语",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "welcome_text": {"type": "string", "description": "欢迎语，支持 {nickname} {group_name} 变量"},
                 }, "required": ["group_platform_id", "welcome_text"]},
                 "admin", set_welcome, category="direct", source="builtin.direct"),
        ToolSpec("get_welcome", "获取当前欢迎语",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                 }, "required": ["group_platform_id"]},
                 "admin", get_welcome, category="direct", source="builtin.direct"),
        ToolSpec("clear_welcome", "清除欢迎语",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                 }, "required": ["group_platform_id"]},
                 "admin", clear_welcome, category="direct", source="builtin.direct"),
        ToolSpec("set_verify_question", "设置入群验证问题",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "question": {"type": "string"},
                     "answer": {"type": "string"},
                 }, "required": ["group_platform_id", "question", "answer"]},
                 "admin", set_verify_question, category="direct", source="builtin.direct"),

        # ═══════════════════════════════════════════════════
        #  新增：定时消息
        # ═══════════════════════════════════════════════════
        ToolSpec("create_scheduled_message", "创建定时消息（支持 cron 表达式）",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "creator_platform_id": {"type": "string"},
                     "content": {"type": "string", "description": "消息内容"},
                     "cron_expr": {"type": "string", "description": "cron 表达式，如 0 9 * * * 表示每天9点"},
                 }, "required": ["group_platform_id", "creator_platform_id", "content", "cron_expr"]},
                 "admin", create_scheduled_message, category="direct", source="builtin.direct"),
        ToolSpec("list_scheduled_messages", "列出群定时消息",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                 }, "required": ["group_platform_id"]},
                 "member", list_scheduled_messages, category="direct", source="builtin.direct"),
        ToolSpec("delete_scheduled_message", "删除定时消息",
                 {"type": "object", "properties": {
                     "msg_id": {"type": "integer"},
                     "operator_platform_id": {"type": "string"},
                 }, "required": ["msg_id", "operator_platform_id"]},
                 "admin", delete_scheduled_message, category="direct", source="builtin.direct"),
        ToolSpec("toggle_scheduled_message", "启用/暂停定时消息",
                 {"type": "object", "properties": {
                     "msg_id": {"type": "integer"},
                     "enabled": {"type": "boolean"},
                 }, "required": ["msg_id", "enabled"]},
                 "admin", toggle_scheduled_message, category="direct", source="builtin.direct"),

        # ═══════════════════════════════════════════════════
        #  新增：日程事件
        # ═══════════════════════════════════════════════════
        ToolSpec("add_event", "添加日程事件",
                 {"type": "object", "properties": {
                     "creator_platform_id": {"type": "string"},
                     "title": {"type": "string", "description": "事件标题"},
                     "event_time_str": {"type": "string", "description": "时间，格式 YYYY-MM-DD HH:MM"},
                     "group_platform_id": {"type": "string"},
                     "location": {"type": "string", "description": "地点"},
                     "description": {"type": "string", "description": "描述"},
                     "remind_before_min": {"type": "integer", "description": "提前提醒分钟数，默认 30"},
                 }, "required": ["creator_platform_id", "title", "event_time_str"]},
                 "member", add_event, category="direct", source="builtin.direct"),
        ToolSpec("list_events", "查看近期日程",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "days": {"type": "integer", "description": "查看未来几天，默认 7"},
                 }, "required": []},
                 "member", list_events, category="direct", source="builtin.direct"),
        ToolSpec("delete_event", "删除日程",
                 {"type": "object", "properties": {
                     "event_id": {"type": "integer"},
                     "operator_platform_id": {"type": "string"},
                 }, "required": ["event_id", "operator_platform_id"]},
                 "member", delete_event, category="direct", source="builtin.direct"),

        # ═══════════════════════════════════════════════════
        #  新增：增强关键词
        # ═══════════════════════════════════════════════════
        ToolSpec("add_keyword_rule", "添加增强关键词规则（支持正则、随机回复、冷却时间）",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "creator_platform_id": {"type": "string"},
                     "pattern": {"type": "string", "description": "关键词或正则表达式"},
                     "replies_str": {"type": "string", "description": "回复内容，多条用 | 分隔随机选"},
                     "is_regex": {"type": "boolean", "description": "是否正则匹配"},
                     "cooldown_seconds": {"type": "integer", "description": "冷却秒数，0 无冷却"},
                 }, "required": ["group_platform_id", "creator_platform_id", "pattern", "replies_str"]},
                 "admin", add_keyword_rule, category="direct", source="builtin.direct"),
        ToolSpec("list_keyword_rules", "列出关键词规则",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                 }, "required": ["group_platform_id"]},
                 "admin", list_keyword_rules, category="direct", source="builtin.direct"),
        ToolSpec("delete_keyword_rule", "删除关键词规则",
                 {"type": "object", "properties": {
                     "rule_id": {"type": "integer"},
                 }, "required": ["rule_id"]},
                 "admin", delete_keyword_rule, category="direct", source="builtin.direct"),

        # ═══════════════════════════════════════════════════
        #  新增：小游戏
        # ═══════════════════════════════════════════════════
        ToolSpec("start_guess", "开始猜数字游戏",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "creator_id": {"type": "string"},
                     "min_val": {"type": "integer", "description": "最小值，默认 1"},
                     "max_val": {"type": "integer", "description": "最大值，默认 100"},
                 }, "required": ["group_platform_id", "creator_id"]},
                 "member", start_guess, category="direct", source="builtin.direct"),
        ToolSpec("make_guess", "提交猜数字",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "user_id": {"type": "string"},
                     "guess": {"type": "integer", "description": "猜测的数字"},
                 }, "required": ["group_platform_id", "user_id", "guess"]},
                 "member", make_guess, category="direct", source="builtin.direct"),
        ToolSpec("start_quiz", "开始答题竞赛",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "num_questions": {"type": "integer", "description": "题目数量，默认 5"},
                 }, "required": ["group_platform_id"]},
                 "member", start_quiz, category="direct", source="builtin.direct"),
        ToolSpec("answer_quiz", "提交答题答案",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "user_id": {"type": "string"},
                     "choice": {"type": "integer", "description": "选项编号（从 1 开始）"},
                 }, "required": ["group_platform_id", "user_id", "choice"]},
                 "member", answer_quiz, category="direct", source="builtin.direct"),

        # ═══════════════════════════════════════════════════
        #  新增：语录收集
        # ═══════════════════════════════════════════════════
        ToolSpec("add_quote", "收录群语录",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "content": {"type": "string", "description": "语录内容"},
                     "added_by_platform_id": {"type": "string"},
                     "author_platform_id": {"type": "string", "description": "原作者 QQ 号"},
                     "author_nickname": {"type": "string", "description": "原作者昵称"},
                 }, "required": ["group_platform_id", "content", "added_by_platform_id"]},
                 "member", add_quote, category="direct", source="builtin.direct"),
        ToolSpec("random_quote", "随机展示一条群语录",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                 }, "required": ["group_platform_id"]},
                 "member", random_quote, category="direct", source="builtin.direct"),
        ToolSpec("search_quote", "搜索群语录",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "keyword": {"type": "string", "description": "搜索关键词"},
                 }, "required": ["group_platform_id", "keyword"]},
                 "member", search_quote, category="direct", source="builtin.direct"),
        ToolSpec("list_quotes", "列出群语录",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "page": {"type": "integer", "description": "页码，默认 1"},
                     "page_size": {"type": "integer", "description": "每页条数，默认 10"},
                 }, "required": ["group_platform_id"]},
                 "member", list_quotes, category="direct", source="builtin.direct"),

        # ═══════════════════════════════════════════════════
        #  新增：倒数日
        # ═══════════════════════════════════════════════════
        ToolSpec("add_countdown", "添加倒数日/纪念日",
                 {"type": "object", "properties": {
                     "creator_platform_id": {"type": "string"},
                     "name": {"type": "string", "description": "名称"},
                     "target_date_str": {"type": "string", "description": "目标日期，格式 YYYY-MM-DD"},
                     "group_platform_id": {"type": "string"},
                     "remind_daily": {"type": "boolean", "description": "是否每日提醒"},
                 }, "required": ["creator_platform_id", "name", "target_date_str"]},
                 "member", add_countdown, category="direct", source="builtin.direct"),
        ToolSpec("list_countdowns", "列出倒数日",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                 }, "required": []},
                 "member", list_countdowns, category="direct", source="builtin.direct"),
        ToolSpec("delete_countdown", "删除倒数日",
                 {"type": "object", "properties": {
                     "cd_id": {"type": "integer"},
                 }, "required": ["cd_id"]},
                 "member", delete_countdown, category="direct", source="builtin.direct"),

        # ═══════════════════════════════════════════════════
        #  新增：群聊摘要
        # ═══════════════════════════════════════════════════
        ToolSpec("summarize_chat", "生成群聊摘要（AI 总结群消息）",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "limit": {"type": "integer", "description": "分析最近多少条消息，默认 50"},
                 }, "required": ["group_platform_id"]},
                 "member", summarize_chat, category="direct", source="builtin.direct"),

        # ═══════════════════════════════════════════════════
        #  新增：人设增强
        # ═══════════════════════════════════════════════════
        ToolSpec("list_personas", "列出所有人设",
                 {"type": "object", "properties": {}},
                 "member", list_personas, category="direct", source="builtin.direct"),
        ToolSpec("preview_persona", "预览人设详情",
                 {"type": "object", "properties": {
                     "name": {"type": "string", "description": "人设名称"},
                 }, "required": ["name"]},
                 "member", preview_persona, category="direct", source="builtin.direct"),
        ToolSpec("switch_persona", "切换群默认人设",
                 {"type": "object", "properties": {
                     "group_platform_id": {"type": "string"},
                     "persona_name": {"type": "string", "description": "人设名称"},
                 }, "required": ["group_platform_id", "persona_name"]},
                 "admin", switch_persona, category="direct", source="builtin.direct"),
    ]

    for spec in specs:
        registry.register(spec)
