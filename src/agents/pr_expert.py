from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.duckduckgo_search import ddgs_search
from ..tools.google_news_rss import fetch_google_news

class PRExpertAgent(BaseAgent):
    """新闻与声誉专家Agent - 负责调研动态、新闻与口碑"""

    def __init__(self):
        super().__init__(name="pr_expert")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行新闻与声誉调研"""
        sources = []
        content_parts = []

        # 1. Google News获取近期新闻
        news = fetch_google_news(card.company_name, max_results=5, months_back=6)
        if news:
            content_parts.append("**近期新闻**：")
            for n in news[:3]:
                content_parts.append(f"- {n.get('title', '')}")
            sources.extend([n.get('link', '') for n in news if n.get('link')])

        # 2. DuckDuckGo搜索行业口碑
        reputation = ddgs_search(
            f"{card.company_name} reviews reputation",
            max_results=3
        )
        if reputation:
            content_parts.append("**行业口碑**：")
            for r in reputation[:2]:
                content_parts.append(f"- {r.get('title', '')}")
            sources.extend([r.get('href', '') for r in reputation if r.get('href')])

        # 3. DuckDuckGo搜索合作案例
        cases = ddgs_search(
            f"{card.company_name} customer case study",
            max_results=3
        )
        if cases:
            content_parts.append("**合作案例**：")
            for c in cases[:2]:
                content_parts.append(f"- {c.get('title', '')}")
            sources.extend([c.get('href', '') for c in cases if c.get('href')])

        # 4. 组装内容
        content = "\n".join(content_parts) if content_parts else "未找到相关新闻与声誉信息"

        return self._create_result(
            content=content,
            sources=sources[:5],
            confidence="medium"
        )
