from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.duckduckgo_search import ddgs_search

class OrgExpertAgent(BaseAgent):
    """组织架构专家Agent - 负责调研组织架构与团队动态"""

    def __init__(self):
        super().__init__(name="org_expert")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行组织架构调研"""
        sources = []
        content_parts = []

        # 1. DuckDuckGo Dorking搜索LinkedIn公司主页
        linkedin_company = ddgs_search(
            f"site:linkedin.com/company/ {card.company_name}",
            max_results=3
        )
        if linkedin_company:
            content_parts.append("**LinkedIn公司主页**：")
            for r in linkedin_company[:2]:
                content_parts.append(f"- {r.get('href', '')}")
            sources.extend([r.get('href', '') for r in linkedin_company if r.get('href')])

        # 2. 搜索高管信息
        linkedin_executives = ddgs_search(
            f"site:linkedin.com/in/ {card.company_name} ('CEO' OR 'Purchasing' OR 'Sourcing' OR 'Procurement')",
            max_results=5
        )
        if linkedin_executives:
            content_parts.append("**关键决策人**：")
            for r in linkedin_executives[:3]:
                content_parts.append(f"- {r.get('title', '')}")
            sources.extend([r.get('href', '') for r in linkedin_executives if r.get('href')])

        # 3. 搜索招聘信息
        hiring = ddgs_search(
            f"site:indeed.com {card.company_name}",
            max_results=3
        )
        if hiring:
            content_parts.append("**招聘动态**：")
            for r in hiring[:2]:
                content_parts.append(f"- {r.get('title', '')}")
            sources.extend([r.get('href', '') for r in hiring if r.get('href')])

        # 4. 组装内容
        content = "\n".join(content_parts) if content_parts else "未找到相关组织架构信息"

        return self._create_result(
            content=content,
            sources=sources[:5],
            confidence="medium"
        )
