import time
from src.feishu_bot.user_context import UserContextManager


def test_store_and_get_text():
    manager = UserContextManager(context_timeout=600)
    manager.store_text("user1", "这是一家德国公司")
    text = manager.get_text("user1")
    assert text == "这是一家德国公司"


def test_get_text_clears_context():
    manager = UserContextManager(context_timeout=600)
    manager.store_text("user1", "补充信息")
    manager.get_text("user1")
    assert manager.get_text("user1") == ""


def test_context_timeout():
    manager = UserContextManager(context_timeout=0)
    manager.store_text("user1", "过期信息")
    time.sleep(0.1)
    assert manager.get_text("user1") == ""


def test_multiple_users():
    manager = UserContextManager(context_timeout=600)
    manager.store_text("user1", "用户1的信息")
    manager.store_text("user2", "用户2的信息")
    assert manager.get_text("user1") == "用户1的信息"
    assert manager.get_text("user2") == "用户2的信息"
