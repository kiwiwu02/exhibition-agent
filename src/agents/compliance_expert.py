from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.duckduckgo_search import ddgs_search


class ComplianceExpertAgent(BaseAgent):
    """法律财务合规Agent - 负责调研规模与健康度"""

    def __init__(self):
        super().__init__(name="compliance_expert")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行合规调研"""
        sources = []
        content_parts = []

        # 1. 搜索工商信息
        registration_results = ddgs_search(
            f"{card.company_name} {card.country} company registration",
            max_results=3
        )
        if registration_results:
            content_parts.append("**工商注册信息**：")
            for r in registration_results[:2]:
                content_parts.append(f"- {r.get('title', '')}")
            sources.extend([r.get('href', '') for r in registration_results if r.get('href')])

        # 2. 搜索财务信息
        financial_results = ddgs_search(
            f"{card.company_name} financial report revenue",
            max_results=3
        )
        if financial_results:
            content_parts.append("**财务信息**：")
            for r in financial_results[:2]:
                content_parts.append(f"- {r.get('title', '')}")
            sources.extend([r.get('href', '') for r in financial_results if r.get('href')])

        # 3. 搜索风险信息
        risk_results = ddgs_search(
            f"{card.company_name} lawsuit bankruptcy risk",
            max_results=3
        )
        if risk_results:
            content_parts.append("**风险信息**：")
            for r in risk_results[:2]:
                content_parts.append(f"- {r.get('title', '')}")
            sources.extend([r.get('href', '') for r in risk_results if r.get('href')])

        # 4. 组装内容
        content = "\n".join(content_parts) if content_parts else "未找到相关合规信息"

        return self._create_result(
            content=content,
            sources=sources[:5],
            confidence="medium"
        )
