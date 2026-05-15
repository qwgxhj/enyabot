import time
import uuid
from app.schemas.event import Event


class NapCatEventParser:
    @staticmethod
    def parse(payload: dict) -> Event | None:
        post_type = payload.get("post_type")
        notice_type = payload.get("notice_type")

        # ── 群消息事件 ──────────────────────────────────
        if post_type == "message":
            message_type = payload.get("message_type")
            event_type = "group_message" if message_type == "group" else "private_message"
            message = payload.get("message")
            raw_message = payload.get("raw_message")
            mentions: list[str] = []
            attachments: list[dict] = []
            text_parts: list[str] = []
            self_id = str(payload.get("self_id")) if payload.get("self_id") is not None else None

            if isinstance(message, list):
                for seg in message:
                    if not isinstance(seg, dict):
                        continue
                    seg_type = seg.get("type")
                    seg_data = seg.get("data") or {}
                    if seg_type == "text":
                        text_parts.append(str(seg_data.get("text") or ""))
                    elif seg_type == "at":
                        qq = seg_data.get("qq")
                        if qq is not None:
                            mentions.append(str(qq))
                    else:
                        attachments.append({"type": seg_type, "data": seg_data})
                raw_text = "".join(text_parts).strip()
            else:
                raw_text = str(raw_message or message or "").strip()

            return Event(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                time=int(payload.get("time") or time.time()),
                self_id=self_id,
                group_id=str(payload.get("group_id")) if payload.get("group_id") else None,
                user_id=str(payload.get("user_id") or ""),
                message_id=str(payload.get("message_id")) if payload.get("message_id") else None,
                raw_text=raw_text,
                is_at_bot=bool(self_id and self_id in mentions),
                mentions=mentions,
                attachments=attachments,
                sender_role=((payload.get("sender") or {}).get("role") or "member"),
                raw_payload=payload,
            )

        # ── 群成员增加事件 ──────────────────────────────
        if post_type == "notice" and notice_type == "group_increase":
            self_id = str(payload.get("self_id")) if payload.get("self_id") is not None else None
            user_id = str(payload.get("user_id") or "")
            group_id = str(payload.get("group_id")) if payload.get("group_id") else None
            sub_type = payload.get("sub_type", "")  # approve / invite

            return Event(
                event_id=str(uuid.uuid4()),
                event_type="group_increase",
                time=int(payload.get("time") or time.time()),
                self_id=self_id,
                group_id=group_id,
                user_id=user_id,
                message_id=None,
                raw_text=f"__group_increase__:{sub_type}",
                is_at_bot=False,
                mentions=[],
                attachments=[],
                sender_role="member",
                raw_payload=payload,
            )

        # ── 群成员减少事件（可选扩展） ──────────────────
        if post_type == "notice" and notice_type == "group_decrease":
            # 预留：可在此处理退群事件
            pass

        return None
