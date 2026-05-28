"""工商法律调研 Agent - 全球企业工商注册信息、法律风险筛查"""
import logging
from typing import Optional

from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.opencorporates import search_company as oc_search, get_company_details
from ..tools.deep_search import SourceIndex, deep_search
from ..tools.web_crawler import fetch_web_content

logger = logging.getLogger(__name__)


class BusinessLegalAgent(BaseAgent):
    """工商法律调研 Agent"""

    def __init__(self):
        super().__init__("business_legal")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行工商法律调研 - 深度搜索 + 详细爬取"""
        company_name = card.company_name or card.company_name_en
        if not company_name:
            return self._create_result("公司名称缺失，无法调研", confidence="low")

        source_index = SourceIndex()
        findings = []

        # 1. OpenCorporates 查询
        oc_result = self._query_opencorporates(company_name, card.country, source_index)
        if oc_result:
            findings.append(oc_result)

        # 2. 法律风险深度搜索
        legal_result = self._search_legal_risk_deep(company_name, card.country, source_index)
        if legal_result:
            findings.append(legal_result)

        # 3. 工商信息深度搜索
        business_result = self._search_business_info_deep(company_name, card.country, source_index)
        if business_result:
            findings.append(business_result)

        raw_content = "\n\n".join(findings) if findings else ""

        if not raw_content:
            return AgentResult(
                agent_name=self.name,
                content=f"未能找到 {company_name} 的工商法律信息",
                confidence="low",
                source_index=source_index,
            )

        # LLM 评估信息充足性 + 补充搜索 + 最终总结
        final_content, source_urls = self._evaluate_and_search(
            company_name=company_name,
            raw_findings=raw_content,
            source_index=source_index,
            agent_role="工商法律调研",
            search_categories=[
                "公司注册信息",
                "法律诉讼与合规",
                "经营异常与处罚",
                "知识产权与商标",
                "行业许可与资质",
            ],
            country=card.country,
            agent_prefix="L",
        )

        confidence = "high" if oc_result else "medium" if len(findings) >= 2 else "low"

        return AgentResult(
            agent_name=self.name,
            content=final_content,
            sources=[s["url"] for s in source_index.get_all_sources()],
            confidence=confidence,
            source_content_map={s["url"]: s.get("content_preview", "") for s in source_index.get_all_sources()},
            source_index=source_index,
            source_urls=source_urls,
        )

    def _query_opencorporates(self, company_name: str, country: str, source_index: SourceIndex) -> Optional[str]:
        """OpenCorporates 工商注册查询"""
        try:
            jurisdiction = self._map_country_to_jurisdiction(country) if country else None
            result = oc_search(company_name, jurisdiction_code=jurisdiction, limit=5)

            if not result.get("companies"):
                return None

            summary = "**工商注册信息 (OpenCorporates)**\n"
            for comp in result["companies"][:3]:
                summary += f"\n**{comp.get('name', '')}**\n"
                summary += f"- 状态：{comp.get('status', '')}\n"
                summary += f"- 类型：{comp.get('type', '')}\n"
                summary += f"- 注册地：{comp.get('jurisdiction', '')}\n"
                if comp.get("incorporation_date"):
                    summary += f"- 成立日期：{comp['incorporation_date']}\n"
                if comp.get("company_number"):
                    summary += f"- 注册号：{comp['company_number']}\n"
                if comp.get("registered_address"):
                    summary += f"- 注册地址：{comp['registered_address']}\n"
                if comp.get("opencorporates_url"):
                    summary += f"- 详情：{comp['opencorporates_url']}\n"

                    # 爬取 OpenCorporates 详情页
                    web_content = fetch_web_content(comp['opencorporates_url'], max_length=2000)
                    if web_content:
                        source_index.add_source(
                            url=comp['opencorporates_url'],
                            title=f"OpenCorporates {comp.get('name', '')}",
                            content=web_content,
                            category="opencorporates"
                        )

                # 获取详细信息
                details = self._get_company_details(
                    comp.get("jurisdiction_code", ""),
                    comp.get("company_number", ""),
                    source_index
                )
                if details:
                    summary += details

            # 添加 OpenCorporates 搜索结果到来源索引
            source_index.add_source(
                url=f"OpenCorporates: {company_name}",
                title=f"OpenCorporates 搜索: {company_name}",
                content=str(result),
                category="opencorporates"
            )

            return summary
        except Exception as e:
            logger.warning(f"OpenCorporates query failed for {company_name}: {e}")
            return None

    def _get_company_details(self, jurisdiction: str, company_number: str, source_index: SourceIndex) -> str:
        """获取公司详细信息"""
        if not jurisdiction or not company_number:
            return ""

        try:
            details = get_company_details(jurisdiction, company_number)
            if "error" in details:
                return ""

            additional = ""
            if details.get("agent_name"):
                additional += f"- 法定代理人：{details['agent_name']}\n"
            if details.get("annual_return_due_date"):
                additional += f"- 年报到期：{details['annual_return_due_date']}\n"
            if details.get("dissolution_date"):
                additional += f"- 注销日期：{details['dissolution_date']}\n"
            if details.get("last_update"):
                additional += f"- 最后更新：{details['last_update']}\n"

            return additional
        except Exception as e:
            logger.warning(f"OpenCorporates details query failed: {e}")
            return ""

    def _search_legal_risk_deep(self, company_name: str, country: str, source_index: SourceIndex) -> Optional[str]:
        """法律风险深度搜索"""
        try:
            queries = [
                f'"{company_name}" lawsuit bankruptcy risk',
                f'"{company_name}" legal complaint penalty',
                f'"{company_name}" court case litigation',
            ]

            content, deep_index = deep_search(
                queries=queries,
                max_results_per_query=3,
                crawl_top_n=5,
                max_content_length=50000,
                category="legal_risk",
                company_name=company_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category="legal_risk"
                )

            if content:
                return f"**法律风险信息**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Legal risk search failed for {company_name}: {e}")
            return None

    def _search_business_info_deep(self, company_name: str, country: str, source_index: SourceIndex) -> Optional[str]:
        """工商信息深度搜索"""
        try:
            queries = [
                f'"{company_name}" {country or ""} company registration business license',
                f'"{company_name}" business license permit',
            ]

            content, deep_index = deep_search(
                queries=queries,
                max_results_per_query=3,
                crawl_top_n=5,
                max_content_length=50000,
                category="business_info",
                company_name=company_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category="business_info"
                )

            if content:
                return f"**工商信息补充**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Business info search failed for {company_name}: {e}")
            return None

    def _map_country_to_jurisdiction(self, country: str) -> Optional[str]:
        """将国家名映射到 OpenCorporates 管辖区代码"""
        country_map = {
            "usa": "us_de",
            "us": "us_de",
            "united states": "us_de",
            "uk": "gb",
            "united kingdom": "gb",
            "china": "cn",
            "singapore": "sg",
            "hong kong": "hk",
            "australia": "au",
            "germany": "de",
            "japan": "jp",
            "canada": "ca",
        }
        return country_map.get(country.lower().strip())
