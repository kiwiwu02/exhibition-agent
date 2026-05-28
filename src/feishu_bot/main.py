import asyncio
import logging
from contextlib import asynccontextmanager

import lark_oapi as lark
from fastapi import FastAPI

from .config import config
from .feishu_client import FeishuClient
from .user_context import UserContextManager
from .message_handler import MessageHandler

logger = logging.getLogger(__name__)

# Global instances
feishu_client = FeishuClient(config.FEISHU_APP_ID, config.FEISHU_APP_SECRET)
user_context = UserContextManager(context_timeout=config.CONTEXT_TIMEOUT)
message_handler = MessageHandler(feishu_client, user_context)

# WebSocket client and task references
_ws_client = None
_ws_task = None


def create_event_handler():
    def do_p2_im_message_receive_v1(data: lark.CustomizedEvent) -> None:
        loop = asyncio.get_event_loop()
        loop.create_task(message_handler.handle_message(data))

    handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
        .build()
    return handler


async def _run_ws_client_async():
    """Run WebSocket client within uvicorn's event loop."""
    import lark_oapi.ws.client as ws_module

    event_handler = create_event_handler()
    ws_client = lark.ws.Client(
        config.FEISHU_APP_ID,
        config.FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )

    # Patch the module-level loop to use the current running loop
    current_loop = asyncio.get_running_loop()
    ws_module.loop = current_loop

    try:
        await ws_client._connect()
        # Start ping loop as a background task
        ping_task = current_loop.create_task(ws_client._ping_loop())
        # Block until disconnected (receive loop handles reconnection)
        await ws_client._conn.wait_closed()
        ping_task.cancel()
    except Exception as e:
        logger.error(f"WebSocket client error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ws_task
    logger.info("Starting Feishu Bot Service...")

    # Run WebSocket client within uvicorn's event loop
    _ws_task = asyncio.create_task(_run_ws_client_async())
    logger.info("WebSocket client started")

    yield

    logger.info("Shutting down...")
    if _ws_task:
        _ws_task.cancel()


app = FastAPI(title="Feishu Bot Service", lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
