from datetime import datetime, timedelta


async def create_reminder(content: str, minutes: int = 30) -> dict:
    remind_at = datetime.now() + timedelta(minutes=minutes)
    return {
        "content": content,
        "minutes": minutes,
        "remind_at": remind_at.isoformat(timespec="seconds"),
        "note": "V1 当前返回占位结果；实际落库与调度在 ReminderService 中接入。",
    }
