"""动态新闻调研 Agent - 近期业务动态、扩张趋势监测"""
import logging
from typing import Optional

from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.deep_search import SourceIndex, deep_search
from ..tools.google_news_rss import fetch_google_news
from ..tools.web_crawler import fetch_web_content

logger = logging.getLogger(__name__)


class DynamicNewsAgent(BaseAgent):
    """动态新闻调研 Agent"""

    def __init__(self):
        super().__init__("dynamic_news")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行动态新闻调研"""
        company_name = card.company_name or card.company_name_en
        if not company_name:
            return self._create_result("公司名称缺失，无法调研", confidence="low")

        source_index = SourceIndex()
        findings = []

        # 1. Google News RSS 近期新闻
        news_result = self._query_google_news(company_name, source_index)
        if news_result:
            findings.append(news_result)

        # 2. 搜索引擎查找近期动态
        dynamic_result = self._search_dynamics_deep(company_name, card.country, source_index)
        if dynamic_result:
            findings.append(dynamic_result)

        # 3. 招聘动态
        hiring_result = self._search_hiring_deep(company_name, source_index)
        if hiring_result:
            findings.append(hiring_result)

        # 4. 行业相关动态
        industry_result = self._search_industry_deep(company_name, card.country, source_index)
        if industry_result:
            findings.append(industry_result)

        raw_content = "\n\n".join(findings) if findings else ""

        if not raw_content:
            return AgentResult(
                agent_name=self.name,
                content=f"未能找到 {company_name} 的近期动态信息",
                confidence="low",
                source_index=source_index,
            )

        # LLM 评估信息充足性 + 补充搜索 + 最终总结
        final_content, source_urls = self._evaluate_and_search(
            company_name=company_name,
            raw_findings=raw_content,
            source_index=source_index,
            agent_role="动态新闻调研",
            search_categories=[
                "近期新闻与动态",
                "融资与并购",
                "产品发布",
                "高管变动",
                "行业趋势",
            ],
            country=card.country,
            agent_prefix="N",
        )

        confidence = "high" if news_result and len(findings) >= 3 else "medium" if len(findings) >= 2 else "low"

        return AgentResult(
            agent_name=self.name,
            content=final_content,
            sources=[s["url"] for s in source_index.get_all_sources()],
            confidence=confidence,
            source_content_map={s["url"]: s.get("content_preview", "") for s in source_index.get_all_sources()},
            source_index=source_index,
            source_urls=source_urls,
        )

    def _query_google_news(self, company_name: str, source_index: SourceIndex) -> Optional[str]:
        """Google News RSS 新闻查询，并爬取新闻详情"""
        try:
            news = fetch_google_news(company_name, max_results=10)
            if not news:
                return None

            summary = f"**近期新闻 (Google News)**\n"
            summary += f"- 新闻数量：{len(news)} 条\n\n"

            for item in news[:8]:
                title = item.get("title", "")
                published = item.get("published", "")
                url = item.get("link", "")

                if url:
                    # 爬取新闻详情
                    web_content = fetch_web_content(url, max_length=1500)
                    if web_content:
                        summary += f"- **[{published}] {title}**\n"
                        summary += f"  内容：{web_content[:300]}...\n"

                        source_index.add_source(
                            url=url,
                            title=title,
                            content=web_content,
                            category="google_news"
                        )
                    else:
                        summary += f"- [{published}] {title}\n"
                        summary += f"  链接：{url}\n"

            # 添加 Google News 来源
            source_index.add_source(
                url=f"Google News: {company_name}",
                title=f"Google News 搜索: {company_name}",
                content=f"共找到 {len(news)} 条新闻",
                category="google_news"
            )

            return summary
        except Exception as e:
            logger.warning(f"Google News query failed for {company_name}: {e}")
            return None

    def _search_dynamics_deep(self, company_name: str, country: str, source_index: SourceIndex) -> Optional[str]:
        """搜索业务动态 - 深度搜索 + 详细爬取"""
        try:
            queries = [
                f'"{company_name}" announcement news latest',
                f'"{company_name}" expansion growth investment',
                f'"{company_name}" partnership collaboration',
            ]

            content, deep_index = deep_search(
                queries=queries,
                max_results_per_query=3,
                crawl_top_n=5,
                max_content_length=50000,
                category="business_dynamics",
                company_name=company_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category="business_dynamics"
                )

            if content:
                return f"**业务动态**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Dynamics search failed for {company_name}: {e}")
            return None

    def _search_hiring_deep(self, company_name: str, source_index: SourceIndex) -> Optional[str]:
        """招聘动态 - 深度搜索 + 详细爬取"""
        try:
            queries = [
                f'"{company_name}" hiring recruitment new positions',
                f'"{company_name}" jobs careers openings',
            ]

            content, deep_index = deep_search(
                queries=queries,
                max_results_per_query=3,
                crawl_top_n=3,
                max_content_length=50000,
                category="hiring_news",
                company_name=company_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category="hiring_news"
                )

            if content:
                return f"**招聘动态**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Hiring news search failed for {company_name}: {e}")
            return None

    def _search_industry_deep(self, company_name: str, country: str, source_index: SourceIndex) -> Optional[str]:
        """行业相关动态 - 深度搜索 + 详细爬取"""
        try:
            queries = [
                f'"{company_name}" industry trend market',
                f'"{company_name}" sector outlook forecast',
            ]

            content, deep_index = deep_search(
                queries=queries,
                max_results_per_query=3,
                crawl_top_n=3,
                max_content_length=50000,
                category="industry_news",
                company_name=company_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category="industry_news"
                )

            if content:
                return f"**行业动态**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Industry news search failed for {company_name}: {e}")
            return None
