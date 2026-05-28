import json
import logging
import time
from pathlib import Path

import httpx
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    GetMessageResourceRequest,
    PatchMessageRequest,
    PatchMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from .config import config

logger = logging.getLogger(__name__)


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()
        self._progress_message_id: str | None = None

    async def download_image(self, message) -> str:
        if message is None:
            raise ValueError("message is required")

        content = json.loads(message.content)
        image_key = content.get("image_key")
        if not image_key:
            raise ValueError("No image_key in message content")

        # Use SDK to download image resource
        request = GetMessageResourceRequest.builder() \
            .message_id(message.message_id) \
            .file_key(image_key) \
            .type("image") \
            .build()

        response = self._client.im.v1.message_resource.get(request)
        if not response.success():
            raise Exception(f"Download failed: {response.code} {response.msg}")

        attachments_dir = Path(config.ATTACHMENTS_DIR)
        attachments_dir.mkdir(parents=True, exist_ok=True)

        filename = f"img_{int(time.time() * 1000)}_0.jpg"
        filepath = attachments_dir / filename
        filepath.write_bytes(response.file.read())

        logger.info(f"Image downloaded: {filepath}")
        return str(filepath)

    async def reply(self, message_id: str, content: str) -> str | None:
        """回复消息，返回新消息的 message_id"""
        body = ReplyMessageRequestBody.builder() \
            .msg_type("text") \
            .content(json.dumps({"text": content})) \
            .build()

        request = ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(body) \
            .build()

        response = self._client.im.v1.message.reply(request)
        if not response.success():
            logger.error(f"Reply failed: {response.code} {response.msg}")
            return None
        return response.data.message_id if response.data else None

    async def reply_card(self, message_id: str, card: dict) -> str | None:
        """回复消息卡片，返回新消息的 message_id"""
        body = ReplyMessageRequestBody.builder() \
            .msg_type("interactive") \
            .content(json.dumps(card)) \
            .build()

        request = ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(body) \
            .build()

        response = self._client.im.v1.message.reply(request)
        if not response.success():
            logger.error(f"Reply card failed: {response.code} {response.msg}")
            return None
        return response.data.message_id if response.data else None

    async def update_card(self, message_id: str, card: dict) -> bool:
        """编辑已有的消息卡片"""
        body = PatchMessageRequestBody.builder() \
            .msg_type("interactive") \
            .content(json.dumps(card)) \
            .build()

        request = PatchMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(body) \
            .build()

        response = self._client.im.v1.message.patch(request)
        if not response.success():
            logger.error(f"Update card failed: {response.code} {response.msg}")
            return False
        return True

    def reset_progress(self):
        """重置进度消息追踪（新处理开始时调用）"""
        self._progress_message_id = None

    async def send_progress(self, message_id: str, message: str) -> bool:
        """发送或更新进度消息 - 使用卡片格式，支持原地更新"""
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "⏳ 处理中..."},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": message}}
            ]
        }
        if self._progress_message_id:
            return await self.update_card(self._progress_message_id, card)
        else:
            new_id = await self.reply_card(message_id, card)
            if new_id:
                self._progress_message_id = new_id
            return new_id is not None
