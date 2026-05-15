from __future__ import annotations

import asyncio
import signal
import sys

from loguru import logger

from app.config.config_manager import ConfigManager
from app.host import BASE_DIR, HOST


_CONFIG_PATH = BASE_DIR / "config.yaml"


def _setup_logging():
    """配置 loguru：保留 stderr 输出，同时写入日志文件。"""
    log_dir = BASE_DIR / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_dir / "bot_{time:YYYY-MM-DD}.log"),
        level="DEBUG",
        rotation="00:00",       # 每天午夜轮转
        retention="30 days",    # 保留 30 天
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
        enqueue=True,           # 线程安全
        backtrace=True,
        diagnose=True,
    )


def main():
    _setup_logging()
    asyncio.run(_main())


async def _main():
    ConfigManager().load(_CONFIG_PATH)
    await HOST.start_bot()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_signal(sig: int, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        stop_event.set()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)
    else:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    try:
        await stop_event.wait()
    finally:
        logger.info("Shutting down...")
        await HOST.shutdown_all()


if __name__ == "__main__":
    main()
