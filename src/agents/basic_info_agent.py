"""基础信息调研 Agent - 公司官网验证、域名历史、办公地址核验、社媒基础画像"""
import logging
from typing import Optional

from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.whois_lookup import lookup_whois
from ..tools.wayback_machine import get_wayback_snapshots, get_snapshot_content
from ..tools.google_maps import get_address_info
from ..tools.deep_search import SourceIndex, search_company_deep
from ..tools.web_crawler import fetch_web_content

logger = logging.getLogger(__name__)


class BasicInfoAgent(BaseAgent):
    """基础信息调研 Agent"""

    def __init__(self):
        super().__init__("basic_info")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行基础信息调研 - 深度搜索 + 详细爬取"""
        company_name = card.company_name or card.company_name_en
        source_index = SourceIndex()
        findings = []

        # 如果公司名为空，尝试从其他字段搜索发现
        if not company_name:
            discovery_result = self._discover_from_other_fields(card, source_index)
            if discovery_result:
                findings.append(discovery_result)
                # 从搜索结果中提取公司名
                extracted_name = self._extract_company_name_from_text(discovery_result)
                if extracted_name:
                    card.company_name = extracted_name
                    company_name = extracted_name
                    logger.info(f"从搜索结果中发现公司名: {company_name}")

        if not company_name:
            return self._create_result("公司名称缺失，无法调研", confidence="low")

        domain = self._extract_domain(card.website) if card.website else ""

        # 1. WHOIS 查询 - 域名注册信息
        if domain:
            whois_result = self._query_whois(domain, source_index)
            if whois_result:
                findings.append(whois_result)

        # 2. Wayback Machine - 网站历史快照
        if domain:
            wayback_result = self._query_wayback(domain, source_index)
            if wayback_result:
                findings.append(wayback_result)

        # 3. Google Maps 地址验证
        if card.address:
            maps_result = self._query_google_maps(card.address, source_index)
            if maps_result:
                findings.append(maps_result)

        # 4. 深度搜索 - 多轮搜索 + 网页爬取
        deep_result = self._deep_search_company(company_name, card.country, card.contact_name, source_index)
        if deep_result:
            findings.append(deep_result)

        # 5. LinkedIn 深度搜索
        linkedin_result = self._search_linkedin_deep(company_name, card.country, source_index)
        if linkedin_result:
            findings.append(linkedin_result)

        raw_content = "\n\n".join(findings) if findings else ""

        if not raw_content:
            return AgentResult(
                agent_name=self.name,
                content=f"未能找到 {company_name} 的基础信息",
                confidence="low",
                source_index=source_index,
            )

        # LLM 评估信息充足性 + 补充搜索 + 最终总结
        final_content, source_urls = self._evaluate_and_search(
            company_name=company_name,
            raw_findings=raw_content,
            source_index=source_index,
            agent_role="基础信息调研",
            search_categories=[
                "公司官网与域名信息",
                "公司简介与主营业务",
                "公司规模与员工数",
                "办公地址与联系方式",
                "社交媒体与品牌画像",
            ],
            country=card.country,
            agent_prefix="B",
        )

        confidence = "high" if len(findings) >= 3 else "medium" if len(findings) >= 2 else "low"

        return AgentResult(
            agent_name=self.name,
            content=final_content,
            sources=[s["url"] for s in source_index.get_all_sources()],
            confidence=confidence,
            source_content_map={s["url"]: s.get("content_preview", "") for s in source_index.get_all_sources()},
            source_index=source_index,
            source_urls=source_urls,
        )

    def _extract_domain(self, url: str) -> str:
        """从 URL 中提取域名"""
        domain = url.replace("https://", "").replace("http://", "").replace("www.", "")
        return domain.split("/")[0].split("?")[0]

    def _query_whois(self, domain: str, source_index: SourceIndex) -> Optional[str]:
        """WHOIS 域名查询"""
        try:
            result = lookup_whois(domain)
            if "error" in result:
                return None

            age = result.get("age_years", 0)
            registrar = result.get("registrar", "未知")
            creation = result.get("creation_date", "未知")

            summary = f"**域名 WHOIS 信息 ({domain})**\n"
            summary += f"- 注册时间：{creation}\n"
            summary += f"- 域名年龄：{age} 年\n"
            summary += f"- 注册商：{registrar}\n"

            if result.get("name_servers"):
                summary += f"- DNS 服务器：{', '.join(result['name_servers'][:3])}\n"

            # 添加到来源索引
            source_index.add_source(
                url=f"WHOIS:{domain}",
                title=f"WHOIS {domain}",
                content=str(result),
                category="whois"
            )

            return summary
        except Exception as e:
            logger.warning(f"WHOIS query failed for {domain}: {e}")
            return None

    def _query_wayback(self, domain: str, source_index: SourceIndex) -> Optional[str]:
        """Wayback Machine 历史快照查询"""
        try:
            snapshots = get_wayback_snapshots(domain, years=3, limit=5)
            if not snapshots:
                return None

            summary = f"**网站历史快照 ({domain})**\n"
            summary += f"- 收录快照数：{len(snapshots)}\n"

            for snap in snapshots[:3]:
                year = snap.get("year", "")
                timestamp = snap.get("timestamp", "")
                summary += f"- {year} 年快照：{timestamp}\n"

                # 添加到来源索引
                snap_url = snap.get("url", "")
                if snap_url:
                    source_index.add_source(
                        url=snap_url,
                        title=f"Wayback {domain} {year}",
                        content=f"历史快照 {timestamp}",
                        category="wayback"
                    )

            if snapshots:
                latest = snapshots[-1]
                content = get_snapshot_content(latest.get("url", ""), max_chars=500)
                if content:
                    summary += f"- 最新快照内容摘要：{content[:200]}...\n"

            return summary
        except Exception as e:
            logger.warning(f"Wayback query failed for {domain}: {e}")
            return None

    def _query_google_maps(self, address: str, source_index: SourceIndex) -> Optional[str]:
        """Google Maps 地址验证"""
        try:
            result = get_address_info(address)
            if result.get("error"):
                return None

            summary = "**办公地址验证 (Google Maps)**\n"
            summary += f"- 标准化地址：{result.get('address', '')}\n"
            summary += f"- 城市：{result.get('city', '')}\n"
            summary += f"- 州/省：{result.get('state', '')}\n"
            summary += f"- 国家：{result.get('country', '')}\n"

            if result.get("lat") and result.get("lng"):
                summary += f"- 坐标：({result['lat']}, {result['lng']})\n"

            # 添加到来源索引
            source_index.add_source(
                url=f"Google Maps: {address}",
                title="Google Maps 地址验证",
                content=str(result),
                category="google_maps"
            )

            return summary
        except Exception as e:
            logger.warning(f"Google Maps query failed: {e}")
            return None

    def _deep_search_company(
        self,
        company_name: str,
        country: str,
        contact_name: str,
        source_index: SourceIndex,
    ) -> Optional[str]:
        """深度搜索公司信息 - 多轮搜索 + 网页爬取"""
        try:
            content, deep_index = search_company_deep(
                company_name=company_name,
                country=country,
                contact_name=contact_name,
            )

            # 合并来源索引
            for src in deep_index.get_all_sources():
                source_index.add_source(
                    url=src["url"],
                    title=src.get("title", ""),
                    content=src.get("content", ""),
                    category=src.get("category", "search")
                )

            if content:
                return f"**公司深度调研**\n\n{content}"

            return None
        except Exception as e:
            logger.warning(f"Deep search failed for {company_name}: {e}")
            return None

    def _search_linkedin_deep(
        self,
        company_name: str,
        country: str,
        source_index: SourceIndex,
    ) -> Optional[str]:
        """LinkedIn 深度搜索"""
        try:
            from ..tools.linkedin_scraper import search_company as linkedin_search_company

            result = linkedin_search_company(company_name, location=country, limit=3)
            if not result.get("companies"):
                return None

            summary = "**LinkedIn 公司信息**\n"
            for comp in result["companies"][:3]:
                name = comp.get("name", "")
                url = comp.get("url", "")
                desc = comp.get("description", "")

                summary += f"- {name}: {url}\n"
                if desc:
                    summary += f"  描述：{desc[:100]}...\n"

                # 爬取 LinkedIn 页面内容
                if url:
                    web_content = fetch_web_content(url, max_length=1500)
                    if web_content:
                        source_index.add_source(
                            url=url,
                            title=f"LinkedIn {name}",
                            content=web_content,
                            category="linkedin"
                        )

            return summary
        except Exception as e:
            logger.warning(f"LinkedIn search failed for {company_name}: {e}")
            return None

    def _discover_from_other_fields(self, card: BusinessCard, source_index: SourceIndex) -> str:
        """从其他字段（email, website, contact_name）搜索公司信息"""
        from ..tools.deep_search import deep_search

        queries = []
        # 用 email 域名搜索
        if card.email and "@" in card.email:
            domain = card.email.split("@")[-1]
            if domain not in ("gmail.com", "qq.com", "163.com", "126.com", "yahoo.com", "hotmail.com"):
                queries.append(f'"{domain}" company')

        # 用 contact_name + position 搜索
        if card.contact_name:
            queries.append(f'"{card.contact_name}" company')
            if card.position:
                queries.append(f'"{card.contact_name}" "{card.position}" company')

        # 用 phone 搜索
        if card.phone:
            queries.append(f'"{card.phone}" company')

        if not queries:
            return ""

        try:
            content, idx = deep_search(
                queries[:3],
                max_results_per_query=3,
                crawl_top_n=2,
                max_content_length=5000,
            )
            # 合并来源索引
            if hasattr(idx, 'sources') and hasattr(idx.sources, 'items'):
                for source_id, source_info in idx.sources.items():
                    source_index.add_source(source_id, source_info)
            return content
        except Exception as e:
            logger.warning(f"从其他字段搜索失败: {e}")
            return ""

    def _extract_company_name_from_text(self, text: str) -> str:
        """从搜索结果文本中提取公司名"""
        import re
        from openai import OpenAI
        from ..config import config

        if not text:
            return ""

        try:
            client = OpenAI(
                api_key=config.mimo.api_key,
                base_url=config.mimo.api_base
            )

            prompt = f"""从以下搜索结果中提取公司名称。

搜索结果：
{text[:2000]}

请只返回公司名称（保留原始语言，不要翻译成中文），不要其他内容。如果无法确定，返回空字符串。"""

            response = client.chat.completions.create(
                model=config.mimo.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.1,
            )

            result = response.choices[0].message.content.strip()
            # 清理引号等
            result = result.strip('"').strip("'").strip()
            if len(result) > 2 and len(result) < 100:
                return result
            return ""

        except Exception as e:
            logger.warning(f"提取公司名失败: {e}")
            return ""
