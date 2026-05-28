import time
from typing import Dict, Tuple, Optional


class UserContextManager:
    def __init__(self, context_timeout: int = 600):
        self._contexts: Dict[str, Tuple[str, float]] = {}
        self._pending_duplicates: Dict[str, dict] = {}  # user_id -> pending decision data
        self._timeout = context_timeout

    def store_text(self, user_id: str, text: str) -> None:
        self._contexts[user_id] = (text, time.time())

    def get_text(self, user_id: str) -> str:
        if user_id not in self._contexts:
            return ""
        text, stored_at = self._contexts[user_id]
        if time.time() - stored_at > self._timeout:
            del self._contexts[user_id]
            return ""
        del self._contexts[user_id]
        return text

    def store_pending_duplicate(self, user_id: str, data: dict) -> None:
        """存储待用户决策的重复记录信息"""
        self._pending_duplicates[user_id] = {
            "data": data,
            "stored_at": time.time(),
        }

    def get_pending_duplicate(self, user_id: str) -> Optional[dict]:
        """获取并消费待决策的重复记录信息（一次性）"""
        if user_id not in self._pending_duplicates:
            return None
        entry = self._pending_duplicates[user_id]
        if time.time() - entry["stored_at"] > self._timeout:
            del self._pending_duplicates[user_id]
            return None
        del self._pending_duplicates[user_id]
        return entry["data"]

    def has_pending_duplicate(self, user_id: str) -> bool:
        """检查用户是否有待决策的重复记录"""
        if user_id not in self._pending_duplicates:
            return False
        entry = self._pending_duplicates[user_id]
        if time.time() - entry["stored_at"] > self._timeout:
            del self._pending_duplicates[user_id]
            return False
        return True
