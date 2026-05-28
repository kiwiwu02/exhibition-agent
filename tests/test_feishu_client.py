import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.feishu_bot.feishu_client import FeishuClient


@pytest.fixture
def client():
    return FeishuClient(app_id="test_id", app_secret="test_secret")


def test_client_init(client):
    assert client.app_id == "test_id"
    assert client.app_secret == "test_secret"


@pytest.mark.asyncio
async def test_download_image_raises_without_message():
    client = FeishuClient(app_id="test_id", app_secret="test_secret")
    with pytest.raises(ValueError):
        await client.download_image(message=None)
