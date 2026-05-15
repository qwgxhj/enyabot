import asyncio
import json
import uuid
from loguru import logger
import websockets

from app.adapters.event_parser import NapCatEventParser


class NapCatWsClient:
    def __init__(self, ws_url: str, on_event):
        self.ws_url = ws_url
        self.on_event = on_event
        self._running = False
        self._ws = None
        self._pending_calls: dict[str, asyncio.Future] = {}
        self._event_tasks: set[asyncio.Task] = set()

    @property
    def websocket(self):
        return self._ws

    async def call_api(self, action: str, params: dict, timeout: int = 15):
        ws = self.websocket
        if ws is None:
            raise RuntimeError("NapCat websocket is not connected")
        echo = f"{action}:{uuid.uuid4().hex}"
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_calls[echo] = future
        payload = {"action": action, "params": params, "echo": echo}
        await ws.send(json.dumps(payload, ensure_ascii=False))
        logger.info(f"NapCat action sent: {action}")
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"NapCat action timeout: action={action}, params={params}")
            raise
        finally:
            self._pending_calls.pop(echo, None)

    async def _handle_event(self, event):
        try:
            await self.on_event(event)
        except Exception as exc:
            logger.exception(f"Error while handling event {event.event_id}: {exc}")

    def _spawn_event_task(self, event):
        task = asyncio.create_task(self._handle_event(event))
        self._event_tasks.add(task)
        task.add_done_callback(self._event_tasks.discard)

    async def run_forever(self, reconnect_interval: int = 5):
        self._running = True
        while self._running:
            try:
                logger.info(f"Connecting to NapCat WS: {self.ws_url}")
                async with websockets.connect(self.ws_url) as ws:
                    self._ws = ws
                    logger.success("NapCat WebSocket connected")
                    async for message in ws:
                        payload = json.loads(message)
                        echo = payload.get("echo")
                        if echo and echo in self._pending_calls:
                            future = self._pending_calls.get(echo)
                            if future and not future.done():
                                future.set_result(payload)
                            continue
                        event = NapCatEventParser.parse(payload)
                        if event is not None:
                            self._spawn_event_task(event)
            except asyncio.CancelledError:
                logger.info("NapCat WS task cancelled")
                raise
            except Exception as exc:
                logger.exception(f"NapCat WS error: {exc}")
                await asyncio.sleep(reconnect_interval)
            finally:
                for future in self._pending_calls.values():
                    if not future.done():
                        future.cancel()
                self._pending_calls.clear()
                for task in list(self._event_tasks):
                    task.cancel()
                self._event_tasks.clear()
                self._ws = None

    async def stop(self):
        self._running = False
        if self._ws is not None:
            await self._ws.close()
