"""财务信用调研 Agent - 财务状况、采购能力、信用风险初判"""
import logging
from typing import Optional

from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.sec_edgar import search_company_filings, get_company_info
from ..tools.yfinance_tool import query_company_financials
from ..tools.deep_search import SourceIndex, deep_search

logger = logging.getLogger(__name__)


class FinancialCreditAgent(BaseAgent):
    """财务信用调研 Agent"""

    def __init__(self):
        super().__init__("financial_credit")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行财务信用调研 - 深度搜索 + 详细爬取"""
        company_name = card.company_name or card.company_name_en
        if not company_name:
            return self._create_result("公司名称缺失，无法调研", confidence="low")

        source_index = SourceIndex()
        findings = []

        # 1. SEC EDGAR 查询（美国上市公司）
        sec_result = self._query_sec_edgar(company_name, source_index)
        if sec_result:
            findings.append(sec_result)

        # 2. yfinance 查询（上市公司财务数据）
        yfinance_result = self._query_yfinance(company_name, source_index)
        if yfinance_result:
            findings.append(yfinance_result)

        # 3. 财务信息深度搜索
        finance_search = self._search_financial_info_deep(company_name, card.country, source_index)
        if finance_search:
            findings.append(finance_search)

        # 4. 进出口数据深度搜索
        trade_result = self._search_trade_data_deep(company_name, card.country, source_index)
        if trade_result:
            findings.append(trade_result)

        raw_content = "\n\n".join(findings) if findings else ""

        if not raw_content:
            return AgentResult(
                agent_name=self.name,
                content=f"未能找到 {company_name} 的财务信用信息",
                confidence="low",
                source_index=source_index,
            )

        # LLM 评估信息充足性 + 补充搜索 + 最终总结
        final_content, source_urls = self._evaluate_and_search(
            company_name=company_name,
            raw_findings=raw_content,
            source_index=source_index,
            agent_role="财务信用调研",
            search_categories=[
                "财务报表与营收",
                "信用评级",
                "融资与投资记录",
                "贸易数据",
                "行业财务对比",
            ],
            country=card.country,
            agent_prefix="F",
        )

        confidence = "high" if sec_result or yfinance_result else "medium" if len(findings) >= 2 else "low"

        return AgentResult(
            agent_name=self.name,
            content=final_content,
            sources=[s["url"] for s in source_index.get_all_sources()],
            confidence=confidence,
            source_content_map={s["url"]: s.get("content_preview", "") for s in source_index.get_all_sources()},
            source_index=source_index,
            source_urls=source_urls,
        )

    def _query_sec_edgar(self, company_name: str, source_index: SourceIndex) -> Optional[str]:
        """SEC EDGAR 财务报表查询"""
        try:
            filings_result = search_company_filings(company_name, limit=3)
            if not filings_result.get("filings"):
                return None

            summary = "**SEC EDGAR 财务文件**\n"
            for filing in filings_result["filings"][:3]:
                summary += f"- {filing.get('form_type', '')} ({filing.get('file_date', '')})\n"
                summary += f"  公司：{filing.get('company_name', '')}\n"

            # 添加到来源索引
            source_index.add_source(
                url=f"SEC EDGAR: {company_name}",
                title=f"SEC EDGAR 搜索: {company_name}",
                content=str(filings_result),
                category="sec_edgar"
            )

            return summary
        except Exception as e:
            logger.warning(f"SEC EDGAR query failed for {company_name}: {e}")
            return None

    def _query_yfinance(self, company_name: str, source_index: SourceIndex) -> Optional[str]:
        """yfinance 上市公司财务数据查询"""
        try:
            result = query_company_financials(company_name)
            if not result or result.get("error"):
                return None

            summary = "**上市公司财务数据 (yfinance)**\n"
            if result.get("market_cap"):
                summary += f"- 市值：{result['market_cap']}\n"
            if result.get("revenue"):
                summary += f"- 营收：{result['revenue']}\n"
            if result.get("net_income"):
                summary += f"- 净利润：{result['net_income']}\n"
            if result.get("profit_margin"):
                summary += f"- 利润率：{result['profit_margin']}\n"
            if result.get("pe_ratio"):
                summary += f"- 市盈率：{result['pe_ratio']}\n"
            if result.get("sector"):
                summary += f"- 行业：{result['sector']}\n"
            if result.get("industry"):
                summary += f"- 细分行业：{result['industry']}\n"
            if result.get("employees"):
                summary += f"- 员工数：{result['employees']}\n"

            # 添加到来源索引
            source_index.add_source(
                url=f"yfinance: {company_name}",
                title=f"yfinance 财务数据: {company_name}",
                content=str(result),
                category="yfinance"
            )

            return summary
        except Exception as e:
            logger.warning(f"yfinance query failed for {company_name}: {e}")
            return None

    def _search_financial_info_deep(self, company_name: str, country: str, source_index: SourceIndex) -> Optional[str]:
        """财务信息深度搜索"""
        try:
            queries = [
                f'"{company_name}" financial report revenue',
                f'"{company_name}" annual report',
                f'"{company_name}" financial statements',
            ]

            content, deep_index = deep_search(
                queries=queries,
                max_results_per_query=3,
                crawl_top_n=5,
                max_content_length=50000,
                category="financial_info",
                company_name=company_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category="financial_info"
                )

            if content:
                return f"**财务信息搜索结果**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Financial info search failed for {company_name}: {e}")
            return None

    def _search_trade_data_deep(self, company_name: str, country: str, source_index: SourceIndex) -> Optional[str]:
        """进出口数据深度搜索"""
        try:
            queries = [
                f'"{company_name}" {country or ""} import export trade data',
                f'"{company_name}" customs data shipment',
            ]

            content, deep_index = deep_search(
                queries=queries,
                max_results_per_query=3,
                crawl_top_n=3,
                max_content_length=50000,
                category="trade_data",
                company_name=company_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category="trade_data"
                )

            if content:
                return f"**进出口贸易数据**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Trade data search failed for {company_name}: {e}")
            return None
