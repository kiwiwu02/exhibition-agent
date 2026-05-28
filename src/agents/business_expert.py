from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.wikidata import query_wikidata_company
from ..tools.duckduckgo_search import ddgs_search
from ..tools.web_crawler import crawl_and_extract
from ..config import config

class BusinessExpertAgent(BaseAgent):
    """商业百科专家Agent - 负责调研基本面与赛道定位"""

    def __init__(self):
        super().__init__(name="business_expert")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行商业调研"""
        sources = []
        content_parts = []
        source_content_map = {}

        # 1. Wikidata查询
        wikidata = query_wikidata_company(card.company_name)
        if wikidata.get("found"):
            content_parts.append(f"**公司描述**：{wikidata.get('description', '无')}")
            if wikidata.get("industry"):
                content_parts.append(f"**所属行业**：{wikidata['industry']}")
            if wikidata.get("country"):
                content_parts.append(f"**所在国家**：{wikidata['country']}")
            wikidata_url = f"https://www.wikidata.org/wiki/{wikidata.get('wikidata_id', '')}"
            sources.append(wikidata_url)
            source_content_map[wikidata_url] = f"公司描述: {wikidata.get('description', '无')}, 行业: {wikidata.get('industry', '无')}"

        # 2. 多维度搜索
        search_queries = [
            f"{card.company_name} industry position competitors",
            f"{card.company_name} {card.country} company profile",
        ]
        if card.contact_name:
            search_queries.append(f"{card.contact_name} {card.company_name}")
        if card.website:
            search_queries.append(f"{card.website}")

        all_search_results = []
        for query in search_queries[:3]:
            results = ddgs_search(query, max_results=3)
            all_search_results.extend(results)

        if all_search_results:
            # 提取搜索结果URL
            urls = [r.get('href', '') for r in all_search_results if r.get('href')]
            sources.extend(urls[:5])

            # 爬取前3个网页获取详细内容
            unique_urls = list(dict.fromkeys(urls))  # 去重保序
            print(f"正在爬取 {min(3, len(unique_urls))} 个网页...")
            crawled_content, crawled_map = crawl_and_extract(unique_urls[:3], max_length_per_page=50000)
            if crawled_content:
                content_parts.append("**详细信息（来自网页）**：")
                content_parts.append(crawled_content[:3000])
                source_content_map.update(crawled_map)
            else:
                content_parts.append("**行业信息**：")
                for r in all_search_results[:5]:
                    content_parts.append(f"- {r.get('title', '')}: {r.get('body', '')[:100]}")

        # 3. 组装内容
        content = "\n".join(content_parts) if content_parts else "未找到相关商业信息"

        return self._create_result(
            content=content,
            sources=sources[:5],
            confidence="medium" if wikidata.get("found") else "low",
            source_content_map=source_content_map
        )
