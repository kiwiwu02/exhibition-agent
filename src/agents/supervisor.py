"""SupervisorAgent - 调度中心，任务拆分、分组并行、交叉验证"""
import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import BaseAgent
from .basic_info_agent import BasicInfoAgent
from .business_legal_agent import BusinessLegalAgent
from .financial_credit_agent import FinancialCreditAgent
from .org_structure_agent import OrgStructureAgent
from .dynamic_news_agent import DynamicNewsAgent
from .supply_chain_agent import SupplyChainAgent
from .cross_validation_agent import CrossValidationAgent, FieldVerification
from .report_writer import ReportWriterAgent
from .crm_supplement_agent import CRMSupplementAgent
from ..models import BusinessCard, AgentResult, ResearchReport
from ..tools.deep_search import SourceIndex

logger = logging.getLogger(__name__)

# Agent 中文名称映射
AGENT_DISPLAY_NAMES = {
    "basic_info": "基础信息调研",
    "business_legal": "工商法律调研",
    "financial_credit": "财务信用调研",
    "org_structure": "组织架构调研",
    "dynamic_news": "动态新闻调研",
    "supply_chain": "供应链与口碑调研",
}


class SupervisorAgent(BaseAgent):
    """主管Agent - 统筹任务拆解与分组并行执行"""

    def __init__(self):
        super().__init__(name="supervisor")

        # Group 1: 基础信息（先行执行）
        self.basic_info_agent = BasicInfoAgent()

        # Group 2: 专项调研（并行执行）
        self.agents = [
            BusinessLegalAgent(),
            FinancialCreditAgent(),
            OrgStructureAgent(),
            DynamicNewsAgent(),
            SupplyChainAgent(),
        ]

        # Group 3: 交叉验证（最后执行）
        self.cross_validation_agent = CrossValidationAgent()
        self.report_writer = ReportWriterAgent()
        self.crm_supplement_agent = CRMSupplementAgent()

    def research(self, card: BusinessCard, on_progress=None) -> ResearchReport:
        """执行完整调研流程

        执行顺序：
        1. Group 1: 基础信息调研（先行）
        2. Group 2: 5个专项 Agent 并行执行
        3. Group 3: 交叉验证 + 报告生成
        """
        def _notify(step, msg):
            if on_progress:
                on_progress(step, msg)

        # 防御性检查：如果公司名为空，尝试自动发现
        if not card.company_name and not card.company_name_en:
            from ..company_discovery import discover_company_name
            cn, cn_en, _ = discover_company_name(card)
            if cn:
                card.company_name = cn
                if cn_en:
                    card.company_name_en = cn_en

        # 合并所有来源索引
        merged_source_index = SourceIndex()

        # Group 1: 基础信息调研
        _notify("basic_info", "🔍 基础信息调研中...")
        basic_result = self.basic_info_agent.research(card)
        self._merge_source_index(merged_source_index, basic_result.source_index)
        _notify("basic_info_done", "✅ 基础信息调研完成")

        # Group 2: 并行执行专项调研
        agent_names = [AGENT_DISPLAY_NAMES.get(a.name, a.name) for a in self.agents]
        _notify("parallel_start", "🔬 专家 Agent调研并行中...\n" + "\n".join(f"{n} Agent" for n in agent_names))
        group2_results = self._run_parallel_research(card, on_progress)

        # 合并所有结果的来源索引
        for result in group2_results:
            self._merge_source_index(merged_source_index, result.source_index)

        # 合并所有结果
        all_results = [basic_result] + group2_results
        _notify("parallel_done", f"✅ 专家调研完成 ({len(group2_results)}/5)")

        # Group 3: 交叉验证
        _notify("validation", "🔎 交叉验证中...")
        validations = self._cross_validate(card, all_results)
        _notify("validation_done", "✅ 交叉验证完成")

        # Group 4: CRM 字段补充
        _notify("crm_supplement", "📊 补充 CRM 缺失字段...")
        crm_supplements = self.crm_supplement_agent.supplement(card, all_results)
        if crm_supplements:
            _notify("crm_done", f"✅ CRM 补充完成 ({len(crm_supplements)} 个字段)")
        else:
            _notify("crm_done", "✅ CRM 字段已完整")

        # 生成报告（传入合并后的来源索引、CRM 补充、交叉验证结果）
        _notify("report", "📝 生成调研报告...")
        report = self.report_writer.write_report(card, all_results, merged_source_index, crm_supplements, validations)
        _notify("report_done", "✅ 调研报告生成完成")

        return report

    def _run_parallel_research(self, card: BusinessCard, on_progress=None) -> List[AgentResult]:
        """并行执行 Group 2 的 5 个专项 Agent"""
        results = []

        def _notify_agent(step, msg):
            if on_progress:
                on_progress(step, msg)

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_agent = {
                executor.submit(agent.research, card): agent
                for agent in self.agents
            }

            for future in as_completed(future_to_agent):
                agent = future_to_agent[future]
                try:
                    result = future.result(timeout=120)
                    results.append(result)
                    display_name = AGENT_DISPLAY_NAMES.get(agent.name, agent.name)
                    _notify_agent("agent_done", f"✅ {display_name} Agent 完成 ({len(results)}/5)")
                    logger.info(f"Agent {agent.name} 完成调研")
                except Exception as e:
                    logger.warning(f"Agent {agent.name} 调研失败: {e}")
                    results.append(AgentResult(
                        agent_name=agent.name,
                        content=f"调研失败: {str(e)}",
                        confidence="low"
                    ))

        return results

    def _merge_source_index(self, target: SourceIndex, source: SourceIndex):
        """合并来源索引"""
        if source is None:
            return
        for src in source.get_all_sources():
            target.add_source(
                url=src["url"],
                title=src.get("title", ""),
                content=src.get("content", ""),
                category=src.get("category", "")
            )

    def _cross_validate(
        self,
        card: BusinessCard,
        results: List[AgentResult],
    ) -> List[FieldVerification]:
        """交叉验证多源信息"""
        import logging
        logger = logging.getLogger(__name__)

        # 提取需要验证的关键字段
        fields_to_validate = self._extract_fields_for_validation(card, results)
        logger.info(f"交叉验证: 提取了 {len(fields_to_validate)} 个字段: {list(fields_to_validate.keys())}")

        validations = []
        for field_name, field_values in fields_to_validate.items():
            verification = self.cross_validation_agent.validate_field(field_name, field_values)
            logger.info(f"验证 {field_name}: 一致性={verification.consistency}, 状态={verification.verification_status}, 来源数={len(field_values)}")
            if not verification.consistency and len(field_values) > 1:
                logger.warning(f"⚠️ {field_name} 信息不一致: {[fv.get('value', '') for fv in field_values]}")
            validations.append(verification)

        return validations

    def _extract_fields_for_validation(
        self,
        card: BusinessCard,
        results: List[AgentResult],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """从结果中提取需要交叉验证的字段，对比名片信息与调研数据"""
        fields = {}

        # 合并所有调研内容
        all_content = "\n\n".join(r.content for r in results if r.content)

        # 公司名称
        company_values = [{"source": "名片", "value": card.company_name}]
        if card.company_name_en:
            company_values.append({"source": "名片(英文)", "value": card.company_name_en})
        research_company = self._extract_field_from_content(all_content, "公司名称|company name|公司名")
        if research_company:
            company_values.append({"source": "调研数据", "value": research_company})
        fields["公司名称"] = company_values

        # 职位
        if card.position:
            position_values = [{"source": "名片", "value": card.position}]
            research_position = self._extract_field_from_content(all_content, "职位|position|title|职务")
            if research_position:
                position_values.append({"source": "调研数据", "value": research_position})
            fields["职位"] = position_values

        # 国家/地区
        if card.country:
            country_values = [{"source": "名片", "value": card.country}]
            research_country = self._extract_field_from_content(all_content, "国家|country|地区")
            if research_country:
                country_values.append({"source": "调研数据", "value": research_country})
            fields["国家/地区"] = country_values

        # 城市
        if card.city:
            city_values = [{"source": "名片", "value": card.city}]
            research_city = self._extract_field_from_content(all_content, "城市|city")
            if research_city:
                city_values.append({"source": "调研数据", "value": research_city})
            fields["城市"] = city_values

        # 地址
        if card.address:
            address_values = [{"source": "名片", "value": card.address}]
            research_address = self._extract_field_from_content(all_content, "地址|address|办公地点|headquarters")
            if research_address:
                address_values.append({"source": "调研数据", "value": research_address})
            fields["地址"] = address_values

        # 联系人
        if card.contact_name:
            fields["联系人"] = [{"source": "名片", "value": card.contact_name}]

        return fields

    def _extract_field_from_content(self, content: str, field_pattern: str) -> str:
        """从调研内容中提取特定字段的值"""
        import re
        if not content:
            return ""

        # 匹配 markdown 表格或列表中的字段
        patterns = [
            rf'(?:{field_pattern})\s*[：:]\s*(.+?)(?:\n|$)',
            rf'\|\s*(?:{field_pattern})\s*\|\s*(.+?)\s*\|',
            rf'[-*]\s*\*?\*?(?:{field_pattern})\*?\*?\s*[：:]\s*(.+?)(?:\n|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # 清理 markdown 格式
                value = re.sub(r'\*+', '', value)
                value = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', value)  # 提取链接文字
                if len(value) > 2 and len(value) < 200:
                    return value

        return ""

    def get_validation_report(self, validations: List[FieldVerification]) -> str:
        """生成交叉验证报告"""
        return self.cross_validation_agent.generate_verification_report(validations)
