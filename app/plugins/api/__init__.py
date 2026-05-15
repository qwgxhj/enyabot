"""API 类插件统一导出。"""
from app.plugins.api.entertainment import kfc_crazy_thursday, random_superpower
from app.plugins.api.identity import name_duplicate_query
from app.plugins.api.ip_lookup import ip_location_query
from app.plugins.api.media import media_parse
from app.plugins.api.weather import weather_query
from app.plugins.api.translator import translate_text
from app.plugins.api.image_search import image_search
from app.plugins.api.music import search_music, get_song_url
from app.plugins.api.meme import generate_meme
from app.plugins.api.github import repo_info, repo_releases

__all__ = [
    "weather_query",
    "ip_location_query",
    "random_superpower",
    "kfc_crazy_thursday",
    "name_duplicate_query",
    "media_parse",
    "translate_text",
    "image_search",
    "search_music",
    "get_song_url",
    "generate_meme",
    "repo_info",
    "repo_releases",
]
