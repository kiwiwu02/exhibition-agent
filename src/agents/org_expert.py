from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.duckduckgo_search import ddgs_search
from ..tools.web_crawler import crawl_and_extract

class OrgExpertAgent(BaseAgent):
    """组织架构专家Agent - 负责调研组织架构与团队动态"""

    def __init__(self):
        super().__init__(name="org_expert")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行组织架构调研"""
        sources = []
        content_parts = []
        source_content_map = {}

        # 1. 搜索联系人信息 - 用名片中的联系人名字搜索
        if card.contact_name:
            contact_search = ddgs_search(
                f"{card.contact_name} {card.company_name} LinkedIn",
                max_results=3
            )
            if contact_search:
                urls = [r.get('href', '') for r in contact_search if r.get('href')]
                sources.extend(urls[:2])
                crawled, crawled_map = crawl_and_extract(urls[:2], max_length_per_page=50000)
                if crawled:
                    content_parts.append(f"**联系人 {card.contact_name} 信息**：")
                    content_parts.append(crawled[:1500])
                    source_content_map.update(crawled_map)
                else:
                    content_parts.append(f"**联系人 {card.contact_name} 信息**：")
                    for r in contact_search[:2]:
                        content_parts.append(f"- {r.get('title', '')}: {r.get('body', '')[:100]}")

        # 2. 搜索公司高管和组织架构
        org_searches = [
            f"{card.company_name} executives CEO management team",
            f"{card.company_name} {card.city} leadership",
        ]
        if card.position:
            org_searches.append(f"{card.position} {card.company_name}")

        org_results = []
        for query in org_searches[:2]:
            results = ddgs_search(query, max_results=3)
            org_results.extend(results)

        if org_results:
            urls = [r.get('href', '') for r in org_results if r.get('href')]
            unique_urls = list(dict.fromkeys(urls))
            sources.extend(unique_urls[:3])
            crawled, crawled_map = crawl_and_extract(unique_urls[:2], max_length_per_page=50000)
            if crawled:
                content_parts.append("**公司组织信息（详细）**：")
                content_parts.append(crawled[:2000])
                source_content_map.update(crawled_map)
            else:
                content_parts.append("**公司组织信息**：")
                for r in org_results[:3]:
                    content_parts.append(f"- {r.get('title', '')}: {r.get('body', '')[:100]}")

        # 3. 搜索招聘信息
        hiring_queries = [
            f"{card.company_name} hiring jobs careers",
            f"{card.company_name} {card.city} job openings",
        ]
        hiring_results = []
        for query in hiring_queries[:2]:
            results = ddgs_search(query, max_results=3)
            hiring_results.extend(results)

        if hiring_results:
            urls = [r.get('href', '') for r in hiring_results if r.get('href')]
            unique_urls = list(dict.fromkeys(urls))
            sources.extend(unique_urls[:2])
            crawled, crawled_map = crawl_and_extract(unique_urls[:2], max_length_per_page=50000)
            if crawled:
                content_parts.append("**招聘动态（详细）**：")
                content_parts.append(crawled[:1500])
                source_content_map.update(crawled_map)
            else:
                content_parts.append("**招聘动态**：")
                for r in hiring_results[:2]:
                    content_parts.append(f"- {r.get('title', '')}: {r.get('body', '')[:100]}")

        # 4. 组装内容
        content = "\n".join(content_parts) if content_parts else "未找到相关组织架构信息"

        return self._create_result(
            content=content,
            sources=sources[:5],
            confidence="medium",
            source_content_map=source_content_map
        )
