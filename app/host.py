from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import socket
import sys
from typing import Optional

from loguru import logger

from app.adapters.napcat_sender import NapCatSender
from app.adapters.napcat_ws_client import NapCatWsClient
from app.config.config_manager import ConfigManager
from app.core.router import Router
from app.db.base import Base
from app.db.session import engine
from app.services.scheduled_msg_service import ScheduledMessageService

import app.models.audit_log
import app.models.group
import app.models.group_member
import app.models.memory
import app.models.message_log
import app.models.model_provider
import app.models.reminder
import app.models.session
import app.models.user
import app.models.vote
import app.models.scheduled_message
import app.models.calendar_event
import app.models.quote
import app.models.countdown
import app.models.keyword_rule


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_MANAGER = ConfigManager()


class BotApplication:
    def __init__(self):
        self.base_dir = BASE_DIR
        self._closed = False
        self.router = Router(self.base_dir)
        self.ws_client = NapCatWsClient(self._load_ws_url(), self.on_event)
        self.sender = NapCatSender(self.ws_client)
        # 注入 sender 到 router
        self.router.set_sender(self.sender)
        # 定时消息调度服务
        self._scheduled_service = ScheduledMessageService(
            send_callback=self._send_scheduled_message
        )

    def _load_ws_url(self) -> str:
        config = CONFIG_MANAGER.get()
        return config.get("napcat", {}).get("ws_url", "ws://127.0.0.1:3001")

    async def _send_scheduled_message(self, group_id: str, text: str):
        """定时消息发送回调。"""
        try:
            await self.sender.send_group_text(group_id, text)
        except Exception as e:
            logger.error(f"Failed to send scheduled message to {group_id}: {e}")

    async def on_event(self, event):
        from app.services.msg_logger import log_incoming
        log_incoming(
            event_type=event.event_type,
            group_id=event.group_id or "",
            user_id=event.user_id or "",
            content=event.raw_text or "",
        )
        text = await self.router.route(event)
        if not text:
            return
        max_retries = 2
        for attempt in range(max_retries):
            try:
                if event.group_id:
                    await self.sender.send_group_text(event.group_id, text)
                else:
                    await self.sender.send_private_text(event.user_id, text)
                return
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    logger.warning(f"Send message timeout (attempt {attempt + 1}/{max_retries}), retrying: user_id={event.user_id}, group_id={event.group_id}")
                else:
                    logger.warning(f"Send message timeout after {max_retries} attempts: user_id={event.user_id}, group_id={event.group_id}, event_id={event.event_id}")
            except Exception as exc:
                logger.exception(f"Send message failed: event_id={event.event_id}, error={exc}")
                return

    async def run(self):
        Base.metadata.create_all(bind=engine)
        from app.services.msg_logger import init as msg_logger_init, log_system
        msg_logger_init(self.base_dir)
        log_system("bot_start", "机器人启动")
        self.router.reminder_service.start()
        self._scheduled_service.start()
        try:
            try:
                loaded = await self.router.load_mcp_tools()
                logger.info(f"MCP tools loaded: {loaded}")
            except Exception as exc:
                logger.exception(f"Load MCP tools failed: {exc}")
            # 从 config 读取 WebUI 配置
            config = CONFIG_MANAGER.get()
            webui_cfg = config.get("webui", {})
            webui_host = webui_cfg.get("host", "127.0.0.1")
            webui_port = webui_cfg.get("port", 7860)
            await HOST.start_webui(host=webui_host, port=webui_port)
            await self.ws_client.run_forever()
        finally:
            await self.close()

    async def stop(self):
        await self.ws_client.stop()

    async def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._scheduled_service.stop()
        except Exception as exc:
            logger.warning(f"Stop scheduled message service failed: {exc}")
        try:
            scheduler = self.router.reminder_service.scheduler
            if scheduler.running:
                scheduler.shutdown(wait=False)
        except Exception as exc:
            logger.warning(f"Stop reminder scheduler failed: {exc}")
        try:
            await self.router.close()
        except Exception as exc:
            logger.warning(f"Close router resources failed: {exc}")


@dataclass
class BotStatus:
    running: bool
    webui_running: bool
    ws_url: str


class AppHost:
    def __init__(self):
        logger.remove()
        logger.add(sys.stderr, level="INFO")
        self._bot_app: Optional[BotApplication] = None
        self._bot_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._webui_server = None
        self._webui_task: Optional[asyncio.Task] = None
        self._webui_enabled = False
        self._webui_external = False

    def _is_port_in_use(self, host: str, port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            return sock.connect_ex((host, port)) == 0
        finally:
            sock.close()

    async def start_bot(self) -> bool:
        async with self._lock:
            if self._bot_task and not self._bot_task.done():
                return False
            app = BotApplication()
            task = asyncio.create_task(app.run(), name="qq-bot-main")
            self._bot_app = app
            self._bot_task = task
            task.add_done_callback(self._on_bot_task_done)
            logger.info("Bot host started bot task")
            return True

    def _on_bot_task_done(self, task: asyncio.Task) -> None:
        try:
            exc = task.exception()
            if exc is not None:
                logger.exception(f"Bot task exited with error: {exc}")
            else:
                logger.info("Bot task exited")
        except asyncio.CancelledError:
            logger.info("Bot task cancelled")

    async def stop_bot(self) -> bool:
        async with self._lock:
            task = self._bot_task
            app = self._bot_app
            if app is None or task is None or task.done():
                return False
            await app.stop()
        try:
            await asyncio.wait_for(task, timeout=15)
        except asyncio.TimeoutError:
            logger.warning("Bot stop timed out, cancelling task")
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        finally:
            async with self._lock:
                self._bot_task = None
                self._bot_app = None
        logger.info("Bot host stopped bot task")
        return True

    async def restart_bot(self) -> None:
        await self.stop_bot()
        await self.start_bot()

    async def start_webui(self, host: str = "127.0.0.1", port: int = 7860) -> bool:
        async with self._lock:
            if self._webui_task and not self._webui_task.done():
                return False
            if self._is_port_in_use(host, port):
                self._webui_server = None
                self._webui_task = None
                self._webui_enabled = False
                self._webui_external = True
                logger.warning(f"WebUI port already in use, reuse existing service: http://{host}:{port}")
                return False
            import uvicorn
            from app.webui.server import app as webui_app

            config = uvicorn.Config(webui_app, host=host, port=port, reload=False, log_level="info")
            server = uvicorn.Server(config)
            task = asyncio.create_task(server.serve(), name="qq-bot-webui")
            self._webui_server = server
            self._webui_task = task
            self._webui_enabled = True
            self._webui_external = False
            logger.info(f"WebUI server starting at http://{host}:{port}")
            return True

    async def stop_webui(self) -> bool:
        async with self._lock:
            if self._webui_external:
                logger.warning("WebUI is external/already running; current host will not stop it")
                return False
            task = self._webui_task
            server = self._webui_server
            if task is None or task.done() or server is None:
                return False
            server.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=15)
        except asyncio.TimeoutError:
            logger.warning("WebUI stop timed out, cancelling task")
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        finally:
            async with self._lock:
                self._webui_task = None
                self._webui_server = None
                self._webui_enabled = False
                self._webui_external = False
        logger.info("WebUI server stopped")
        return True

    def get_status(self) -> BotStatus:
        bot_task = self._bot_task
        bot_running = bot_task is not None and not bot_task.done()
        webui_task = self._webui_task
        webui_running = (webui_task is not None and not webui_task.done()) or self._webui_external
        ws_url = "ws://127.0.0.1:3001"
        try:
            ws_url = self._bot_app.ws_client.ws_url if self._bot_app else ws_url
        except Exception:
            pass
        return BotStatus(running=bot_running, webui_running=webui_running, ws_url=ws_url)

    async def shutdown_all(self) -> None:
        await self.stop_bot()
        await self.stop_webui()


HOST = AppHost()
