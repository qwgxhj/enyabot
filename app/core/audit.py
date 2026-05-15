from __future__ import annotations

import json

from loguru import logger

from app.db.session import db_session
from app.models.audit_log import AuditLog


def audit(
    action: str,
    operator_user_id: str | None = None,
    group_id: str | None = None,
    detail: dict | None = None,
    target_id: str | None = None,
    result: str | None = None,
) -> None:
    """Write audit log to both logger and database."""
    detail = detail or {}
    logger.bind(audit=True).info({
        "action": action,
        "operator_user_id": operator_user_id,
        "group_id": group_id,
        "detail": detail,
    })
    try:
        with db_session() as db:
            db.add(AuditLog(
                action=action,
                operator_user_id=operator_user_id,
                group_id=group_id,
                target_id=target_id,
                params_json=json.dumps(detail, ensure_ascii=False) if detail else None,
                result=result,
            ))
    except Exception as exc:
        logger.warning(f"Audit DB write failed: {exc}")
