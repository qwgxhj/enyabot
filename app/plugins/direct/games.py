"""小游戏插件 — 猜数字、成语接龙、答题竞赛。"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field


# ── 猜数字 ─────────────────────────────────────────────

@dataclass
class GuessGame:
    answer: int
    creator_id: str
    min_val: int = 1
    max_val: int = 100
    attempts: int = 0
    max_attempts: int = 10
    created_at: float = field(default_factory=time.time)
    finished: bool = False


# {group_platform_id: GuessGame}
_guess_games: dict[str, GuessGame] = {}


async def start_guess(group_platform_id: str, creator_id: str, min_val: int = 1, max_val: int = 100) -> dict:
    """开始一局猜数字。"""
    if group_platform_id in _guess_games and not _guess_games[group_platform_id].finished:
        return {"success": False, "message": "当前有一局正在进行，先结束它吧"}

    answer = random.randint(min_val, max_val)
    _guess_games[group_platform_id] = GuessGame(
        answer=answer, creator_id=creator_id, min_val=min_val, max_val=max_val
    )

    return {
        "success": True,
        "message": f"🎮 猜数字开始！范围：{min_val} ~ {max_val}\n共 {_guess_games[group_platform_id].max_attempts} 次机会\n发送 /猜 <数字> 来猜",
    }


async def make_guess(group_platform_id: str, user_id: str, guess: int) -> dict:
    """提交猜测。"""
    game = _guess_games.get(group_platform_id)
    if not game or game.finished:
        return {"success": False, "message": "当前没有进行中的游戏，发送 /猜数字 开始"}

    game.attempts += 1

    if guess == game.answer:
        game.finished = True
        return {
            "success": True,
            "message": f"🎉 恭喜！答案就是 {game.answer}！用了 {game.attempts} 次",
            "finished": True,
        }

    if game.attempts >= game.max_attempts:
        game.finished = True
        return {
            "success": True,
            "message": f"💀 机会用完了！答案是 {game.answer}",
            "finished": True,
        }

    hint = "大了 ⬆️" if guess > game.answer else "小了 ⬇️"
    remaining = game.max_attempts - game.attempts
    return {
        "success": True,
        "message": f"{hint} 还剩 {remaining} 次机会",
        "finished": False,
    }


# ── 答题竞赛 ───────────────────────────────────────────

# 简易题库（实际使用时建议从文件或数据库加载）
QUIZ_QUESTIONS = [
    {"q": "中国的首都是哪里？", "options": ["北京", "上海", "广州", "深圳"], "answer": 0},
    {"q": "Python 是哪一年发布的？", "options": ["1989", "1991", "1995", "2000"], "answer": 1},
    {"q": "HTTP 状态码 404 表示什么？", "options": ["服务器错误", "未找到", "禁止访问", "重定向"], "answer": 1},
    {"q": "地球上最大的洋是？", "options": ["大西洋", "印度洋", "太平洋", "北冰洋"], "answer": 2},
    {"q": "光速大约是多少？", "options": ["30万km/s", "15万km/s", "3万km/s", "300万km/s"], "answer": 0},
    {"q": "TCP/IP 协议中 IP 是第几层？", "options": ["第1层", "第2层", "第3层", "第4层"], "answer": 2},
    {"q": "世界上面积最大的国家是？", "options": ["中国", "美国", "加拿大", "俄罗斯"], "answer": 3},
    {"q": "1KB 等于多少字节？", "options": ["512", "1000", "1024", "2048"], "answer": 2},
    {"q": "HTML 的全称是什么？", "options": ["Hyper Text Markup Language", "High Tech Modern Language", "Home Tool Markup Language", "Hyper Transfer Markup Language"], "answer": 0},
    {"q": "Java 是哪个公司开发的？", "options": ["Microsoft", "Sun Microsystems", "Google", "Apple"], "answer": 1},
]


@dataclass
class QuizGame:
    questions: list[dict]
    current: int = 0
    scores: dict[str, int] = field(default_factory=dict)
    finished: bool = False


# {group_platform_id: QuizGame}
_quiz_games: dict[str, QuizGame] = {}


async def start_quiz(group_platform_id: str, num_questions: int = 5) -> dict:
    """开始答题竞赛。"""
    if group_platform_id in _quiz_games and not _quiz_games[group_platform_id].finished:
        return {"success": False, "message": "当前有一局答题进行中"}

    num_questions = min(num_questions, len(QUIZ_QUESTIONS))
    questions = random.sample(QUIZ_QUESTIONS, num_questions)
    _quiz_games[group_platform_id] = QuizGame(questions=questions)

    q = questions[0]
    options_text = "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(q["options"]))
    return {
        "success": True,
        "message": f"📝 答题竞赛开始！共 {num_questions} 题\n\n第 1 题：{q['q']}\n{options_text}\n\n发送 /答题 <选项编号>",
    }


async def answer_quiz(group_platform_id: str, user_id: str, choice: int) -> dict:
    """提交答案。choice 从 1 开始。"""
    game = _quiz_games.get(group_platform_id)
    if not game or game.finished:
        return {"success": False, "message": "当前没有进行中的答题"}

    q = game.questions[game.current]
    correct = choice - 1 == q["answer"]

    if correct:
        game.scores[user_id] = game.scores.get(user_id, 0) + 1
        result = "✅ 正确！"
    else:
        result = f"❌ 错误！正确答案是：{q['options'][q['answer']]}"

    game.current += 1

    if game.current >= len(game.questions):
        game.finished = True
        # 排行
        ranking = sorted(game.scores.items(), key=lambda x: -x[1])
        rank_text = "\n".join(f"  {i+1}. {uid}: {score}分" for i, (uid, score) in enumerate(ranking))
        return {
            "success": True,
            "message": f"{result}\n\n🏁 答题结束！最终排名：\n{rank_text}",
            "finished": True,
        }

    # 下一题
    next_q = game.questions[game.current]
    options_text = "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(next_q["options"]))
    return {
        "success": True,
        "message": f"{result}\n\n第 {game.current + 1} 题：{next_q['q']}\n{options_text}",
        "finished": False,
    }
