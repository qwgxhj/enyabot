"""GitHub 集成插件 — 仓库查询 / Release 监控。"""
from __future__ import annotations

import os

import httpx

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

HEADERS = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"


async def repo_info(owner: str, repo: str) -> dict:
    """查询 GitHub 仓库信息。"""
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    if not owner or not repo:
        return {"success": False, "message": "格式：owner/repo，如 openclaw/openclaw"}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}", headers=HEADERS)
            if resp.status_code == 404:
                return {"success": False, "message": f"仓库 {owner}/{repo} 不存在"}
            resp.raise_for_status()
            data = resp.json()

        return {
            "success": True,
            "full_name": data.get("full_name", ""),
            "description": data.get("description", ""),
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "language": data.get("language", ""),
            "license": (data.get("license") or {}).get("spdx_id", "无"),
            "url": data.get("html_url", ""),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "message": "查询成功",
        }
    except Exception as e:
        return {"success": False, "message": f"查询失败：{e}"}


async def repo_releases(owner: str, repo: str, limit: int = 3) -> dict:
    """查询仓库最近 Release。"""
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    if not owner or not repo:
        return {"success": False, "message": "格式：owner/repo"}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/releases",
                headers=HEADERS,
                params={"per_page": limit},
            )
            resp.raise_for_status()
            data = resp.json()

        releases = []
        for r in data[:limit]:
            releases.append({
                "tag": r.get("tag_name", ""),
                "name": r.get("name", ""),
                "published_at": r.get("published_at", ""),
                "url": r.get("html_url", ""),
                "prerelease": r.get("prerelease", False),
            })

        return {
            "success": True,
            "count": len(releases),
            "releases": releases,
            "message": f"最近 {len(releases)} 个 Release",
        }
    except Exception as e:
        return {"success": False, "message": f"查询失败：{e}"}
