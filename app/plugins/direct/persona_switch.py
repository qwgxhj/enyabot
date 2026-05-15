"""人设增强插件 — 群级人设切换与管理。"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

PERSONAS_DIR = Path(__file__).parent.parent.parent.parent / "personas"


async def list_personas() -> dict:
    """列出所有人设。"""
    if not PERSONAS_DIR.exists():
        return {"success": False, "message": "人设目录不存在"}

    personas = []
    for f in PERSONAS_DIR.glob("*.yaml"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            personas.append({
                "name": f.stem,
                "display_name": data.get("name", f.stem),
                "description": data.get("description", "")[:50],
            })
        except Exception:
            personas.append({"name": f.stem, "display_name": f.stem, "description": ""})

    if not personas:
        return {"success": True, "personas": [], "message": "当前没有人设文件"}

    lines = ["🎭 可用人设列表："]
    for p in personas:
        desc = f" — {p['description']}" if p['description'] else ""
        lines.append(f"  - {p['name']}{desc}")

    return {
        "success": True,
        "count": len(personas),
        "personas": personas,
        "message": "\n".join(lines),
    }


async def preview_persona(name: str) -> dict:
    """预览人设详情。"""
    name = (name or "").strip()
    if not name:
        return {"success": False, "message": "人设名称不能为空"}

    file_path = PERSONAS_DIR / f"{name}.yaml"
    if not file_path.exists():
        return {"success": False, "message": f"人设「{name}」不存在"}

    with open(file_path, "r", encoding="utf-8") as fh:
        content = fh.read()

    return {
        "success": True,
        "name": name,
        "content": content,
        "message": f"🎭 人设「{name}」预览：\n{content[:500]}{'...' if len(content) > 500 else ''}",
    }


async def switch_persona(group_platform_id: str, persona_name: str) -> dict:
    """切换群默认人设（需要写入 Group 表）。"""
    persona_name = (persona_name or "").strip()
    if not persona_name:
        return {"success": False, "message": "人设名称不能为空"}

    file_path = PERSONAS_DIR / f"{persona_name}.yaml"
    if not file_path.exists():
        available = [f.stem for f in PERSONAS_DIR.glob("*.yaml")] if PERSONAS_DIR.exists() else []
        return {"success": False, "message": f"人设「{persona_name}」不存在，可用：{', '.join(available) or '无'}"}

    # 写入 Group 表
    from app.db.session import db_session
    from app.models.group import Group
    from sqlalchemy import select

    with db_session() as db:
        group = db.execute(
            select(Group).where(Group.platform_group_id == group_platform_id)
        ).scalar_one_or_none()
        if not group:
            return {"success": False, "message": "群组未注册"}
        group.default_persona = persona_name

    return {
        "success": True,
        "message": f"✅ 已切换群人设为「{persona_name}」",
    }
