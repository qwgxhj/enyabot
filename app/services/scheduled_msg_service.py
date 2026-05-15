"""定时消息调度服务 — 基于 APScheduler，管理 cron 定时消息 + 日程提醒 + 倒数日提醒。"""
from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.scheduled_message import ScheduledMessage
from app.models.calendar_event import CalendarEvent
from app.models.countdown import Countdown


class ScheduledMessageService:
    """定时消息 + 日程提醒 + 倒数日提醒的统一调度服务。"""

    def __init__(self, send_callback=None):
        """
        Args:
            send_callback: 异步回调函数，签名 async (group_id: str, text: str) -> None
                           用于发送消息到群。如果为 None 则仅记录日志。
        """
        self.scheduler = AsyncIOScheduler()
        self._send_callback = send_callback

    def start(self):
        """启动调度器并加载所有定时任务。"""
        if not self.scheduler.running:
            self.scheduler.start()
        self._load_scheduled_messages()
        self._register_calendar_checker()
        self._register_countdown_checker()
        logger.info("ScheduledMessageService started")

    def stop(self):
        """停止调度器。"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def _send_to_group(self, group_id: str, text: str):
        """发送消息到群。"""
        if self._send_callback:
            try:
                await self._send_callback(group_id, text)
            except Exception as e:
                logger.error(f"Failed to send scheduled message to group {group_id}: {e}")
        else:
            logger.info(f"[ScheduledMessage] group={group_id}: {text}")

    # ── 定时消息管理 ────────────────────────────────────

    def _load_scheduled_messages(self):
        """从数据库加载所有启用的定时消息并注册 cron job。"""
        try:
            with SessionLocal() as db:
                messages = db.execute(
                    select(ScheduledMessage).where(ScheduledMessage.enabled == True)
                ).scalars().all()

            for msg in messages:
                self._add_cron_job(msg.id, msg.group_platform_id, msg.content, msg.cron_expr)

            logger.info(f"Loaded {len(messages)} scheduled messages")
        except Exception as e:
            logger.warning(f"Failed to load scheduled messages: {e}")

    def _add_cron_job(self, msg_id: int, group_id: str, content: str, cron_expr: str):
        """注册一个 cron job。"""
        job_id = f"scheduled_msg_{msg_id}"
        # 移除已有的同名 job
        existing = self.scheduler.get_job(job_id)
        if existing:
            self.scheduler.remove_job(job_id)

        try:
            parts = cron_expr.strip().split()
            if len(parts) != 5:
                logger.warning(f"Invalid cron expression for msg {msg_id}: {cron_expr}")
                return
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
            self.scheduler.add_job(
                self._execute_scheduled_message,
                trigger=trigger,
                id=job_id,
                args=[msg_id, group_id, content],
                replace_existing=True,
            )
            logger.debug(f"Added cron job {job_id}: {cron_expr}")
        except Exception as e:
            logger.warning(f"Failed to add cron job for msg {msg_id}: {e}")

    async def _execute_scheduled_message(self, msg_id: int, group_id: str, content: str):
        """执行定时消息。"""
        logger.info(f"Executing scheduled message #{msg_id} -> group {group_id}")
        await self._send_to_group(group_id, content)
        # 更新最后执行时间
        try:
            with SessionLocal() as db:
                msg = db.get(ScheduledMessage, msg_id)
                if msg:
                    msg.last_run_at = datetime.utcnow()
                    db.commit()
        except Exception as e:
            logger.warning(f"Failed to update last_run_at for msg {msg_id}: {e}")

    def add_scheduled_message(self, msg_id: int, group_id: str, content: str, cron_expr: str):
        """动态添加定时消息（创建后调用）。"""
        self._add_cron_job(msg_id, group_id, content, cron_expr)

    def remove_scheduled_message(self, msg_id: int):
        """移除定时消息。"""
        job_id = f"scheduled_msg_{msg_id}"
        existing = self.scheduler.get_job(job_id)
        if existing:
            self.scheduler.remove_job(job_id)

    def toggle_scheduled_message(self, msg_id: int, group_id: str, content: str, cron_expr: str, enabled: bool):
        """启用/暂停定时消息。"""
        if enabled:
            self._add_cron_job(msg_id, group_id, content, cron_expr)
        else:
            self.remove_scheduled_message(msg_id)

    # ── 日程提醒 ────────────────────────────────────────

    def _register_calendar_checker(self):
        """注册每分钟检查日程提醒的任务。"""
        self.scheduler.add_job(
            self._check_calendar_reminders,
            "interval",
            minutes=1,
            id="calendar_reminder_checker",
            replace_existing=True,
        )

    async def _check_calendar_reminders(self):
        """检查需要提醒的日程事件。"""
        now = datetime.utcnow()
        try:
            with SessionLocal() as db:
                events = db.execute(
                    select(CalendarEvent).where(
                        CalendarEvent.reminded == False,
                        CalendarEvent.event_time <= now + timedelta(minutes=60),
                    )
                ).scalars().all()

                for event in events:
                    remind_at = event.event_time - timedelta(minutes=event.remind_before_min)
                    if now >= remind_at:
                        group_id = event.group_platform_id
                        if group_id:
                            time_str = event.event_time.strftime("%H:%M")
                            msg = f"📅 日程提醒：{event.title}\n时间：{time_str}"
                            if event.location:
                                msg += f"\n地点：{event.location}"
                            await self._send_to_group(group_id, msg)
                        event.reminded = True

                db.commit()
        except Exception as e:
            logger.warning(f"Calendar reminder check failed: {e}")

    # ── 倒数日提醒 ──────────────────────────────────────

    def _register_countdown_checker(self):
        """注册每天早上 8 点检查倒数日的任务。"""
        self.scheduler.add_job(
            self._check_countdowns,
            CronTrigger(hour=8, minute=0),
            id="countdown_daily_checker",
            replace_existing=True,
        )

    async def _check_countdowns(self):
        """检查倒数日并发送提醒。"""
        today = datetime.utcnow().date()
        try:
            with SessionLocal() as db:
                countdowns = db.execute(
                    select(Countdown).where(Countdown.remind_daily == True)
                ).scalars().all()

                # 按群分组
                grouped: dict[str, list] = {}
                for cd in countdowns:
                    group_id = cd.group_platform_id
                    if not group_id:
                        continue
                    days_left = (cd.target_date - today).days
                    if group_id not in grouped:
                        grouped[group_id] = []
                    grouped[group_id].append((cd.name, days_left))

                for group_id, items in grouped.items():
                    lines = ["⏰ 倒数日提醒："]
                    for name, days in items:
                        if days > 0:
                            lines.append(f"  {name}：还有 {days} 天")
                        elif days == 0:
                            lines.append(f"  {name}：就是今天！🎉")
                        else:
                            lines.append(f"  {name}：已过去 {abs(days)} 天")
                    await self._send_to_group(group_id, "\n".join(lines))

        except Exception as e:
            logger.warning(f"Countdown check failed: {e}")
