async def add_keyword(keyword: str, reply_content: str) -> dict:
    return {
        "keyword": keyword,
        "reply_content": reply_content,
        "message": "关键词已加入（占位实现）。",
    }
