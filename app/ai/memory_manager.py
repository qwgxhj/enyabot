from __future__ import annotations

from sqlalchemy import select, or_

from app.db.session import SessionLocal, db_session
from app.models.memory import Memory


class MemoryManager:
    def recall(self, scope_type: str, scope_id: str, query: str | None = None, limit: int = 5) -> list[str]:
        """Recall memories, optionally filtering by keyword.

        When *query* is provided, results that contain any of the query
        keywords are ranked above non-matching results.  The final order is:
        keyword-matched first (by importance desc, updated_at desc),
        then the rest (by importance desc, updated_at desc).
        """
        with SessionLocal() as db:
            stmt = select(Memory).where(
                Memory.scope_type == scope_type,
                Memory.scope_id == scope_id,
            )
            if query:
                keywords = [kw.strip() for kw in query.split() if kw.strip()]
                if keywords:
                    like_clauses = [Memory.content.ilike(f"%{kw}%") for kw in keywords]
                    stmt = stmt.order_by(
                        or_(*like_clauses).desc(),
                        Memory.importance.desc(),
                        Memory.updated_at.desc(),
                    )
                else:
                    stmt = stmt.order_by(Memory.importance.desc(), Memory.updated_at.desc())
            else:
                stmt = stmt.order_by(Memory.importance.desc(), Memory.updated_at.desc())
            rows = db.execute(stmt.limit(limit)).scalars().all()
            return [row.content for row in rows]

    def remember(self, scope_type: str, scope_id: str, content: str, importance: int = 1, source_type: str | None = None, source_ref: str | None = None) -> None:
        with db_session() as db:
            db.add(Memory(scope_type=scope_type, scope_id=scope_id, content=content, importance=importance, source_type=source_type, source_ref=source_ref))
