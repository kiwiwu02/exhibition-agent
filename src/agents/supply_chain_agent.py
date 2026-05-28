"""供应链与口碑调研 Agent - 上下游分析、行业口碑与负面信息筛查"""
import logging
from typing import Optional

from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.trustpilot_scraper import search_company_reviews, get_company_rating
from ..tools.deep_search import SourceIndex, deep_search
from ..tools.web_crawler import fetch_web_content

logger = logging.getLogger(__name__)


class SupplyChainAgent(BaseAgent):
    """供应链与口碑调研 Agent"""

    def __init__(self):
        super().__init__("supply_chain")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行供应链与口碑调研"""
        company_name = card.company_name or card.company_name_en
        if not company_name:
            return self._create_result("公司名称缺失，无法调研", confidence="low")

        source_index = SourceIndex()
        findings = []

        # 1. Trustpilot 评价查询
        trustpilot_result = self._query_trustpilot(company_name, card.website, source_index)
        if trustpilot_result:
            findings.append(trustpilot_result)

        # 2. 供应链信息深度搜索
        supply_result = self._search_supply_chain_deep(company_name, card.country, source_index)
        if supply_result:
            findings.append(supply_result)

        # 3. 负面信息深度筛查
        negative_result = self._search_negative_deep(company_name, source_index)
        if negative_result:
            findings.append(negative_result)

        # 4. 口碑评价深度搜索
        reputation_result = self._search_reputation_deep(company_name, source_index)
        if reputation_result:
            findings.append(reputation_result)

        raw_content = "\n\n".join(findings) if findings else ""

        if not raw_content:
            return AgentResult(
                agent_name=self.name,
                content=f"未能找到 {company_name} 的供应链与口碑信息",
                confidence="low",
                source_index=source_index,
            )

        # LLM 评估信息充足性 + 补充搜索 + 最终总结
        final_content, source_urls = self._evaluate_and_search(
            company_name=company_name,
            raw_findings=raw_content,
            source_index=source_index,
            agent_role="供应链与口碑调研",
            search_categories=[
                "供应商与合作伙伴",
                "客户评价与口碑",
                "负面信息",
                "供应链稳定性",
                "行业地位",
            ],
            country=card.country,
            agent_prefix="S",
        )

        confidence = "high" if trustpilot_result and len(findings) >= 3 else "medium" if len(findings) >= 2 else "low"

        return AgentResult(
            agent_name=self.name,
            content=final_content,
            sources=[s["url"] for s in source_index.get_all_sources()],
            confidence=confidence,
            source_content_map={s["url"]: s.get("content_preview", "") for s in source_index.get_all_sources()},
            source_index=source_index,
            source_urls=source_urls,
        )

    def _query_trustpilot(self, company_name: str, website: str, source_index: SourceIndex) -> Optional[str]:
        """Trustpilot 评价查询"""
        try:
            domain = ""
            if website:
                domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

            # 搜索 Trustpilot 页面
            reviews_result = search_company_reviews(company_name, domain=domain, limit=3)

            if not reviews_result.get("reviews"):
                return None

            summary = "**Trustpilot 评价**\n"

            for review in reviews_result["reviews"][:3]:
                slug = review.get("company_slug", "")
                summary += f"- 公司：{slug}\n"
                if review.get("rating"):
                    summary += f"  评分：{review['rating']}/5\n"
                if review.get("url"):
                    summary += f"  链接：{review['url']}\n"

                    # 爬取 Trustpilot 页面详情
                    web_content = fetch_web_content(review['url'], max_length=1500)
                    if web_content:
                        source_index.add_source(
                            url=review['url'],
                            title=f"Trustpilot {slug}",
                            content=web_content,
                            category="trustpilot"
                        )

                # 尝试获取详细评分
                if slug:
                    detail = get_company_rating(slug)
                    if not detail.get("error"):
                        if detail.get("review_count"):
                            summary += f"  评价数量：{detail['review_count']}\n"
                        if detail.get("trust_score"):
                            summary += f"  TrustScore：{detail['trust_score']}\n"
                        break

            # 添加 Trustpilot 搜索来源
            source_index.add_source(
                url=f"Trustpilot: {company_name}",
                title=f"Trustpilot 搜索: {company_name}",
                content=str(reviews_result),
                category="trustpilot"
            )

            return summary
        except Exception as e:
            logger.warning(f"Trustpilot query failed for {company_name}: {e}")
            return None

    def _search_supply_chain_deep(self, company_name: str, country: str, source_index: SourceIndex) -> Optional[str]:
        """供应链信息深度搜索"""
        try:
            queries = [
                f'"{company_name}" supplier vendor partner',
                f'"{company_name}" customer client buyer',
                f'"{company_name}" supply chain distribution',
            ]

            content, deep_index = deep_search(
                queries=queries,
                max_results_per_query=3,
                crawl_top_n=5,
                max_content_length=50000,
                category="supply_chain",
                company_name=company_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category="supply_chain"
                )

            if content:
                return f"**供应链信息**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Supply chain search failed for {company_name}: {e}")
            return None

    def _search_negative_deep(self, company_name: str, source_index: SourceIndex) -> Optional[str]:
        """负面信息深度筛查"""
        try:
            queries = [
                f'"{company_name}" scam fraud complaint',
                f'"{company_name}" review bad negative',
                f'"{company_name}" lawsuit bankruptcy',
            ]

            content, deep_index = deep_search(
                queries=queries,
                max_results_per_query=3,
                crawl_top_n=5,
                max_content_length=50000,
                category="negative_info",
                company_name=company_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category="negative_info"
                )

            if content:
                return f"**负面信息筛查**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Negative info search failed for {company_name}: {e}")
            return None

    def _search_reputation_deep(self, company_name: str, source_index: SourceIndex) -> Optional[str]:
        """口碑评价深度搜索"""
        try:
            queries = [
                f'"{company_name}" reviews reputation rating',
                f'"{company_name}" customer experience feedback',
            ]

            content, deep_index = deep_search(
                queries=queries,
                max_results_per_query=3,
                crawl_top_n=5,
                max_content_length=50000,
                category="reputation",
                company_name=company_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category="reputation"
                )

            if content:
                return f"**口碑评价**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Reputation search failed for {company_name}: {e}")
            return None
