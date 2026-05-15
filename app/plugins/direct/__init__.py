"""Direct 类插件统一导出。"""
from app.plugins.direct.group_admin import kick_member, mute_member
from app.plugins.direct.keyword import add_keyword
from app.plugins.direct.memory import recall_memory, remember_fact
from app.plugins.direct.reminder import create_reminder
from app.plugins.direct.score import query_score, sign_in
from app.plugins.direct.vote import create_vote, cast_vote, vote_result, close_vote
from app.plugins.direct.welcome import set_welcome, get_welcome, clear_welcome, set_verify_question, check_verify, on_member_join
from app.plugins.direct.scheduler_msg import create_scheduled_message, list_scheduled_messages, delete_scheduled_message, toggle_scheduled_message
from app.plugins.direct.calendar_event import add_event, list_events, delete_event
from app.plugins.direct.keyword_plus import add_keyword_rule, list_keyword_rules, delete_keyword_rule, match_keyword
from app.plugins.direct.games import start_guess, make_guess, start_quiz, answer_quiz
from app.plugins.direct.quote import add_quote, random_quote, search_quote, list_quotes
from app.plugins.direct.countdown import add_countdown, list_countdowns, delete_countdown
from app.plugins.direct.chat_summary import summarize_chat
from app.plugins.direct.persona_switch import list_personas, preview_persona, switch_persona

__all__ = [
    "create_reminder",
    "sign_in",
    "query_score",
    "mute_member",
    "kick_member",
    "add_keyword",
    "remember_fact",
    "recall_memory",
    "create_vote",
    "cast_vote",
    "vote_result",
    "close_vote",
    "set_welcome",
    "get_welcome",
    "clear_welcome",
    "set_verify_question",
    "check_verify",
    "on_member_join",
    "create_scheduled_message",
    "list_scheduled_messages",
    "delete_scheduled_message",
    "toggle_scheduled_message",
    "add_event",
    "list_events",
    "delete_event",
    "add_keyword_rule",
    "list_keyword_rules",
    "delete_keyword_rule",
    "match_keyword",
    "start_guess",
    "make_guess",
    "start_quiz",
    "answer_quiz",
    "add_quote",
    "random_quote",
    "search_quote",
    "list_quotes",
    "add_countdown",
    "list_countdowns",
    "delete_countdown",
    "summarize_chat",
    "list_personas",
    "preview_persona",
    "switch_persona",
]
