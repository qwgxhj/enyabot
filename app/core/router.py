"""消息路由器 - 命令分发、关键词匹配、AI 对话。"""
from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

from app.core.audit import audit
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.permissions import has_permission, get_sender_role, is_master
from app.plugins import ToolRegistry, register_builtin_tools
from app.plugins.mcp import MCPPluginBridge

# ── API 类插件 ──────────────────────────────────────────
from app.plugins.api.entertainment import kfc_crazy_thursday, random_superpower
from app.plugins.api.identity import name_duplicate_query
from app.plugins.api.ip_lookup import ip_location_query
from app.plugins.api.media import media_parse
from app.plugins.api.weather import weather_query
from app.plugins.api.translator import translate_text
from app.plugins.api.image_search import image_search
from app.plugins.api.music import search_and_cache, select_song
from app.plugins.api.meme import generate_meme
from app.plugins.api.github import repo_info, repo_releases

# ── Direct 类插件 ───────────────────────────────────────
from app.plugins.direct.reminder import create_reminder
from app.plugins.direct.score import query_score, sign_in
from app.plugins.direct.vote import create_vote, cast_vote, vote_result, close_vote
from app.plugins.direct.welcome import set_welcome, get_welcome, clear_welcome, set_verify_question, on_member_join
from app.plugins.direct.scheduler_msg import create_scheduled_message, list_scheduled_messages, delete_scheduled_message, toggle_scheduled_message
from app.plugins.direct.calendar_event import add_event, list_events, delete_event
from app.plugins.direct.keyword_plus import add_keyword_rule, list_keyword_rules, delete_keyword_rule, match_keyword
from app.plugins.direct.games import start_guess, make_guess, start_quiz, answer_quiz
from app.plugins.direct.quote import add_quote, random_quote, search_quote, list_quotes
from app.plugins.direct.countdown import add_countdown, list_countdowns, delete_countdown
from app.plugins.direct.chat_summary import summarize_chat
from app.plugins.direct.persona_switch import list_personas, preview_persona, switch_persona
from app.plugins.direct.group_admin import (
    cmd_mute, cmd_unmute, cmd_kick, cmd_mute_all,
    cmd_set_admin, cmd_set_card, cmd_set_title,
    cmd_set_group_name, cmd_group_info, cmd_group_member_info, cmd_mute_list,
)
from app.plugins.direct.image_gen import generate_image, list_image_commands

from app.services.ai_service import AIService
from app.services.message_service import MessageService
from app.services.reminder_service import ReminderService
from app.config.config_manager import ConfigManager


class Router:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.registry = ToolRegistry()
        self.mcp_bridge = MCPPluginBridge.from_base_dir(base_dir)
        self._register_tools()
        self.ai = AIService(base_dir, self.registry)
        self.message_service = MessageService()
        self.reminder_service = ReminderService()
        self.rate_limiter = SlidingWindowRateLimiter()
        self._sender = None  # 由 BotApplication 注入

    def set_sender(self, sender):
        """注入 NapCatSender,用于需要主动发消息的场景。"""
        self._sender = sender
        # 注入到 group_admin 供 AI tool 调用
        from app.plugins.direct.group_admin import set_sender as ga_set_sender
        ga_set_sender(sender)

    def _register_tools(self):
        register_builtin_tools(self.registry)

    async def load_mcp_tools(self) -> int:
        return await self.mcp_bridge.register_tools(self.registry)

    async def close(self) -> None:
        await self.mcp_bridge.close()

    # ═══════════════════════════════════════════════════════
    #  帮助文本
    # ═══════════════════════════════════════════════════════

    def _build_help_text(self) -> str:
        lines = [
            "═══ QQ 机器人命令 ═══",
            "",
            "【基础】",
            "  /ping - 测试连通性",
            "  /help - 显示帮助",
            "  /主人 - 查看主人列表",
            "  /设置主人 - 绑定自己为一级主人",
            "  /设置二级主人 QQ号 - 添加二级主人(一级主人)",
            "  /移除二级主人 QQ号 - 移除二级主人(一级主人)",
            "",
            "【工具类】",
            "  /天气 城市 - 查询天气",
            "  /IP 地址 - 查询 IP 归属地",
            "  /翻译 [目标语言] 文本 - 翻译(如 /翻译 en 你好)",
            "  /搜图 [图片] - 以图搜图(附带图片或回复图片)",
            "  /点歌 歌名 - 搜索音乐",
            "  /选歌 编号 - 选择歌曲获取链接",
            "  /重名 姓名 - 查询姓名重名",
            "  /解析 URL - 解析媒体链接(支持B站/抖音/快手)",
            "  /github 用户/仓库 - 查询 GitHub 仓库",
            "",
            "【趣味】",
            "  /超能力 - 随机超能力",
            "  /KFC - 疯狂星期四文案",
            "  /表情 上方文字 | 下方文字 - 生成表情包",
            "  /作图 命令名 @用户 文字 - 趣味作图（详见 /作图列表）",
            "  /作图列表 - 查看所有可用作图命令",
            "",
            "【群互动】",
            "  /投票 问题 | 选项1 | 选项2 | ... - 创建投票",
            "  /投票 <ID> <选项编号> - 参与投票",
            "  /投票结果 <ID> - 查看投票结果",
            "  /语录收录 <内容> - 收录群语录",
            "  /语录 - 随机展示一条语录",
            "  /语录搜索 <关键词> - 搜索语录",
            "  /猜数字 - 开始猜数字游戏",
            "  /猜 <数字> - 提交猜测",
            "  /答题 - 开始答题竞赛",
            "  /答题 <选项编号> - 提交答案",
            "",
            "【群管理】",
            "  /提醒 分钟 内容 - 创建提醒",
            "  /日程 时间 标题 - 添加日程(如 /日程 2026-05-15 14:00 会议)",
            "  /日程列表 - 查看近期日程",
            "  /定时 cron表达式 内容 - 创建定时消息",
            "  /定时列表 - 查看定时消息",
            "  /倒数日 名称 日期 - 添加倒数日(如 /倒数日 高考 2026-06-07)",
            "  /倒数日列表 - 查看倒数日",
            "  /签到 - 每日签到",
            "  /积分 - 查询积分",
            "  /总结 - AI 总结群聊(最近50条)",
            "",
            "【人设】",
            "  /人设列表 - 查看所有人设",
            "  /人设预览 名称 - 预览人设",
            "  /人设切换 名称 - 切换群人设(管理员)",
            "",
            "【关键词(管理员)】",
            "  /关键词添加 关键词 回复内容",
            "  /关键词列表",
            "  /关键词删除 ID",
            "",
            "【欢迎语(管理员)】",
            "  /设置欢迎语 内容",
            "  /查看欢迎语",
            "  /清除欢迎语",
            "  /设置验证 问题 答案",
            "",
            "【群管(管理员)】",
            "  /禁言 @用户 分钟数 - 禁言群成员",
            "  /解禁 @用户 - 解除禁言",
            "  /踢 @用户 - 踢出群成员",
            "  /全员禁言 - 开启全员禁言",
            "  /解除全员禁言 - 关闭全员禁言",
            "  /群名 新名称 - 修改群名",
            "  /群信息 - 查看群信息",
            "  /成员信息 @用户 - 查看成员详情",
            "  /禁言列表 - 查看禁言中成员",
            "  /群牌 @用户 名片 - 设置群名片",
            "  /头衔 @用户 头衔 - 设置专属头衔(群主)",            "  /设置管理 @用户 - 设置管理员(群主)",
            "  /取消管理 @用户 - 取消管理员(群主)",
            "",
            "也支持 @机器人 或唤醒词进入 AI 对话。",
        ]
        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════
    #  主路由
    # ═══════════════════════════════════════════════════════

    async def route(self, event) -> str | None:
        self.message_service.ensure_user_and_group(event)

        # ── 群成员增加事件 ──────────────────────────────
        if event.event_type == "group_increase":
            return await self._handle_group_increase(event)

        if not event.raw_text and not event.attachments:
            return None

        # ── 解析有效角色（主人优先） ───────────────────
        event.sender_role = get_sender_role(event.sender_role, event.user_id)

        # ── 关键词匹配(优先于命令) ────────────────────
        if event.group_id:
            keyword_reply = await match_keyword(event.group_id, event.raw_text)
            if keyword_reply:
                return keyword_reply

        # ── 命令路由 ────────────────────────────────────
        text = event.raw_text.strip()

        # 基础命令
        if text.startswith("/ping"):
            return "pong"
        if text.startswith("/help"):
            return self._build_help_text()

        # ── 主人设置 ───────────────────────────────────
        if text.startswith("/设置主人"):
            return await self._cmd_set_master(text, event)
        if text.startswith("/设置二级主人"):
            return await self._cmd_set_master2(text, event)
        if text.startswith("/移除二级主人"):
            return await self._cmd_remove_master2(text, event)
        if text.startswith("/主人"):
            from app.core.permissions import _get_master_config, _get_all_masters, _get_master2_list
            bot_cfg = _get_master_config()
            m1 = str(bot_cfg.get("master_qq", "")).strip()
            m2 = _get_master2_list(bot_cfg)
            lines = []
            if m1:
                lines.append(f"一级主人: {m1}")
            else:
                lines.append("一级主人: 未设置")
            if m2:
                lines.append(f"二级主人: {', '.join(m2)}")
            else:
                lines.append("二级主人: 无")
            return "\n".join(lines)

        # ── 工具类命令 ──────────────────────────────────
        if text.startswith("/天气"):
            city = text.replace("/天气", "", 1).strip() or "北京"
            result = await weather_query(city)
            return f"{result['city']}:{result['weather']},{result['temp']}"

        if text.startswith("/IP") or text.startswith("/ip"):
            ip = text.split(maxsplit=1)[1].strip() if len(text.split(maxsplit=1)) > 1 else ""
            if not ip:
                return "用法:/IP 8.8.8.8"
            result = await ip_location_query(ip)
            return result["message"]

        if text.startswith("/翻译"):
            return await self._cmd_translate(text)

        if text.startswith("/搜图"):
            return await self._cmd_image_search(text, event)

        if text.startswith("/点歌"):
            keyword = text.replace("/点歌", "", 1).strip()
            if not keyword:
                return "用法:/点歌 歌名"
            result = await search_and_cache(keyword, event.group_id, event.user_id)
            return result["message"]

        if text.startswith("/选歌"):
            num_str = text.replace("/选歌", "", 1).strip()
            if not num_str or not num_str.isdigit():
                return "用法：/选歌 <编号>（先用 /点歌 搜索）"
            result = await select_song(int(num_str), event.group_id, event.user_id)
            if not result["success"]:
                return result["message"]
            # 尝试发送音频
            play_url = result.get("play_url", "")
            if play_url and self._sender and event.group_id:
                try:
                    song = result.get("song", {})
                    title = f"{song.get('name', '')} - {song.get('artist', '')}"
                    await self._sender.send_group_record(event.group_id, play_url, title=title)
                    return result["message"]
                except Exception:
                    pass
            return result["message"]

        if text.startswith("/github"):
            parts = text.replace("/github", "", 1).strip().split("/")
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                return "用法:/github 用户名/仓库名\n例如:/github openclaw/openclaw"
            result = await repo_info(parts[0].strip(), parts[1].strip())
            if not result["success"]:
                return result["message"]
            return (
                f"📦 {result['full_name']}\n"
                f"{result['description']}\n"
                f"⭐ {result['stars']}  🍴 {result['forks']}  🐛 {result['open_issues']}\n"
                f"语言:{result['language']}  许可:{result['license']}\n"
                f"{result['url']}"
            )

        if text.startswith("/重名"):
            name = text.replace("/重名", "", 1).strip()
            if not name:
                return "用法:/重名 张三"
            result = await name_duplicate_query(name)
            return result["message"]

        if text.startswith("/解析"):
            url = text.replace("/解析", "", 1).strip()
            if not url:
                return "用法:/解析 https://example.com/video\n支持: B站(bilibili.com/b23.tv)、抖音(douyin.com)、快手(kuaishou.com)"
            result = await media_parse(url)
            # 如果有播放地址，下载后发送视频文件
            play_url = result.get("play_url", "")
            if play_url and self._sender and event.group_id and result.get("success"):
                import os, tempfile
                import httpx
                tmp_path = None
                try:
                    platform = result.get("platform", "")
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    }
                    if platform == "bilibili":
                        headers["Referer"] = "https://www.bilibili.com/"
                    elif platform == "douyin":
                        headers["Referer"] = "https://www.douyin.com/"
                    elif platform == "kuaishou":
                        headers["Referer"] = "https://www.kuaishou.com/"
                    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as dl_client:
                        resp = await dl_client.get(play_url, headers=headers)
                        if resp.status_code == 200 and len(resp.content) > 1024:
                            ext = ".mp4"
                            ct = resp.headers.get("content-type", "")
                            if "mp3" in ct or "audio" in ct:
                                ext = ".mp3"
                            tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext, prefix="qqbot_")
                            os.close(tmp_fd)
                            with open(tmp_path, "wb") as f:
                                f.write(resp.content)
                            await self._sender.call_action("send_group_msg", {
                                "group_id": int(event.group_id),
                                "message": [{"type": "video", "data": {"file": tmp_path}}],
                            })
                except Exception:
                    pass  # 视频发送失败不影响文字消息
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
            return result["message"]

        # ── 趣味命令 ────────────────────────────────────
        if text.startswith("/超能力"):
            result = await random_superpower()
            return result["message"]

        if text.startswith("/KFC") or text.startswith("/kfc"):
            result = await kfc_crazy_thursday()
            return result["message"]

        if text.startswith("/表情"):
            return await self._cmd_meme(text)

        # ── 作图命令 ────────────────────────────────────
        if text.startswith("/作图列表"):
            return list_image_commands()
        if text.startswith("/作图"):
            return await self._cmd_image_gen(text, event)

        # ── 群互动命令 ──────────────────────────────────
        if text.startswith("/投票"):
            return await self._cmd_vote(text, event)

        if text.startswith("/投票结果"):
            return await self._cmd_vote_result(text)

        if text.startswith("/语录收录"):
            content = text.replace("/语录收录", "", 1).strip()
            if not content:
                return "用法:/语录收录 <内容>"
            result = await add_quote(event.group_id, content, event.user_id)
            return result["message"]

        if text.startswith("/语录搜索"):
            keyword = text.replace("/语录搜索", "", 1).strip()
            if not keyword:
                return "用法:/语录搜索 <关键词>"
            result = await search_quote(event.group_id, keyword)
            return result["message"]

        if text.startswith("/语录"):
            result = await random_quote(event.group_id)
            return result["message"]

        if text.startswith("/猜数字"):
            result = await start_guess(event.group_id, event.user_id)
            return result["message"]

        if text.startswith("/猜"):
            num_str = text.replace("/猜", "", 1).strip()
            if not num_str or not num_str.isdigit():
                return "用法:/猜 <数字>"
            result = await make_guess(event.group_id, event.user_id, int(num_str))
            return result["message"]

        if text.startswith("/答题"):
            arg = text.replace("/答题", "", 1).strip()
            if not arg:
                result = await start_quiz(event.group_id)
                return result["message"]
            if arg.isdigit():
                result = await answer_quiz(event.group_id, event.user_id, int(arg))
                return result["message"]
            return "用法:/答题(开始)或 /答题 <选项编号>"

        # ── 提醒 / 签到 / 积分 ──────────────────────────
        if text.startswith("/提醒"):
            match = re.match(r"^/提醒\s+(\d+)\s+(.+)$", text)
            if not match:
                return "用法:/提醒 30 记得开会"
            minutes = int(match.group(1))
            content = match.group(2).strip()
            try:
                remind_at = self.reminder_service.create_reminder(event.user_id, event.group_id, content, minutes)
            except ValueError as exc:
                return f"创建提醒失败:{exc}"
            audit("create_reminder", operator_user_id=event.user_id, group_id=event.group_id, detail={"minutes": minutes, "content": content})
            return f"提醒已创建:{minutes} 分钟后提醒你 {content}。\n预计时间:{remind_at}"

        if text.startswith("/签到"):
            result = await sign_in(event.user_id)
            return result["message"]

        if text.startswith("/积分"):
            result = await query_score(event.user_id)
            return f"你的积分:{result['score']}\n{result['message']}"

        # ── 日程命令 ────────────────────────────────────
        if text.startswith("/日程列表"):
            result = await list_events(event.group_id)
            return result["message"]

        if text.startswith("/日程删除"):
            id_str = text.replace("/日程删除", "", 1).strip()
            if not id_str or not id_str.isdigit():
                return "用法:/日程删除 <ID>"
            result = await delete_event(int(id_str), event.user_id)
            return result["message"]

        if text.startswith("/日程"):
            return await self._cmd_calendar(text, event)

        # ── 定时消息命令 ────────────────────────────────
        if text.startswith("/定时列表"):
            result = await list_scheduled_messages(event.group_id)
            return result["message"]

        if text.startswith("/定时删除"):
            id_str = text.replace("/定时删除", "", 1).strip()
            if not id_str or not id_str.isdigit():
                return "用法:/定时删除 <ID>"
            result = await delete_scheduled_message(int(id_str), event.user_id)
            return result["message"]

        if text.startswith("/定时"):
            return await self._cmd_scheduled_msg(text, event)

        # ── 倒数日命令 ──────────────────────────────────
        if text.startswith("/倒数日列表"):
            result = await list_countdowns(event.group_id)
            return result["message"]

        if text.startswith("/倒数日删除"):
            id_str = text.replace("/倒数日删除", "", 1).strip()
            if not id_str or not id_str.isdigit():
                return "用法:/倒数日删除 <ID>"
            result = await delete_countdown(int(id_str))
            return result["message"]

        if text.startswith("/倒数日"):
            return await self._cmd_countdown(text, event)

        # ── 群聊总结 ────────────────────────────────────
        if text.startswith("/总结"):
            limit_str = text.replace("/总结", "", 1).strip()
            limit = int(limit_str) if limit_str.isdigit() else 50
            result = await summarize_chat(event.group_id, limit)
            if not result["success"]:
                return result["message"]
            # 调用 AI 生成摘要
            prompt = result.get("prompt_hint", "")
            if prompt:
                # 构造一个临时 event 交给 AI
                import copy
                summary_event = copy.deepcopy(event)
                summary_event.raw_text = prompt
                summary_event.event_type = "private_message"  # 避免触发关键词
                return await self.ai.chat(summary_event)
            return result["message"]

        # ── 人设命令 ────────────────────────────────────
        if text.startswith("/人设列表"):
            result = await list_personas()
            return result["message"]

        if text.startswith("/人设预览"):
            name = text.replace("/人设预览", "", 1).strip()
            if not name:
                return "用法:/人设预览 <名称>"
            result = await preview_persona(name)
            return result["message"]

        if text.startswith("/人设切换"):
            name = text.replace("/人设切换", "", 1).strip()
            if not name:
                return "用法:/人设切换 <名称>"
            if not has_permission(event.sender_role, "admin"):
                return "只有管理员可以切换群人设"
            result = await switch_persona(event.group_id, name)
            return result["message"]

        # ── 关键词管理命令(管理员) ────────────────────
        if text.startswith("/关键词添加"):
            if not has_permission(event.sender_role, "admin"):
                return "只有管理员可以管理关键词"
            return await self._cmd_keyword_add(text, event)

        if text.startswith("/关键词列表"):
            result = await list_keyword_rules(event.group_id)
            return result["message"]

        if text.startswith("/关键词删除"):
            if not has_permission(event.sender_role, "admin"):
                return "只有管理员可以删除关键词"
            id_str = text.replace("/关键词删除", "", 1).strip()
            if not id_str or not id_str.isdigit():
                return "用法:/关键词删除 <ID>"
            result = await delete_keyword_rule(int(id_str))
            return result["message"]

        # ── 欢迎语管理命令(管理员) ────────────────────
        if text.startswith("/设置欢迎语"):
            if not has_permission(event.sender_role, "admin"):
                return "只有管理员可以设置欢迎语"
            welcome_text = text.replace("/设置欢迎语", "", 1).strip()
            result = await set_welcome(event.group_id, welcome_text)
            return result["message"]

        if text.startswith("/查看欢迎语"):
            result = await get_welcome(event.group_id)
            return result["message"]

        if text.startswith("/清除欢迎语"):
            if not has_permission(event.sender_role, "admin"):
                return "只有管理员可以清除欢迎语"
            result = await clear_welcome(event.group_id)
            return result["message"]

        if text.startswith("/设置验证"):
            if not has_permission(event.sender_role, "admin"):
                return "只有管理员可以设置验证"
            return await self._cmd_verify(text, event)

        # ── 群管命令(管理员) ──────────────────────────────
        if self._sender and event.group_id:
            if text.startswith("/禁言"):
                if not has_permission(event.sender_role, "admin"):
                    return "只有管理员可以禁言"
                return await self._cmd_mute(text, event)
            if text.startswith("/解禁"):
                if not has_permission(event.sender_role, "admin"):
                    return "只有管理员可以解禁"
                return await self._cmd_unmute(text, event)
            if text.startswith("/踢"):
                if not has_permission(event.sender_role, "admin"):
                    return "只有管理员可以踢出成员"
                return await self._cmd_kick(text, event)
            if text.startswith("/全员禁言"):
                if not has_permission(event.sender_role, "admin"):
                    return "只有管理员可以全员禁言"
                return await cmd_mute_all(self._sender, event.group_id, True)
            if text.startswith("/解除全员禁言"):
                if not has_permission(event.sender_role, "admin"):
                    return "只有管理员可以解除全员禁言"
                return await cmd_mute_all(self._sender, event.group_id, False)
            if text.startswith("/设置管理"):
                if not has_permission(event.sender_role, "owner"):
                    return "只有群主可以设置管理员"
                return await self._cmd_set_admin(text, event)
            if text.startswith("/取消管理"):
                if not has_permission(event.sender_role, "owner"):
                    return "只有群主可以取消管理员"
                return await self._cmd_cancel_admin(text, event)
            if text.startswith("/群名"):
                if not has_permission(event.sender_role, "admin"):
                    return "只有管理员可以修改群名"
                return await self._cmd_set_group_name(text, event)
            if text.startswith("/群信息"):
                return await cmd_group_info(self._sender, event.group_id)
            if text.startswith("/成员信息"):
                return await self._cmd_member_info(text, event)
            if text.startswith("/禁言列表"):
                return await cmd_mute_list(self._sender, event.group_id)
            if text.startswith("/群牌"):
                if not has_permission(event.sender_role, "admin"):
                    return "只有管理员可以设置群牌"
                return await self._cmd_set_card(text, event)
            if text.startswith("/头衔"):
                if not has_permission(event.sender_role, "admin"):
                    return "只有管理员可以设置头衔"
                return await self._cmd_set_title(text, event)

        # ── AI 对话 ─────────────────────────────────────
        ai_key = f"ai:{event.group_id or event.user_id}:{event.user_id}"
        if self.ai.should_trigger_ai(event):
            if not self.rate_limiter.allow(ai_key, limit=6, window_seconds=60):
                return "你说得有点快,稍等一下再聊。"
            reply = await self.ai.chat(event)
            audit("ai_reply", operator_user_id=event.user_id, group_id=event.group_id, detail={"message": event.raw_text[:200]})
            return reply

        return None

    # ═══════════════════════════════════════════════════════
    #  群成员增加处理
    # ═══════════════════════════════════════════════════════

    async def _handle_group_increase(self, event) -> str | None:
        """处理新成员入群事件。"""
        nickname = ""
        sender_info = event.raw_payload.get("sender", {})
        if isinstance(sender_info, dict):
            nickname = sender_info.get("nickname", sender_info.get("card", ""))
        if not nickname:
            nickname = f"用户{event.user_id}"

        result = await on_member_join(event.group_id, event.user_id, nickname)
        return result.get("message")

    # ═══════════════════════════════════════════════════════
    #  命令子处理函数
    # ═══════════════════════════════════════════════════════

    async def _cmd_translate(self, text: str) -> str:
        """翻译命令:/翻译 [目标语言] 文本"""
        content = text.replace("/翻译", "", 1).strip()
        if not content:
            return "用法:/翻译 [目标语言] 文本\n例如:/翻译 en 你好世界\n支持:zh/en/ja/ko/fr/de/es/ru"

        parts = content.split(maxsplit=1)
        # 判断第一个词是否是语言代码
        lang_codes = {"zh", "en", "ja", "ko", "fr", "de", "es", "ru", "auto"}
        if len(parts) >= 2 and parts[0].lower() in lang_codes:
            target_lang = parts[0].lower()
            to_translate = parts[1]
        else:
            target_lang = "en"
            to_translate = content

        result = await translate_text(to_translate, target_lang)
        if not result["success"]:
            return result["message"]
        engine = result.get("engine", "")
        return f"【翻译 · {engine}】\n{result['translated']}"

    async def _cmd_image_search(self, text: str, event) -> str:
        """搜图命令。"""
        # 从附件中找图片
        image_url = ""
        for att in event.attachments:
            if att.get("type") == "image":
                image_url = (att.get("data") or {}).get("url", "")
                break

        if not image_url:
            return "请发送图片或回复一条带图片的消息后使用 /搜图"

        result = await image_search(image_url)
        if not result["success"]:
            return result["message"]

        lines = [f"🔍 {result['message']}:"]
        for i, r in enumerate(result.get("results", []), 1):
            sim = r.get("similarity", "")
            source = r.get("source", r.get("name", ""))
            url = r.get("url", "")
            engine = r.get("engine", "")
            line = f"  {i}. [{engine}] {sim}"
            if source:
                line += f" - {source}"
            if url:
                line += f"\n     {url}"
            lines.append(line)
        return "\n".join(lines)

    async def _cmd_meme(self, text: str) -> str:
        """表情包命令:/表情 上方文字 | 下方文字"""
        content = text.replace("/表情", "", 1).strip()
        if not content:
            return "用法:/表情 上方文字 | 下方文字\n例如:/表情 当我发现bug在第42行"

        parts = content.split("|", 1)
        top_text = parts[0].strip()
        bottom_text = parts[1].strip() if len(parts) > 1 else ""

        result = await generate_meme(top_text, bottom_text)
        if not result["success"]:
            return result["message"]
        return f"表情包已生成:{result.get('file_path', '')}"

    async def _cmd_vote(self, text: str, event) -> str:
        """投票命令处理。"""
        content = text.replace("/投票", "", 1).strip()
        if not content:
            return "用法:\n  /投票 问题 | 选项1 | 选项2 | ...(创建)\n  /投票 <ID> <选项编号>(参与)"

        # 尝试解析为 "ID 选项编号"
        match = re.match(r"^(\d+)\s+(\d+)$", content)
        if match:
            vote_id = int(match.group(1))
            option_index = int(match.group(2))
            result = await cast_vote(vote_id, event.user_id, option_index)
            return result["message"]

        # 否则创建投票
        parts = content.split("|")
        if len(parts) < 3:
            return "创建投票格式:/投票 问题 | 选项1 | 选项2 | ...\n至少需要 2 个选项"

        question = parts[0].strip()
        options_str = " | ".join(p.strip() for p in parts[1:])
        result = await create_vote(event.group_id, event.user_id, question, options_str)
        return result["message"]

    async def _cmd_vote_result(self, text: str) -> str:
        """投票结果命令。"""
        id_str = text.replace("/投票结果", "", 1).strip()
        if not id_str or not id_str.isdigit():
            return "用法:/投票结果 <ID>"
        result = await vote_result(int(id_str))
        return result["message"]

    async def _cmd_calendar(self, text: str, event) -> str:
        """日程命令:/日程 YYYY-MM-DD HH:MM 标题"""
        content = text.replace("/日程", "", 1).strip()
        if not content:
            return "用法:/日程 YYYY-MM-DD HH:MM 标题\n例如:/日程 2026-05-15 14:00 团队评审"

        match = re.match(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+(.+)", content)
        if not match:
            return "格式错误。用法:/日程 YYYY-MM-DD HH:MM 标题\n例如:/日程 2026-05-15 14:00 团队评审"

        time_str = match.group(1)
        title = match.group(2).strip()
        result = await add_event(event.user_id, title, time_str, event.group_id)
        return result["message"]

    async def _cmd_scheduled_msg(self, text: str, event) -> str:
        """定时消息命令:/定时 cron表达式 内容"""
        content = text.replace("/定时", "", 1).strip()
        if not content:
            return "用法:/定时 cron表达式 内容\n例如:/定时 0 9 * * * 每天早上好\ncron 格式:分 时 日 月 周"

        parts = content.split(maxsplit=5)
        if len(parts) < 6:
            return "格式不完整。用法:/定时 分 时 日 月 周 内容\n例如:/定时 0 9 * * * 每天早上好"

        cron_expr = " ".join(parts[:5])
        msg_content = parts[5]

        if not has_permission(event.sender_role, "admin"):
            return "只有管理员可以创建定时消息"

        result = await create_scheduled_message(event.group_id, event.user_id, msg_content, cron_expr)
        if result["success"]:
            # 动态注册到调度器
            from app.host import HOST
            if HOST._bot_app and hasattr(HOST._bot_app, '_scheduled_service'):
                HOST._bot_app._scheduled_service.add_scheduled_message(
                    result["id"], event.group_id, msg_content, cron_expr
                )
        return result["message"]

    async def _cmd_countdown(self, text: str, event) -> str:
        """倒数日命令:/倒数日 名称 日期"""
        content = text.replace("/倒数日", "", 1).strip()
        if not content:
            return "用法:/倒数日 名称 YYYY-MM-DD\n例如:/倒数日 高考 2026-06-07"

        match = re.match(r"(.+?)\s+(\d{4}-\d{2}-\d{2})$", content)
        if not match:
            return "格式错误。用法:/倒数日 名称 YYYY-MM-DD\n例如:/倒数日 高考 2026-06-07"

        name = match.group(1).strip()
        date_str = match.group(2).strip()
        result = await add_countdown(event.user_id, name, date_str, event.group_id)
        return result["message"]

    async def _cmd_keyword_add(self, text: str, event) -> str:
        """关键词添加命令:/关键词添加 关键词 回复内容"""
        content = text.replace("/关键词添加", "", 1).strip()
        if not content:
            return "用法:/关键词添加 关键词 回复内容\n多条回复用 | 分隔"

        parts = content.split(maxsplit=1)
        if len(parts) < 2:
            return "格式不完整。用法:/关键词添加 关键词 回复内容"

        pattern = parts[0]
        replies_str = parts[1]
        result = await add_keyword_rule(event.group_id, event.user_id, pattern, replies_str)
        return result["message"]

    async def _cmd_verify(self, text: str, event) -> str:
        """设置验证命令:/设置验证 问题 答案"""
        content = text.replace("/设置验证", "", 1).strip()
        if not content:
            return "用法:/设置验证 问题 答案\n例如:/设置验证 本群暗号是什么 暗号123"

        parts = content.split(maxsplit=1)
        if len(parts) < 2:
            return "格式不完整。用法:/设置验证 问题 答案"

        question = parts[0]
        answer = parts[1]
        result = await set_verify_question(event.group_id, question, answer)
        return result["message"]

    # ═══════════════════════════════════════════════════════
    #  群管子命令处理
    # ═══════════════════════════════════════════════════════
    async def _cmd_mute(self, text: str, event) -> str:
        """禁言命令:/禁言 @用户 分钟数"""
        content = text.replace("/禁言", "", 1).strip()
        if not content:
            return "用法:/禁言 @用户 分钟数\n例如:/禁言 @张三 30"
        parts = content.split()
        user_id = self._extract_at_user(event) or (parts[0] if parts else "")
        minutes = int(parts[-1]) if parts and parts[-1].isdigit() else 10
        if not user_id:
            return "请@要禁言的用户，或提供QQ号\n用法:/禁言 @用户 分钟数"
        return await cmd_mute(self._sender, event.group_id, user_id, minutes)

    async def _cmd_unmute(self, text: str, event) -> str:
        """解禁命令:/解禁 @用户"""
        user_id = self._extract_at_user(event) or text.replace("/解禁", "", 1).strip()
        if not user_id:
            return "请@要解禁的用户，或提供QQ号\n用法:/解禁 @用户"
        return await cmd_unmute(self._sender, event.group_id, user_id)

    async def _cmd_kick(self, text: str, event) -> str:
        """踢出命令:/踢 @用户"""
        user_id = self._extract_at_user(event) or text.replace("/踢", "", 1).strip()
        if not user_id:
            return "请@要踢出的用户，或提供QQ号\n用法:/踢 @用户"
        reject = "拒绝" in text or "拉黑" in text
        return await cmd_kick(self._sender, event.group_id, user_id, reject)

    async def _cmd_set_admin(self, text: str, event) -> str:
        """设置管理员:/设置管理 @用户"""
        user_id = self._extract_at_user(event) or text.replace("/设置管理", "", 1).strip()
        if not user_id:
            return "请@要设置为管理员的用户\n用法:/设置管理 @用户"
        return await cmd_set_admin(self._sender, event.group_id, user_id, True)

    async def _cmd_cancel_admin(self, text: str, event) -> str:
        """取消管理员:/取消管理 @用户"""
        user_id = self._extract_at_user(event) or text.replace("/取消管理", "", 1).strip()
        if not user_id:
            return "请@要取消管理员的用户\n用法:/取消管理 @用户"
        return await cmd_set_admin(self._sender, event.group_id, user_id, False)

    async def _cmd_set_group_name(self, text: str, event) -> str:
        """修改群名:/群名 新名称"""
        name = text.replace("/群名", "", 1).strip()
        if not name:
            return "用法:/群名 新群名"
        return await cmd_set_group_name(self._sender, event.group_id, name)

    async def _cmd_member_info(self, text: str, event) -> str:
        """查看成员信息:/成员信息 @用户"""
        user_id = self._extract_at_user(event) or text.replace("/成员信息", "", 1).strip()
        if not user_id:
            return "请@要查看的用户，或提供QQ号\n用法:/成员信息 @用户"
        return await cmd_group_member_info(self._sender, event.group_id, user_id)

    async def _cmd_set_card(self, text: str, event) -> str:
        """设置群名片:/群牌 @用户 名片"""
        content = text.replace("/群牌", "", 1).strip()
        user_id = self._extract_at_user(event)
        if user_id:
            card = content.replace(f"@{user_id}", "").strip()
        else:
            parts = content.split(maxsplit=1)
            user_id = parts[0] if parts else ""
            card = parts[1] if len(parts) > 1 else ""
        if not user_id:
            return "用法:/群牌 @用户 名片内容"
        return await cmd_set_card(self._sender, event.group_id, user_id, card)

    async def _cmd_set_title(self, text: str, event) -> str:
        """设置头衔:/头衔 @用户 头衔"""
        content = text.replace("/头衔", "", 1).strip()
        user_id = self._extract_at_user(event)
        if user_id:
            title = content.replace(f"@{user_id}", "").strip()
        else:
            parts = content.split(maxsplit=1)
            user_id = parts[0] if parts else ""
            title = parts[1] if len(parts) > 1 else ""
        if not user_id:
            return "用法:/头衔 @用户 头衔内容"
        return await cmd_set_title(self._sender, event.group_id, user_id, title)

    async def _cmd_image_gen(self, text: str, event) -> str:
        """作图命令:/作图 命令名 @用户 文字"""
        content = text.replace("/作图", "", 1).strip()
        if not content:
            return "用法:/作图 命令名 @用户 文字\n发送 /作图列表 查看所有可用命令"

        parts = content.split(maxsplit=1)
        cmd = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""

        # 提取被@的用户
        target_qq = self._extract_at_user(event) or event.user_id
        my_qq = event.user_id

        # 获取目标用户群昵称
        name = ""
        if rest:
            # 去掉 @xxx 部分，剩下作为文字
            rest = re.sub(r'@\w+', '', rest).strip()

        result = await generate_image(
            cmd=cmd,
            qq=target_qq,
            myqq=my_qq,
            name=name,
            text=rest,
        )

        if result.get("success") and result.get("image_url") and self._sender and event.group_id:
            try:
                await self._sender.send_group_image(event.group_id, result["image_url"])
                return ""  # 图片已发送，不返回文字
            except Exception:
                pass
        return result.get("message", "作图失败")

    @staticmethod
    def _extract_at_user(event) -> str:
        """从消息中提取被@的用户QQ号。"""
        if event.mentions:
            return event.mentions[0]
        return ""

    async def _cmd_set_master(self, text: str, event) -> str:
        """设置一级主人:/设置主人 或 /设置主人 QQ号"""
        config = ConfigManager().get()
        current_master = str(config.get("bot", {}).get("master_qq", "")).strip()

        if current_master and str(event.user_id) != current_master:
            return f"已有一级主人（{current_master}），只有一级主人才能更换。"

        content = text.replace("/设置主人", "", 1).strip()
        new_master = content if content else str(event.user_id)

        from pathlib import Path
        if "bot" not in config:
            config["bot"] = {}
        config["bot"]["master_qq"] = new_master
        from app.webui.config_store import write_yaml_config
        write_yaml_config(config)
        ConfigManager().reload(Path(__file__).resolve().parents[2] / "config.yaml")

        if new_master == str(event.user_id):
            return f"已绑定你（{new_master}）为一级主人。"
        return f"已设置 {new_master} 为一级主人。"

    async def _cmd_set_master2(self, text: str, event) -> str:
        """添加二级主人:/设置二级主人 QQ号"""
        if not has_permission(event.sender_role, "master"):
            return "只有一级主人可以设置二级主人。"

        content = text.replace("/设置二级主人", "", 1).strip()
        if not content:
            return "用法:/设置二级主人 QQ号"

        from pathlib import Path
        from app.core.permissions import _get_master2_list
        config = ConfigManager().get()
        bot_cfg = config.get("bot", {})
        m2_list = _get_master2_list(bot_cfg)

        if content in m2_list:
            return f"{content} 已经是二级主人了。"

        m2_list.add(content)
        if "bot" not in config:
            config["bot"] = {}
        config["bot"]["master2_qq"] = sorted(m2_list)

        from app.webui.config_store import write_yaml_config
        write_yaml_config(config)
        ConfigManager().reload(Path(__file__).resolve().parents[2] / "config.yaml")
        return f"已添加 {content} 为二级主人。"

    async def _cmd_remove_master2(self, text: str, event) -> str:
        """移除二级主人:/移除二级主人 QQ号"""
        if not has_permission(event.sender_role, "master"):
            return "只有一级主人可以移除二级主人。"

        content = text.replace("/移除二级主人", "", 1).strip()
        if not content:
            return "用法:/移除二级主人 QQ号"

        from pathlib import Path
        from app.core.permissions import _get_master2_list
        config = ConfigManager().get()
        bot_cfg = config.get("bot", {})
        m2_list = _get_master2_list(bot_cfg)

        if content not in m2_list:
            return f"{content} 不是二级主人。"

        m2_list.discard(content)
        if "bot" not in config:
            config["bot"] = {}
        config["bot"]["master2_qq"] = sorted(m2_list)

        from app.webui.config_store import write_yaml_config
        write_yaml_config(config)
        ConfigManager().reload(Path(__file__).resolve().parents[2] / "config.yaml")
        return f"已移除 {content} 的二级主人身份。"
