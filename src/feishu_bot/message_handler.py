import asyncio
import json
import logging
import os
import time
from typing import Callable

from .feishu_client import FeishuClient
from .user_context import UserContextManager
from .config import config

logger = logging.getLogger(__name__)


class MessageHandler:
    def __init__(self, feishu_client: FeishuClient, user_context: UserContextManager):
        self.feishu_client = feishu_client
        self.user_context = user_context

    async def handle_message(self, event) -> None:
        message = event.event.message
        sender = event.event.sender
        user_id = sender.sender_id.open_id
        message_id = message.message_id

        logger.info(f"收到消息: type={message.message_type}, user={user_id}, message_id={message_id}")

        if message.message_type == "text":
            await self._handle_text(message_id, user_id, message)
        elif message.message_type == "image":
            await self._handle_image(message_id, user_id, message)
        elif message.message_type == "post":
            await self._handle_post(message_id, user_id, message)
        else:
            logger.warning(f"不支持的消息类型: {message.message_type}, content={message.content[:200] if message.content else 'None'}")

    async def _handle_text(self, message_id: str, user_id: str, message) -> None:
        content = json.loads(message.content)
        text = content.get("text", "").strip()

        if not text:
            return

        logger.info(f"收到文本消息: user={user_id}, text={text}")

        # 检查是否是重复决策回复
        has_pending = self.user_context.has_pending_duplicate(user_id)
        logger.info(f"has_pending_duplicate={has_pending}")
        if has_pending:
            decision = self._parse_duplicate_decision(text)
            logger.info(f"parsed_decision={decision}")
            if decision:
                await self._handle_duplicate_decision(message_id, user_id, decision)
                return

        # 普通补充信息
        self.user_context.store_text(user_id, text)
        await self.feishu_client.reply(message_id, "已收到补充信息，发送名片图片后将一起处理")
        logger.info(f"Stored text context for user {user_id}: {text[:50]}...")

    def _parse_duplicate_decision(self, text: str) -> str:
        """解析用户对重复记录的决策"""
        text = text.strip().lower()
        if text in ("合并", "merge", "是", "yes", "y"):
            return "merge"
        if text in ("新建", "create", "否", "no", "n", "新记录"):
            return "create"
        return ""

    async def _handle_duplicate_decision(
        self, message_id: str, user_id: str, decision: str
    ) -> None:
        """处理用户对重复记录的决策"""
        pending = self.user_context.get_pending_duplicate(user_id)
        if not pending:
            await self.feishu_client.reply(message_id, "决策已过期，请重新发送名片")
            return

        await self.feishu_client.reply(message_id, f"正在{'合并' if decision == 'merge' else '创建新记录'}...")

        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
            from src.agent import ExhibitionAgent
            from src.bitable import save_card_to_bitable, update_record_fields

            agent = ExhibitionAgent()
            card = pending["card"]
            dup_result = pending["dup_result"]

            if decision == "merge":
                # 合并操作很快，同步执行
                result = agent.handle_duplicate_decision(card, dup_result, decision)
                response = agent.format_response(result)
                if isinstance(response, dict):
                    await self.feishu_client.reply_card(message_id, response)
                else:
                    await self.feishu_client.reply(message_id, response)
            else:
                # 新建：先创建记录并回复，再异步执行背调
                record_id = save_card_to_bitable(card)
                if not record_id:
                    await self.feishu_client.reply(message_id, "创建记录失败")
                    return

                # 立即回复卡片
                immediate_result = {
                    "success": True,
                    "action": "created",
                    "record_id": record_id,
                    "card": card,
                    "duplicate_info": dup_result,
                }
                response = agent.format_response(immediate_result)
                if isinstance(response, dict):
                    await self.feishu_client.reply_card(message_id, response)
                else:
                    await self.feishu_client.reply(message_id, response)

                # 异步执行背调
                loop = asyncio.get_event_loop()
                loop.run_in_executor(
                    None,
                    self._run_background_check,
                    agent, card, record_id, message_id, loop,
                )

        except Exception as e:
            logger.error(f"处理重复决策失败: {e}")
            await self.feishu_client.reply(message_id, f"处理失败: {e}")

    def _run_background_check(self, agent, card, record_id, message_id, loop):
        """在后台线程中执行背调"""
        try:
            logger.info(f"后台开始背调: company={card.company_name}, record_id={record_id}")
            result = agent._perform_background_check(card, record_id)
            logger.info(f"后台背调完成: record_id={record_id}")

            # 通知用户调研完成
            report_url = result.get("report_url") if result else None
            if report_url:
                asyncio.run_coroutine_threadsafe(
                    self._notify_research_complete(message_id, card.company_name, report_url),
                    loop,
                )
        except Exception as e:
            logger.error(f"后台背调失败: {e}")

    async def _notify_research_complete(self, message_id: str, company_name: str, report_url: str):
        """通知用户调研完成"""
        try:
            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "📄 调研报告已生成"},
                    "template": "green"
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"**{company_name}** 的调研报告已完成"}},
                    {"tag": "action", "actions": [{
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看调研报告"},
                        "url": report_url,
                        "type": "primary"
                    }]}
                ]
            }
            await self.feishu_client.reply_card(message_id, card)
        except Exception as e:
            logger.error(f"通知调研完成失败: {e}")

    async def _handle_post(self, message_id: str, user_id: str, message) -> None:
        """处理 post 类型消息（图片+文字富文本）"""
        try:
            content = json.loads(message.content)
            raw_json = json.dumps(content, ensure_ascii=False)
            logger.info(f"Post 完整内容长度: {len(raw_json)}")
            logger.info(f"Post 完整内容: {raw_json[:2000]}")

            # 提取图片和文字
            image_key = None
            post_texts = []
            title = content.get("title", "")
            if title:
                post_texts.append(title)

            for block in content.get("content", []):
                for element in block:
                    tag = element.get("tag", "")
                    if tag == "img":
                        image_key = element.get("image_key")
                    elif tag == "text":
                        text = element.get("text", "").strip()
                        if text:
                            post_texts.append(text)
                    elif tag == "a":
                        # 链接中的文字
                        text = element.get("text", "").strip()
                        href = element.get("href", "")
                        if text:
                            post_texts.append(text)
                        if href:
                            post_texts.append(href)

            if not image_key:
                logger.warning(f"Post 消息中未找到图片: {content}")
                await self.feishu_client.reply(message_id, "未找到图片，请直接发送名片图片")
                return

            # 合并文字：post 中的文字 + 之前存储的补充文字
            post_text = "\n".join(post_texts) if post_texts else ""
            stored_text = self.user_context.get_text(user_id) or ""
            text_context = (post_text + "\n" + stored_text).strip() if (post_text or stored_text) else ""
            logger.info(f"Post 提取文字: post_texts={post_texts}, post_text={post_text[:100]}, stored_text={stored_text[:100]}, combined={text_context[:100]}")

            # 使用 SDK 下载图片
            from lark_oapi.api.im.v1 import GetMessageResourceRequest
            from pathlib import Path

            request = GetMessageResourceRequest.builder() \
                .message_id(message_id) \
                .file_key(image_key) \
                .type("image") \
                .build()

            response = self.feishu_client._client.im.v1.message_resource.get(request)
            if not response.success():
                raise Exception(f"下载图片失败: {response.code} {response.msg}")

            attachments_dir = Path(config.ATTACHMENTS_DIR)
            attachments_dir.mkdir(parents=True, exist_ok=True)
            filename = f"img_{int(time.time() * 1000)}_0.jpg"
            filepath = attachments_dir / filename
            filepath.write_bytes(response.file.read())
            logger.info(f"Post 图片下载成功: {filepath}")

            result = await self._run_process_card(str(filepath), text_context, message_id)

            logger.info(f"Post 处理完成, result type={type(result).__name__}, is_dict={isinstance(result, dict)}")

            pending_file = None
            if isinstance(result, dict) and "__pending_dup_file__" in result:
                pending_file = result.pop("__pending_dup_file__")
                result = result.get("card", result)

            if pending_file:
                await self._store_duplicate_context(user_id, pending_file)

            if isinstance(result, dict):
                logger.info(f"Post 发送卡片回复, message_id={message_id}")
                reply_id = await self.feishu_client.reply_card(message_id, result)
                logger.info(f"Post 卡片回复结果: reply_id={reply_id}")
            else:
                logger.info(f"Post 发送文本回复, message_id={message_id}")
                reply_id = await self.feishu_client.reply(message_id, result)
                logger.info(f"Post 文本回复结果: reply_id={reply_id}")

            if filepath.exists():
                filepath.unlink()

        except Exception as e:
            logger.error(f"Post 处理失败: {e}", exc_info=True)
            await self.feishu_client.reply(message_id, f"图片处理失败: {e}")

    async def _handle_image(self, message_id: str, user_id: str, message) -> None:
        try:
            image_path = await self.feishu_client.download_image(message)
            text_context = self.user_context.get_text(user_id)
            result = await self._run_process_card(image_path, text_context, message_id)

            logger.info(f"处理完成, result type={type(result).__name__}, is_dict={isinstance(result, dict)}")

            # 检查是否有待决策的重复记录
            pending_file = None
            if isinstance(result, dict) and "__pending_dup_file__" in result:
                pending_file = result.pop("__pending_dup_file__")
                result = result.get("card", result)

            if pending_file:
                await self._store_duplicate_context(user_id, pending_file)

            # 根据结果类型选择回复方式
            if isinstance(result, dict):
                logger.info(f"发送卡片回复, message_id={message_id}")
                reply_id = await self.feishu_client.reply_card(message_id, result)
                logger.info(f"卡片回复结果: reply_id={reply_id}")
            else:
                logger.info(f"发送文本回复, message_id={message_id}")
                reply_id = await self.feishu_client.reply(message_id, result)
                logger.info(f"文本回复结果: reply_id={reply_id}")
            self._cleanup_image(image_path)

        except Exception as e:
            logger.error(f"Image processing failed: {e}", exc_info=True)
            await self.feishu_client.reply(message_id, f"图片处理失败: {e}")

    async def _store_duplicate_context(self, user_id: str, pending_file: str) -> None:
        """从临时文件读取重复信息并存储到用户上下文"""
        try:
            import pickle
            logger.info(f"Storing pending duplicate: user={user_id}, file={pending_file}, exists={os.path.exists(pending_file)}")
            if os.path.exists(pending_file):
                with open(pending_file, "rb") as f:
                    pending_data = pickle.load(f)
                self.user_context.store_pending_duplicate(user_id, pending_data)
                os.remove(pending_file)
                logger.info(f"Stored pending duplicate for user {user_id}")
            else:
                logger.warning(f"Pending file not found: {pending_file}")
        except Exception as e:
            logger.warning(f"Failed to store pending duplicate: {e}")

    async def _run_process_card(
        self, image_path: str, text_context: str, message_id: str
    ) -> str:
        self.feishu_client.reset_progress()
        loop = asyncio.get_event_loop()

        def on_progress(step: str, message: str):
            asyncio.run_coroutine_threadsafe(
                self.feishu_client.send_progress(message_id, message), loop
            )

        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                self._call_process_card,
                image_path,
                text_context,
                on_progress,
            ),
            timeout=config.PROCESS_CARD_TIMEOUT,
        )
        return result

    def _call_process_card(
        self, image_path: str, text_context: str, on_progress: Callable
    ) -> str:
        from process_card import main_with_progress
        return main_with_progress(image_path, text_context, on_progress)

    def _cleanup_image(self, image_path: str) -> None:
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                logger.info(f"Cleaned up image: {image_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup image: {e}")
