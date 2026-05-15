"""表情包生成插件 — 本地 Pillow 生成。"""
from __future__ import annotations

import os
import random
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# 模板目录（可在项目 data/meme_templates/ 下放置模板图片）
TEMPLATE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "meme_templates"

# 默认模板（纯色背景 + 文字）
DEFAULT_WIDTH = 400
DEFAULT_HEIGHT = 300
DEFAULT_BG_COLORS = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD"]


def _get_font(size: int = 32) -> ImageFont.FreeTypeFont:
    """获取字体，优先系统中文字体。"""
    font_candidates = [
        "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",     # 黑体
        "C:/Windows/Fonts/simsun.ttc",     # 宋体
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """自动换行。"""
    lines = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = font.getbbox(test_line)
        if bbox[2] - bbox[0] > max_width and current_line:
            lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    return lines


def _generate_simple_meme(top_text: str, bottom_text: str) -> str:
    """生成简单表情包（纯色背景 + 上下文字），返回文件路径。"""
    bg_color = random.choice(DEFAULT_BG_COLORS)
    img = Image.new("RGB", (DEFAULT_WIDTH, DEFAULT_HEIGHT), bg_color)
    draw = ImageDraw.Draw(img)
    font = _get_font(36)

    # 上方文字
    if top_text:
        lines = _wrap_text(top_text, font, DEFAULT_WIDTH - 40)
        y = 20
        for line in lines:
            bbox = font.getbbox(line)
            text_w = bbox[2] - bbox[0]
            x = (DEFAULT_WIDTH - text_w) // 2
            draw.text((x, y), line, fill="white", font=font)
            y += 45

    # 下方文字
    if bottom_text:
        lines = _wrap_text(bottom_text, font, DEFAULT_WIDTH - 40)
        total_h = len(lines) * 45
        y = DEFAULT_HEIGHT - total_h - 20
        for line in lines:
            bbox = font.getbbox(line)
            text_w = bbox[2] - bbox[0]
            x = (DEFAULT_WIDTH - text_w) // 2
            draw.text((x, y), line, fill="white", font=font)
            y += 45

    # 保存到临时文件
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    tmp.close()
    return tmp.name


async def generate_meme(top_text: str = "", bottom_text: str = "", template: str = "") -> dict:
    """生成表情包。"""
    top_text = (top_text or "").strip()
    bottom_text = (bottom_text or "").strip()

    if not top_text and not bottom_text:
        return {"success": False, "message": "请提供至少一行文字"}

    try:
        file_path = _generate_simple_meme(top_text, bottom_text)
        return {
            "success": True,
            "file_path": file_path,
            "message": "表情包生成成功",
        }
    except Exception as e:
        return {"success": False, "message": f"生成失败：{e}"}
