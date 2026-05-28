"""组织架构调研 Agent - 关键决策人挖掘、组织架构梳理"""
import logging
from typing import Optional

from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.linkedin_scraper import (
    search_company as linkedin_search_company,
    search_people,
    get_company_employees,
)
from ..tools.deep_search import SourceIndex, search_person_deep
from ..tools.web_crawler import fetch_web_content

logger = logging.getLogger(__name__)


class OrgStructureAgent(BaseAgent):
    """组织架构调研 Agent"""

    def __init__(self):
        super().__init__("org_structure")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行组织架构调研 - 深度搜索 + 详细爬取"""
        company_name = card.company_name or card.company_name_en
        if not company_name:
            return self._create_result("公司名称缺失，无法调研", confidence="low")

        source_index = SourceIndex()
        findings = []

        # 1. LinkedIn 员工规模
        employees_result = self._query_employees(company_name, source_index)
        if employees_result:
            findings.append(employees_result)

        # 2. 关键人员深度搜索
        key_people_result = self._search_key_people_deep(company_name, card.contact_name, source_index)
        if key_people_result:
            findings.append(key_people_result)

        # 3. 管理层信息深度搜索
        mgmt_result = self._search_management_deep(company_name, source_index)
        if mgmt_result:
            findings.append(mgmt_result)

        # 4. 招聘信息深度搜索
        hiring_result = self._search_hiring_deep(company_name, source_index)
        if hiring_result:
            findings.append(hiring_result)

        raw_content = "\n\n".join(findings) if findings else ""

        if not raw_content:
            return AgentResult(
                agent_name=self.name,
                content=f"未能找到 {company_name} 的组织架构信息",
                confidence="low",
                source_index=source_index,
            )

        # LLM 评估信息充足性 + 补充搜索 + 最终总结
        final_content, source_urls = self._evaluate_and_search(
            company_name=company_name,
            raw_findings=raw_content,
            source_index=source_index,
            agent_role="组织架构调研",
            search_categories=[
                "管理层与高管",
                "组织架构",
                "员工规模与招聘",
                "部门设置",
                "企业文化",
            ],
            country=card.country,
            agent_prefix="O",
        )

        confidence = "high" if employees_result and key_people_result else "medium" if len(findings) >= 2 else "low"

        return AgentResult(
            agent_name=self.name,
            content=final_content,
            sources=[s["url"] for s in source_index.get_all_sources()],
            confidence=confidence,
            source_content_map={s["url"]: s.get("content_preview", "") for s in source_index.get_all_sources()},
            source_index=source_index,
            source_urls=source_urls,
        )

    def _query_employees(self, company_name: str, source_index: SourceIndex) -> Optional[str]:
        """查询 LinkedIn 员工规模"""
        try:
            result = get_company_employees(company_name)
            if result.get("error") or not result.get("employee_count"):
                return None

            count = result["employee_count"]
            summary = f"**员工规模 (LinkedIn)**\n"
            summary += f"- 员工数量：{count} 人\n"
            if result.get("linkedin_url"):
                summary += f"- LinkedIn 页面：{result['linkedin_url']}\n"

                # 爬取 LinkedIn 页面
                web_content = fetch_web_content(result['linkedin_url'], max_length=1500)
                if web_content:
                    source_index.add_source(
                        url=result['linkedin_url'],
                        title=f"LinkedIn {company_name}",
                        content=web_content,
                        category="linkedin"
                    )

            # 添加到来源索引
            source_index.add_source(
                url=f"LinkedIn: {company_name}",
                title=f"LinkedIn 员工规模: {company_name}",
                content=str(result),
                category="linkedin"
            )

            return summary
        except Exception as e:
            logger.warning(f"Employee count query failed for {company_name}: {e}")
            return None

    def _search_key_people_deep(self, company_name: str, contact_name: str, source_index: SourceIndex) -> Optional[str]:
        """关键人员深度搜索"""
        try:
            # 如果有联系人姓名，深度搜索其信息
            if contact_name:
                content, deep_index = search_person_deep(
                    person_name=contact_name,
                    company_name=company_name,
                )

                # 合并来源索引
                for src in deep_index.get_all_sources():
                    source_index.add_source(
                        url=src["url"],
                        title=src.get("title", ""),
                        content=src.get("content", ""),
                        category="person_research"
                    )

                if content:
                    return f"**关键人员信息 ({contact_name})**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Key people search failed for {company_name}: {e}")
            return None

    def _search_management_deep(self, company_name: str, source_index: SourceIndex) -> Optional[str]:
        """管理层信息深度搜索"""
        try:
            from ..tools.deep_search import deep_search

            queries = [
                f'"{company_name}" CEO management team executives',
                f'"{company_name}" leadership board directors',
            ]

            content, deep_index = deep_search(
                queries=queries,
                max_results_per_query=3,
                crawl_top_n=5,
                max_content_length=50000,
                category="management",
                company_name=company_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category="management"
                )

            if content:
                return f"**管理层信息**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Management search failed for {company_name}: {e}")
            return None

    def _search_hiring_deep(self, company_name: str, source_index: SourceIndex) -> Optional[str]:
        """招聘信息深度搜索"""
        try:
            from ..tools.deep_search import deep_search

            queries = [
                f'"{company_name}" hiring jobs careers open positions',
                f'"{company_name}" recruitment vacancy',
            ]

            content, deep_index = deep_search(
                queries=queries,
                max_results_per_query=3,
                crawl_top_n=3,
                max_content_length=50000,
                category="hiring",
                company_name=company_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category="hiring"
                )

            if content:
                return f"**招聘信息**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Hiring search failed for {company_name}: {e}")
            return None
