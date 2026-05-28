"""报告撰写 Agent - 按需求文档维度撰写，严格引用"""
import logging
import re
from typing import List, Dict, Any, Optional

from openai import OpenAI
from .base import BaseAgent
from ..models import BusinessCard, AgentResult, ResearchReport
from ..tools.deep_search import SourceIndex
from ..config import config

logger = logging.getLogger(__name__)

# 需求文档要求的 CRM 自动补充字段
CRM_SUPPLEMENT_FIELDS = [
    "country",          # 国家/地区
    "city",             # 城市
    "region",           # 区域
    "address",          # 公司地址
    "website",          # 官网链接
]


class ReportWriterAgent(BaseAgent):
    """调研报告撰写 Agent - 按需求文档维度，确保引用准确"""

    def __init__(self):
        super().__init__(name="report_writer")

    def _llm_summarize(self, prompt: str, max_tokens: int = 2000) -> str:
        """调用 LLM 总结内容，失败时返回空字符串"""
        try:
            client = OpenAI(api_key=config.mimo.api_key, base_url=config.mimo.api_base)
            response = client.chat.completions.create(
                model=config.mimo.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.1,
            )
            result = response.choices[0].message.content
            if result:
                return result.strip()
            return ""
        except Exception as e:
            logger.warning(f"LLM 总结失败: {e}")
            return ""

    def research(self, card: BusinessCard) -> AgentResult:
        return self._create_result(content="", sources=[])

    def write_report(
        self,
        card: BusinessCard,
        expert_results: List[AgentResult],
        source_index: SourceIndex = None,
        crm_supplements: Dict[str, str] = None,
        validations: List = None,
    ) -> ResearchReport:
        """将各专家的调研结果整合成完整报告

        报告维度（参考需求文档）：
        1. 公司概览与基本面
        2. 规模与健康度
        3. 组织架构
        4. 动态与新闻
        5. 合作案例与行业口碑
        6. 信息可信度评估
        7. 销售视角摘要
        8. CRM字段补充建议
        9. 参考来源
        """
        categorized = self._categorize_results(expert_results)

        # 收集带前缀的引用映射
        prefixed_sources = self._collect_prefixed_sources(expert_results)

        # 清理各 Agent 内容：移除末尾来源列表，保留正文+引用
        cleaned_categorized = {}
        for agent_name, content in categorized.items():
            cleaned_categorized[agent_name] = self._strip_reference_list(content)

        # 生成各章节（空章节自动跳过）
        raw_sections = [
            self._section_company_overview(card, cleaned_categorized, prefixed_sources),
            self._section_health_scale(cleaned_categorized, prefixed_sources),
            self._section_org_structure(card, cleaned_categorized, prefixed_sources),
            self._section_news_dynamics(cleaned_categorized, prefixed_sources),
            self._section_reputation_cases(cleaned_categorized, prefixed_sources),
            self._section_confidence_assessment(cleaned_categorized),
            self._section_cross_validation(card, validations) if validations else "",
            self._section_sales_summary(card, cleaned_categorized, prefixed_sources),
            self._section_crm_supplement(card, cleaned_categorized, source_index),
        ]

        # 过滤空章节并重新编号
        sections = [f"# {card.company_name} 公司调研报告\n"]
        section_num = 1
        for sec in raw_sections:
            if sec:
                # 替换章节编号为动态编号
                sec = re.sub(r'^## \d+\.', f'## {section_num}.', sec, count=1)
                sections.append(sec)
                section_num += 1

        sections.append(self._section_references_by_prefix(prefixed_sources))

        report_content = "\n\n".join(sections)

        supply_chain_content = cleaned_categorized.get("supply_chain", "")
        sales_opportunity = self._extract_sales_opportunity(card, cleaned_categorized)

        # 收集所有来源 URL 用于 ResearchReport.sources
        all_source_urls = []
        for agent_mappings in prefixed_sources.values():
            for citation, url in agent_mappings.items():
                all_source_urls.append(f"{citation} {url}")

        return ResearchReport(
            company_name=card.company_name,
            basic_info=cleaned_categorized.get("basic_info", ""),
            business_track=cleaned_categorized.get("business_legal", ""),
            financial_health=cleaned_categorized.get("financial_credit", ""),
            org_structure=cleaned_categorized.get("org_structure", ""),
            news_reputation=cleaned_categorized.get("dynamic_news", ""),
            supply_chain=supply_chain_content,
            sales_opportunity=sales_opportunity,
            full_report_content=report_content,
            sources=all_source_urls[:30],
            verified=True,
            crm_supplements=crm_supplements or {},
        )

    def get_crm_supplements(self, card: BusinessCard, categorized: Dict[str, str]) -> Dict[str, str]:
        """从调研结果中提取可补充到 CRM 的字段

        Returns:
            {bitable_field_name: value} 需要更新的字段
        """
        updates = {}
        all_content = " ".join(categorized.values())

        # 从内容中提取缺失的字段信息
        if not card.country:
            country = self._extract_country(all_content, card.company_name)
            if country:
                updates["国家/地区"] = country

        if not card.city:
            city = self._extract_city(all_content, card.company_name)
            if city:
                updates["城市"] = city

        if not card.address:
            address = self._extract_address(all_content)
            if address:
                updates["公司地址"] = address

        if not card.website:
            website = self._extract_website(all_content)
            if website:
                updates["官网"] = website

        return updates

    def _extract_company_en_name(self, content: str) -> str:
        """从内容中提取公司英文名"""
        patterns = [
            r'(?:also known as|AKA|trading as|T/A)\s+([A-Z][A-Za-z\s&]+?)(?:\.|,|\n)',
            r'(?:English name|公司英文名|英文名称)[：:]\s*(.+?)(?:\n|$)',
            r'(?:officially (?:known|called) as)\s+([A-Z][A-Za-z\s&]+?)(?:\.|,|\n)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_country(self, content: str, company_name: str) -> str:
        """从内容中提取国家"""
        countries = ["USA", "United States", "UK", "United Kingdom", "Canada", "Australia",
                     "Germany", "France", "Japan", "China", "India", "Brazil", "Mexico",
                     "Singapore", "South Korea", "Netherlands", "Italy", "Spain"]
        for country in countries:
            if country.lower() in content.lower():
                return country
        return ""

    def _extract_city(self, content: str, company_name: str) -> str:
        """从内容中提取城市"""
        patterns = [
            r'(?:headquarters?|located in|based in|office in)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)',
            r'(?:总部|位于|设在)\s*[:：]?\s*(.+?)(?:[，,。\n])',
        ]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_address(self, content: str) -> str:
        """从内容中提取地址"""
        patterns = [
            r'(?:address|地址)[：:]\s*(.+?)(?:\n|$)',
            r'(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln)[^,]*(?:,\s*[A-Za-z\s]+)?(?:,\s*[A-Z]{2}\s+\d{5})?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_website(self, content: str) -> str:
        """从内容中提取官网"""
        patterns = [
            r'(?:official website|官网|website)[：:]\s*(https?://[^\s]+)',
            r'(https?://(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                url = match.group(1)
                if not url.startswith("http"):
                    url = "https://" + url
                return url
        return ""

    def _categorize_results(self, results: List[AgentResult]) -> Dict[str, str]:
        categorized = {}
        for result in results:
            agent_name = result.agent_name
            if agent_name in ("basic_info", "business_legal", "financial_credit",
                              "org_structure", "dynamic_news", "supply_chain"):
                categorized[agent_name] = result.content
        return categorized

    # ========== 带前缀引用的处理 ==========

    # Agent 名称 -> 引用前缀映射
    AGENT_PREFIX_MAP = {
        "basic_info": "B",
        "business_legal": "L",
        "financial_credit": "F",
        "org_structure": "O",
        "dynamic_news": "N",
        "supply_chain": "S",
    }

    # 前缀 -> Agent 中文名映射
    PREFIX_NAMES = {
        "B": "基础信息调研",
        "L": "工商法律调研",
        "F": "财务信用调研",
        "O": "组织架构调研",
        "N": "动态新闻调研",
        "S": "供应链与口碑调研",
    }

    def _extract_citation_mappings(self, content: str, agent_name: str) -> Dict[str, str]:
        """从 Agent 内容中提取带前缀的引用映射 [{prefix}N] -> URL

        Agent 内容末尾通常有格式如：
        [B1] https://example.com - Example Title
        [B2] WHOIS:example.com - WHOIS Example
        [F1] SEC EDGAR: Century School of Languages
        """
        prefix = self.AGENT_PREFIX_MAP.get(agent_name, "")
        if not prefix:
            return {}

        mappings = {}
        # 匹配 [B1] 后面的所有内容（到行尾或 " - " 分隔符前）
        pattern = re.compile(rf'\[{re.escape(prefix)}(\d+)\]\s+(.+?)(?:\s+-\s+.+)?$', re.MULTILINE)
        for match in pattern.finditer(content):
            num = match.group(1)
            source = match.group(2).strip().rstrip(" -")
            if source:
                mappings[f"[{prefix}{num}]"] = source

        return mappings

    def _strip_reference_list(self, content: str) -> str:
        """移除 Agent 内容末尾的来源列表（[B1] URL - title 部分）"""
        # 匹配从 "来源列表" 或 "[B1]"/"[L1]" 等开始到末尾的部分
        lines = content.split("\n")
        result_lines = []
        in_reference_section = False

        for line in lines:
            stripped = line.strip()
            # 检测来源列表标题
            if re.match(r'^来源列表[（(]', stripped) or stripped == "来源列表":
                in_reference_section = True
                continue
            # 检测带前缀引用行 [B1] URL - title
            if re.match(r'^\[[A-Z]\d+\]\s+', stripped):
                in_reference_section = True
                continue
            if in_reference_section:
                # 来源列表中的续行（URL 或空白行）
                if not stripped or stripped.startswith("http") or stripped.startswith("（无来源）"):
                    continue
                # 遇到非来源行，结束来源列表
                in_reference_section = False

            if not in_reference_section:
                result_lines.append(line)

        return "\n".join(result_lines).rstrip()

    def _remap_bare_citations(
        self,
        content: str,
        section_agent_names: List[str],
        prefixed_sources: Dict[str, Dict[str, str]],
    ) -> str:
        """回退修正：将 LLM 丢失前缀的 [N] 还原为 [XN] 格式"""
        bare_citations = re.findall(r'\[(\d+)\]', content)
        if not bare_citations:
            return content

        all_prefixed = {}
        for agent_name in section_agent_names:
            agent_citations = prefixed_sources.get(agent_name, {})
            all_prefixed.update(agent_citations)

        if not all_prefixed:
            return content

        sorted_citations = sorted(
            all_prefixed.keys(),
            key=lambda c: (
                re.match(r'([A-Z])', c).group(1) if re.match(r'([A-Z])', c) else '',
                int(re.search(r'(\d+)', c).group(1)) if re.search(r'(\d+)', c) else 0
            )
        )

        result = content
        for bare_num_str in sorted(set(bare_citations), key=int):
            bare_num = int(bare_num_str)
            bare_ref = f"[{bare_num_str}]"
            if 1 <= bare_num <= len(sorted_citations):
                prefixed_ref = sorted_citations[bare_num - 1]
                if prefixed_ref in all_prefixed:
                    result = result.replace(bare_ref, prefixed_ref, 1)

        return result

    def _validate_citations(
        self,
        content: str,
        prefixed_sources: Dict[str, Dict[str, str]],
    ) -> str:
        """校验并移除不存在于 prefixed_sources 中的伪造引用标记"""
        valid_citations = set()
        for agent_citations in prefixed_sources.values():
            valid_citations.update(agent_citations.keys())

        if not valid_citations:
            return content

        output_citations = re.findall(r'\[[A-Z]\d+\]', content)
        for cite in set(output_citations):
            if cite not in valid_citations:
                content = content.replace(cite, "")

        return content

    def _collect_prefixed_sources(self, results: List[AgentResult]) -> Dict[str, Dict[str, str]]:
        """收集所有 Agent 的带前缀引用映射

        Returns:
            {agent_name: {citation: url}} 例如 {"basic_info": {"[B1]": "https://..."}}
        """
        all_mappings = {}
        for result in results:
            if result.agent_name in self.AGENT_PREFIX_MAP:
                mappings = self._extract_citation_mappings(result.content, result.agent_name)
                if mappings:
                    all_mappings[result.agent_name] = mappings
        return all_mappings

    def _collect_sources(self, results: List[AgentResult]) -> List[Dict[str, Any]]:
        seen_urls = set()
        all_sources = []
        for result in results:
            if result.source_index:
                for src in result.source_index.get_all_sources():
                    url = src.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_sources.append(src)
            else:
                for url in result.sources:
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_sources.append({"url": url, "title": "", "content": ""})
        return all_sources

    def _build_source_mapping(self, source_index: SourceIndex, all_sources: List[Dict]) -> Dict[str, int]:
        mapping = {}
        if source_index:
            for src in source_index.get_all_sources():
                url = src.get("url", "")
                if url:
                    mapping[url] = src.get("index", 0)
        next_index = len(mapping) + 1
        for src in all_sources:
            url = src.get("url", "")
            if url and url not in mapping:
                mapping[url] = next_index
                next_index += 1
        return mapping

    def _map_citations(self, content: str, source_mapping: Dict[str, int]) -> str:
        """将内容中的 URL 替换为引用序号"""
        url_pattern = r'(https?://[^\s\)\]]+)'
        urls = re.findall(url_pattern, content)
        for url in urls:
            if url in source_mapping:
                content = content.replace(url, f"[{source_mapping[url]}]")
        return content

    # ========== 报告章节（按需求文档维度） ==========
    # 章节方法返回空字符串 "" 表示该章节无内容，不展示

    def _section_company_overview(self, card: BusinessCard, categorized: Dict, prefixed_sources: Dict) -> str:
        """1. 公司概览与基本面"""
        # 基本信息子章节
        info_items = []
        if card.company_name:
            info_items.append(f"- **公司名称**：{card.company_name}")
        if card.company_name_en:
            info_items.append(f"- **英文名称**：{card.company_name_en}")
        if card.website:
            info_items.append(f"- **官网**：{card.website}")
        if card.country:
            info_items.append(f"- **国家/地区**：{card.country}")
        if card.city:
            info_items.append(f"- **城市**：{card.city}")
        if card.address:
            info_items.append(f"- **地址**：{card.address}")
        if card.contact_name:
            info_items.append(f"- **联系人**：{card.contact_name}")
        if card.position:
            info_items.append(f"- **职位**：{card.position}")
        if card.email:
            info_items.append(f"- **邮箱**：{card.email}")
        if card.phone:
            info_items.append(f"- **电话**：{card.phone}")

        # 业务概况
        basic_content = categorized.get("basic_info", "")

        # 名片信息和调研内容都没有，则不展示此章节
        if not info_items and not basic_content:
            return ""

        section = "## 1. 公司概览与基本面\n\n"

        if info_items:
            section += "### 基本信息\n\n"
            section += "\n".join(info_items) + "\n\n"

        if basic_content:
            basic_cites = list(prefixed_sources.get("basic_info", {}).keys())
            basic_cites_str = "、".join(basic_cites[:5]) if basic_cites else "无"
            prompt = f"""你是一位专业的商业分析师。请根据以下调研数据，为 {card.company_name} 生成"业务概况"章节。

要求：
- 用 3-5 个要点总结公司的核心业务、行业定位、主要产品/服务
- 每个要点用 markdown 列表格式（- 开头），每个要点控制在 1-2 句话以内
- 保留关键数据（成立时间、员工规模、营收等），关键数据用 **加粗**
- 不要编造信息，只基于提供的数据
- **严格保留引用格式**：本章节可用的引用标记为：{basic_cites_str}。只使用调研数据中实际出现的引用标记，绝对不要发明或复制其他章节的引用标记
- 不要包含章节标题，直接输出要点内容
- 控制总字数在 300 字以内
- 如果调研数据中信息不足或没有与该公司直接相关的内容，直接输出"该维度暂无足够信息，建议后续补充调研。"（一句话即可），不要描述搜索过程、不要评论引用系统的可用性、不要说明数据缺失的原因

调研数据：
{basic_content[:8000]}"""
            summary = self._llm_summarize(prompt)
            if summary:
                summary = self._remap_bare_citations(summary, ["basic_info"], prefixed_sources)
                summary = self._validate_citations(summary, prefixed_sources)
                section += "### 业务概况\n\n"
                section += summary + "\n"
            else:
                section += "### 业务概况\n\n"
                section += basic_content + "\n"

        return section

    def _section_health_scale(self, categorized: Dict, prefixed_sources: Dict) -> str:
        """2. 规模与健康度"""
        biz_content = categorized.get("business_legal", "")
        fin_content = categorized.get("financial_credit", "")

        if not biz_content and not fin_content:
            return ""

        section = "## 2. 规模与健康度\n\n"

        combined = ""
        if biz_content:
            combined += f"【工商法律信息】\n{biz_content[:4000]}\n\n"
        if fin_content:
            combined += f"【财务信用信息】\n{fin_content[:4000]}"

        biz_cites = list(prefixed_sources.get("business_legal", {}).keys())
        fin_cites = list(prefixed_sources.get("financial_credit", {}).keys())
        health_cites_str = "、".join((biz_cites + fin_cites)[:5]) if (biz_cites or fin_cites) else "无"
        prompt = f"""你是一位专业的商业分析师。请根据以下调研数据，生成"规模与健康度"章节。

要求：
- 分为"工商与法律信息"和"财务与信用状况"两个子章节（用 ### 三级标题）
- 每个子章节用 3-4 个要点总结关键发现，每个要点控制在 1-2 句话以内
- 突出经营状态、法律风险、财务健康度
- 关键数据用 **加粗**
- 不要编造信息，只基于提供的数据
- **严格保留引用格式**：本章节可用的引用标记为：{health_cites_str}。只使用调研数据中实际出现的引用标记，绝对不要发明或复制其他章节的引用标记
- 不要包含章节标题，直接输出子章节内容
- 控制总字数在 400 字以内
- 如果调研数据中信息不足或没有与该公司直接相关的内容，直接输出"该维度暂无足够信息，建议后续补充调研。"（一句话即可），不要描述搜索过程、不要评论引用系统的可用性、不要说明数据缺失的原因

调研数据：
{combined}"""
        summary = self._llm_summarize(prompt, max_tokens=2500)
        if summary:
            summary = self._remap_bare_citations(summary, ["business_legal", "financial_credit"], prefixed_sources)
            summary = self._validate_citations(summary, prefixed_sources)
            section += summary + "\n"
        else:
            if biz_content:
                section += "### 工商与法律信息\n\n"
                section += biz_content + "\n\n"
            if fin_content:
                section += "### 财务与信用状况\n\n"
                section += fin_content + "\n"

        return section

    def _section_org_structure(self, card: BusinessCard, categorized: Dict, prefixed_sources: Dict) -> str:
        """3. 组织架构"""
        org_content = categorized.get("org_structure", "")

        if not org_content:
            return ""

        org_cites = list(prefixed_sources.get("org_structure", {}).keys())
        org_cites_str = "、".join(org_cites[:5]) if org_cites else "无"
        prompt = f"""你是一位专业的商业分析师。请根据以下调研数据，为 {card.company_name} 生成"组织架构"章节。

要求：
- 用 3-5 个要点总结公司的组织架构、管理层、关键人物
- 保留人名、职位等关键信息，用 **加粗** 标注关键人物姓名和职位
- 不要编造信息，只基于提供的数据
- **严格保留引用格式**：本章节可用的引用标记为：{org_cites_str}。只使用调研数据中实际出现的引用标记，绝对不要发明或复制其他章节的引用标记
- 不要包含章节标题，直接输出要点内容
- 控制总字数在 300 字以内
- 如果调研数据中信息不足或没有与该公司直接相关的内容，直接输出"该维度暂无足够信息，建议后续补充调研。"（一句话即可），不要描述搜索过程、不要评论引用系统的可用性、不要说明数据缺失的原因

调研数据：
{org_content[:6000]}"""
        summary = self._llm_summarize(prompt)
        if summary:
            summary = self._remap_bare_citations(summary, ["org_structure"], prefixed_sources)
            summary = self._validate_citations(summary, prefixed_sources)
            section = "## 3. 组织架构\n\n"
            section += summary + "\n"
            return section

        section = "## 3. 组织架构\n\n"
        section += org_content + "\n"
        return section

    def _section_news_dynamics(self, categorized: Dict, prefixed_sources: Dict) -> str:
        """4. 动态与新闻"""
        content = categorized.get("dynamic_news", "")

        if not content:
            return ""

        news_cites = list(prefixed_sources.get("dynamic_news", {}).keys())
        news_cites_str = "、".join(news_cites[:5]) if news_cites else "无"
        prompt = f"""你是一位专业的商业分析师。请根据以下调研数据，生成"动态与新闻"章节。

要求：
- 用 3-5 个要点总结公司近期的重要动态和新闻
- 突出融资、并购、产品发布、高管变动等重要事件
- 关键日期和事件用 **加粗** 标注
- 不要编造信息，只基于提供的数据
- **严格保留引用格式**：本章节可用的引用标记为：{news_cites_str}。只使用调研数据中实际出现的引用标记，绝对不要发明或复制其他章节的引用标记
- 不要包含章节标题，直接输出要点内容
- 控制总字数在 300 字以内
- 如果调研数据中信息不足或没有与该公司直接相关的内容，直接输出"该维度暂无足够信息，建议后续补充调研。"（一句话即可），不要描述搜索过程、不要评论引用系统的可用性、不要说明数据缺失的原因

调研数据：
{content[:6000]}"""
        summary = self._llm_summarize(prompt)
        if summary:
            summary = self._remap_bare_citations(summary, ["dynamic_news"], prefixed_sources)
            summary = self._validate_citations(summary, prefixed_sources)
            section = "## 4. 动态与新闻\n\n"
            section += summary + "\n"
            return section

        section = "## 4. 动态与新闻\n\n"
        section += content + "\n"
        return section

    def _section_reputation_cases(self, categorized: Dict, prefixed_sources: Dict) -> str:
        """5. 合作案例与行业口碑"""
        content = categorized.get("supply_chain", "")

        if not content:
            return ""

        supply_cites = list(prefixed_sources.get("supply_chain", {}).keys())
        supply_cites_str = "、".join(supply_cites[:5]) if supply_cites else "无"
        prompt = f"""你是一位专业的商业分析师。请根据以下调研数据，生成"合作案例与行业口碑"章节。

要求：
- 用 3-5 个要点总结公司的合作伙伴、客户案例、行业评价
- 突出正面口碑和负面评价
- 关键合作方和评价用 **加粗** 标注
- 不要编造信息，只基于提供的数据
- **严格保留引用格式**：本章节可用的引用标记为：{supply_cites_str}。只使用调研数据中实际出现的引用标记，绝对不要发明或复制其他章节的引用标记
- 不要包含章节标题，直接输出要点内容
- 控制总字数在 300 字以内
- 如果调研数据中信息不足或没有与该公司直接相关的内容，直接输出"该维度暂无足够信息，建议后续补充调研。"（一句话即可），不要描述搜索过程、不要评论引用系统的可用性、不要说明数据缺失的原因

调研数据：
{content[:6000]}"""
        summary = self._llm_summarize(prompt)
        if summary:
            summary = self._remap_bare_citations(summary, ["supply_chain"], prefixed_sources)
            summary = self._validate_citations(summary, prefixed_sources)
            section = "## 5. 合作案例与行业口碑\n\n"
            section += summary + "\n"
            return section

        section = "## 5. 合作案例与行业口碑\n\n"
        section += content + "\n"
        return section

    def _section_confidence_assessment(self, categorized: Dict) -> str:
        """6. 信息可信度评估 - 仅展示有内容的维度"""
        dims = [
            ("基本信息", "basic_info", "★★★★☆ 高", "官网、WHOIS、Google Maps"),
            ("工商法律", "business_legal", "★★★★☆ 高", "OpenCorporates、工商信息"),
            ("财务信用", "financial_credit", "★★★☆☆ 中", "SEC EDGAR、yfinance"),
            ("组织架构", "org_structure", "★★★☆☆ 中", "LinkedIn、招聘信息"),
            ("动态新闻", "dynamic_news", "★★★☆☆ 中", "Google News、行业资讯"),
            ("供应链口碑", "supply_chain", "★★☆☆☆ 低", "Trustpilot、行业评价"),
        ]

        items = []
        for label, key, rating, source in dims:
            if categorized.get(key, ""):
                items.append(f"- **{label}**：{rating} — 来源：{source}")

        if not items:
            return ""

        section = "## 6. 信息可信度评估\n\n"
        section += "\n".join(items) + "\n"
        return section

    def _section_cross_validation(self, card: BusinessCard, validations: List) -> str:
        """7. 交叉验证 - 名片信息与调研数据对比"""
        from ..agents.cross_validation_agent import FieldVerification

        if not validations:
            return ""

        items = []
        discrepancies = []

        for v in validations:
            if not isinstance(v, FieldVerification):
                continue

            if v.consistency:
                # 一致
                items.append(f"- **{v.field_name}**：✅ 一致 — {v.recommended_value}")
            else:
                # 不一致，标记为差异
                discrepancies.append(v)
                source_values = []
                for sv in v.sources:
                    src = sv.get("source", "")
                    val = sv.get("value", "")
                    if val:
                        source_values.append(f"{src}: {val}")
                items.append(f"- **{v.field_name}**：⚠️ 不一致 — {' vs '.join(source_values)}")

        if not items:
            return ""

        section = "## 7. 交叉验证（名片 vs 调研数据）\n\n"

        if discrepancies:
            section += f"⚠️ 发现 {len(discrepancies)} 处信息不一致，建议核实：\n\n"

        section += "\n".join(items) + "\n"
        return section

    def _section_sales_summary(self, card: BusinessCard, categorized: Dict, prefixed_sources: Dict) -> str:
        """7. 销售视角摘要 - LLM 生成综合分析"""
        all_content = " ".join(categorized.values())
        if not all_content.strip():
            return ""

        all_cites = []
        for agent_key in ["basic_info", "business_legal", "financial_credit",
                          "org_structure", "dynamic_news", "supply_chain"]:
            all_cites.extend(list(prefixed_sources.get(agent_key, {}).keys()))
        all_cites_str = "、".join(all_cites[:8]) if all_cites else "无"
        prompt = f"""你是一位专业的商业分析师和销售顾问。请根据以下关于 {card.company_name} 的调研数据，生成"销售视角摘要"章节。

要求：
- 分为三个子章节（用 ### 三级标题）：
  1. **经营风险提示**：列出 2-3 个主要风险点
  2. **关键决策人**：列出已识别的关键决策人（如有）
  3. **合作建议**：给出 2-3 条具体的合作建议
- 每个要点控制在 1-2 句话以内
- 风险点和建议要具体，不要泛泛而谈
- 关键信息用 **加粗** 标注
- 不要编造信息，只基于提供的数据
- 如果某个子章节没有相关信息，可以跳过不展示
- **严格保留引用格式**：本章节可用的引用标记为：{all_cites_str}。只使用调研数据中实际出现的引用标记，绝对不要发明或复制其他章节的引用标记
- 控制总字数在 400 字以内
- 如果调研数据中信息不足或没有与该公司直接相关的内容，直接输出"该维度暂无足够信息，建议后续补充调研。"（一句话即可），不要描述搜索过程、不要评论引用系统的可用性、不要说明数据缺失的原因

调研数据：
{all_content[:10000]}"""
        summary = self._llm_summarize(prompt, max_tokens=2500)
        if summary:
            all_agent_names = ["basic_info", "business_legal", "financial_credit",
                               "org_structure", "dynamic_news", "supply_chain"]
            summary = self._remap_bare_citations(summary, all_agent_names, prefixed_sources)
            summary = self._validate_citations(summary, prefixed_sources)
            section = "## 7. 销售视角摘要\n\n"
            section += summary + "\n"
            return section

        # fallback: 使用规则提取
        risks = self._extract_risks(categorized)
        decision_makers = self._extract_decision_makers(categorized)
        suggestions = self._generate_suggestions(card, categorized)

        if not risks and not decision_makers and not suggestions:
            return ""

        section = "## 7. 销售视角摘要\n\n"

        if risks:
            section += "### 经营风险提示\n\n"
            for risk in risks:
                section += f"- {risk}\n"
            section += "\n"

        if decision_makers:
            section += "### 关键决策人\n\n"
            for dm in decision_makers:
                section += f"- {dm}\n"
            section += "\n"

        if suggestions:
            section += "### 合作建议\n\n"
            for sug in suggestions:
                section += f"- {sug}\n"

        return section

    def _extract_risks(self, categorized: Dict) -> List[str]:
        """从各维度提取经营风险"""
        risks = []
        all_content = " ".join(categorized.values())

        risk_keywords = [
            ("法律诉讼", "存在法律诉讼风险"),
            ("经营异常", "存在经营异常记录"),
            ("负面", "存在负面信息"),
            ("投诉", "存在客户投诉"),
            ("降级", "信用评级被下调"),
            ("亏损", "存在财务亏损"),
            ("裁员", "有裁员动态"),
        ]
        for keyword, risk_desc in risk_keywords:
            if keyword in all_content:
                risks.append(risk_desc)

        return risks[:5]  # 最多5条

    def _extract_decision_makers(self, categorized: Dict) -> List[str]:
        """从组织架构中提取关键决策人"""
        makers = []
        org_content = categorized.get("org_structure", "")

        # 简单提取包含 CEO/CTO/COO/CFO/Founder/总经理/总裁 的行
        for line in org_content.split("\n"):
            line = line.strip()
            if not line:
                continue
            title_keywords = ["CEO", "CTO", "COO", "CFO", "Founder", "President",
                              "总经理", "总裁", "董事", "VP", "Director"]
            for kw in title_keywords:
                if kw.lower() in line.lower():
                    # 清理 markdown 格式
                    clean = line.replace("**", "").replace("*", "").lstrip("- ").strip()
                    if clean and clean not in makers:
                        makers.append(clean)
                    break

        return makers[:5]  # 最多5条

    def _generate_suggestions(self, card: BusinessCard, categorized: Dict) -> List[str]:
        """综合分析生成合作建议"""
        suggestions = []

        if card.company_name:
            suggestions.append(f"建议对 {card.company_name} 进行深度业务交流")

        org_content = categorized.get("org_structure", "")
        if "CEO" in org_content or "Founder" in org_content or "总经理" in org_content:
            suggestions.append("已识别关键决策人，建议安排高层会面")

        news_content = categorized.get("dynamic_news", "")
        if "融资" in news_content or "投资" in news_content:
            suggestions.append("公司近期有融资动态，处于扩张期，合作窗口期较好")

        supply_content = categorized.get("supply_chain", "")
        if "负面" in supply_content or "投诉" in supply_content:
            suggestions.append("存在负面口碑信息，建议深入了解后再做决策")

        if not suggestions:
            suggestions.append("建议进一步了解公司业务细节后再做评估")

        return suggestions

    def _extract_sales_opportunity(self, card: BusinessCard, categorized: Dict) -> str:
        """提取销售机会评估内容"""
        parts = []

        risks = self._extract_risks(categorized)
        if risks:
            parts.append("**经营风险**：" + "；".join(risks))

        makers = self._extract_decision_makers(categorized)
        if makers:
            parts.append("**关键决策人**：" + "；".join(makers))

        suggestions = self._generate_suggestions(card, categorized)
        if suggestions:
            parts.append("**合作建议**：" + "；".join(suggestions))

        return "\n".join(parts) if parts else "待评估"

    def _section_crm_supplement(self, card: BusinessCard, categorized: Dict, source_index: SourceIndex) -> str:
        """8. CRM字段补充建议"""
        section = "## 8. CRM 字段补充建议\n\n"

        # 检查关键字段是否缺失
        missing_fields = []
        if not card.company_name:
            missing_fields.append("公司名称")
        if not card.country:
            missing_fields.append("国家/地区")
        if not card.city:
            missing_fields.append("城市")
        if not card.address:
            missing_fields.append("公司地址")
        if not card.website:
            missing_fields.append("官网")

        # 从调研结果中提取可补充的字段
        supplements = self.get_crm_supplements(card, categorized)

        if supplements:
            section += "根据调研结果，建议补充以下 CRM 字段：\n\n"
            for field, value in supplements.items():
                section += f"- **{field}**：{value}\n"
            # 仍然缺失的字段
            still_missing = [f for f in missing_fields if f not in supplements]
            if still_missing:
                section += "\n以下字段仍需手动补充：\n\n"
                for field in still_missing:
                    section += f"- **{field}**：待补充\n"
        elif missing_fields:
            section += "以下 CRM 字段信息缺失，建议手动补充：\n\n"
            for field in missing_fields:
                section += f"- **{field}**：待补充\n"
        else:
            section += "CRM 字段信息已完整，无需补充。\n"

        return section

    def _section_references_by_prefix(self, prefixed_sources: Dict[str, Dict[str, str]]) -> str:
        """参考来源 - 按 Agent 分组展示"""
        section = "## 参考来源\n\n"

        for agent_name in ["basic_info", "business_legal", "financial_credit",
                           "org_structure", "dynamic_news", "supply_chain"]:
            prefix = self.AGENT_PREFIX_MAP.get(agent_name, "")
            agent_label = self.PREFIX_NAMES.get(prefix, agent_name)
            citations = prefixed_sources.get(agent_name, {})

            if not citations:
                continue

            section += f"### {agent_label}\n\n"
            # 按引用编号排序
            sorted_citations = sorted(citations.items(), key=lambda x: (
                x[0],
                int(re.search(r'(\d+)', x[0]).group(1)) if re.search(r'(\d+)', x[0]) else 0
            ))
            for citation, url in sorted_citations:
                section += f"{citation} {url}\n"
            section += "\n"

        section += "---\n*本报告由 AI 自动生成，信息仅供参考，请以实际调查为准。*\n"
        return section

    def _validate_citations(self, content: str, source_index: SourceIndex) -> str:
        """验证引用准确性 - 支持带前缀引用（如 [B1], [L2]）"""
        if not source_index:
            return content
        # 匹配纯数字引用 [N] 和带前缀引用 [XN]
        citations = re.findall(r'\[([A-Z]?\d+)\]', content)
        for cite in set(citations):
            # 尝试解析为数字索引
            try:
                index = int(cite)
                source = source_index.get_source(index)
                if not source:
                    content = content.replace(f"[{cite}]", f"[{cite}] ⚠️来源待验证")
            except ValueError:
                # 带前缀引用（如 B1, L2），跳过验证
                pass
        return content
