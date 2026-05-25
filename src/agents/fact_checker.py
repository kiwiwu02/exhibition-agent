import re
from typing import List
from .base import BaseAgent
from ..models import AgentResult


class FactCheckerAgent(BaseAgent):
    """事实风控审计Agent - 确保信息准确、有依据"""

    def __init__(self):
        super().__init__(name="fact_checker")

    def verify(self, results: List[AgentResult]) -> List[AgentResult]:
        """验证所有Agent的结果"""
        verified = []

        for result in results:
            if self._has_source_links(result.content):
                if self._validate_sources(result.content):
                    verified.append(result)
                else:
                    verified.append(AgentResult(
                        agent_name=result.agent_name,
                        content=f"⚠️ {result.content} (来源待验证)",
                        sources=result.sources,
                        confidence="low"
                    ))
            else:
                verified.append(AgentResult(
                    agent_name=result.agent_name,
                    content=f"⚠️ {result.content} (待验证)",
                    sources=result.sources,
                    confidence="low"
                ))

        return verified

    def _has_source_links(self, content: str) -> bool:
        """检查内容是否包含来源链接"""
        return bool(re.search(r'\[来源:\s*https?://', content))

    def _validate_sources(self, content: str) -> bool:
        """验证来源链接是否有效（仅做格式校验，不发网络请求）"""
        urls = re.findall(r'\[来源:\s*(https?://[^\]]+)\]', content)
        for url in urls[:3]:
            if not self._is_valid_url(url):
                return False
        return True

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """基本URL格式校验"""
        return bool(re.match(r'^https?://[^\s]+$', url))

    def research(self, card):
        """BaseAgent抽象方法的实现（本Agent不使用research方法）"""
        raise NotImplementedError("FactCheckerAgent不执行调研，仅用于验证结果")
