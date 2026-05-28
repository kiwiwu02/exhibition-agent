import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.feishu_bot.message_handler import MessageHandler


@pytest.fixture
def handler():
    feishu_client = AsyncMock()
    user_context = MagicMock()
    return MessageHandler(feishu_client, user_context)


def test_handler_init(handler):
    assert handler.feishu_client is not None
    assert handler.user_context is not None


@pytest.mark.asyncio
async def test_handle_text_stores_context(handler):
    event = MagicMock()
    event.message.message_type = "text"
    event.message.message_id = "msg_123"
    event.message.content = '{"text": "这是一家德国公司"}'
    event.sender.sender_id.open_id = "user_1"

    await handler.handle_message(event)

    handler.user_context.store_text.assert_called_once_with("user_1", "这是一家德国公司")
    handler.feishu_client.reply.assert_called_once()


@pytest.mark.asyncio
async def test_handle_image_calls_process_card(handler):
    event = MagicMock()
    event.message.message_type = "image"
    event.message.message_id = "msg_456"
    event.message.content = '{"image_key": "img_xxx"}'
    event.sender.sender_id.open_id = "user_2"

    handler.feishu_client.download_image = AsyncMock(return_value="/tmp/test.jpg")
    handler.user_context.get_text.return_value = "补充信息"

    with patch.object(handler, "_run_process_card", new_callable=AsyncMock) as mock_run, \
         patch.object(handler, "_cleanup_image") as mock_cleanup:
        mock_run.return_value = "处理成功"
        await handler.handle_message(event)

    handler.feishu_client.reply.assert_called()
    mock_cleanup.assert_called_once_with("/tmp/test.jpg")


@pytest.mark.asyncio
async def test_handle_unknown_type_ignored(handler):
    event = MagicMock()
    event.message.message_type = "file"
    event.sender.sender_id.open_id = "user_3"

    await handler.handle_message(event)

    handler.feishu_client.reply.assert_not_called()
