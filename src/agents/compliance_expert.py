from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.duckduckgo_search import ddgs_search
from ..tools.web_crawler import crawl_and_extract


class ComplianceExpertAgent(BaseAgent):
    """法律财务合规Agent - 负责调研规模与健康度"""

    def __init__(self):
        super().__init__(name="compliance_expert")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行合规调研"""
        sources = []
        content_parts = []
        source_content_map = {}

        # 1. 搜索工商信息 - 多维度
        registration_queries = [
            f"{card.company_name} {card.country} company registration",
            f"{card.company_name} {card.city} business license",
        ]
        if card.website:
            registration_queries.append(f"site:{card.website.split('//')[-1].split('/')[0]} about")

        registration_results = []
        for query in registration_queries[:2]:
            results = ddgs_search(query, max_results=3)
            registration_results.extend(results)

        if registration_results:
            urls = [r.get('href', '') for r in registration_results if r.get('href')]
            unique_urls = list(dict.fromkeys(urls))
            sources.extend(unique_urls[:3])
            crawled, crawled_map = crawl_and_extract(unique_urls[:2], max_length_per_page=50000)
            if crawled:
                content_parts.append("**工商注册信息（详细）**：")
                content_parts.append(crawled[:2000])
                source_content_map.update(crawled_map)
            else:
                content_parts.append("**工商注册信息**：")
                for r in registration_results[:3]:
                    content_parts.append(f"- {r.get('title', '')}: {r.get('body', '')[:100]}")

        # 2. 搜索财务信息 - 多维度
        financial_queries = [
            f"{card.company_name} financial report revenue",
            f"{card.company_name} annual report",
        ]
        if card.address:
            financial_queries.append(f"{card.company_name} {card.address.split(',')[-2].strip() if ',' in card.address else card.city}")

        financial_results = []
        for query in financial_queries[:2]:
            results = ddgs_search(query, max_results=3)
            financial_results.extend(results)

        if financial_results:
            urls = [r.get('href', '') for r in financial_results if r.get('href')]
            unique_urls = list(dict.fromkeys(urls))
            sources.extend(unique_urls[:3])
            crawled, crawled_map = crawl_and_extract(unique_urls[:2], max_length_per_page=50000)
            if crawled:
                content_parts.append("**财务信息（详细）**：")
                content_parts.append(crawled[:2000])
                source_content_map.update(crawled_map)
            else:
                content_parts.append("**财务信息**：")
                for r in financial_results[:3]:
                    content_parts.append(f"- {r.get('title', '')}: {r.get('body', '')[:100]}")

        # 3. 搜索风险信息
        risk_results = ddgs_search(
            f"{card.company_name} lawsuit bankruptcy risk",
            max_results=3
        )
        if risk_results:
            urls = [r.get('href', '') for r in risk_results if r.get('href')]
            unique_urls = list(dict.fromkeys(urls))
            sources.extend(unique_urls[:2])
            crawled, crawled_map = crawl_and_extract(unique_urls[:2], max_length_per_page=50000)
            if crawled:
                content_parts.append("**风险信息（详细）**：")
                content_parts.append(crawled[:2000])
                source_content_map.update(crawled_map)
            else:
                content_parts.append("**风险信息**：")
                for r in risk_results[:2]:
                    content_parts.append(f"- {r.get('title', '')}: {r.get('body', '')[:100]}")

        # 4. 组装内容
        content = "\n".join(content_parts) if content_parts else "未找到相关合规信息"

        return self._create_result(
            content=content,
            sources=sources[:5],
            confidence="medium",
            source_content_map=source_content_map
        )
