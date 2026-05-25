from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.wikidata import query_wikidata_company
from ..tools.duckduckgo_search import ddgs_search
from ..config import config

class BusinessExpertAgent(BaseAgent):
    """商业百科专家Agent - 负责调研基本面与赛道定位"""

    def __init__(self):
        super().__init__(name="business_expert")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行商业调研"""
        sources = []
        content_parts = []

        # 1. Wikidata查询
        wikidata = query_wikidata_company(card.company_name)
        if wikidata.get("found"):
            content_parts.append(f"**公司描述**：{wikidata.get('description', '无')}")
            if wikidata.get("industry"):
                content_parts.append(f"**所属行业**：{wikidata['industry']}")
            if wikidata.get("country"):
                content_parts.append(f"**所在国家**：{wikidata['country']}")
            sources.append(f"https://www.wikidata.org/wiki/{wikidata.get('wikidata_id', '')}")

        # 2. DuckDuckGo搜索行业信息
        search_results = ddgs_search(f"{card.company_name} industry position competitors", max_results=5)
        if search_results:
            content_parts.append("**行业信息**：")
            for r in search_results[:3]:
                content_parts.append(f"- {r.get('title', '')}")
            sources.extend([r.get('href', '') for r in search_results if r.get('href')])

        # 3. 组装内容
        content = "\n".join(content_parts) if content_parts else "未找到相关商业信息"

        return self._create_result(
            content=content,
            sources=sources[:5],  # 限制来源数量
            confidence="medium" if wikidata.get("found") else "low"
        )
