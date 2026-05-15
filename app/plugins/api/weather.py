from datetime import datetime


async def weather_query(city: str) -> dict:
    return {
        "city": city,
        "weather": "晴",
        "temp": "25℃",
        "note": "V1 默认占位实现，建议后续接入真实天气 API。",
        "time": datetime.now().isoformat(),
    }
