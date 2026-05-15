async def sign_in(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "score_delta": 5,
        "message": "签到成功，积分 +5",
    }


async def query_score(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "score": 0,
        "message": "当前为骨架版，尚未接入真实积分查询。",
    }
