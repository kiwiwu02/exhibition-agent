from typing import List
from .base import BaseAgent
from .business_expert import BusinessExpertAgent
from .compliance_expert import ComplianceExpertAgent
from .org_expert import OrgExpertAgent
from .pr_expert import PRExpertAgent
from .fact_checker import FactCheckerAgent
from ..models import BusinessCard, AgentResult, ResearchReport


class SupervisorAgent(BaseAgent):
    """主管Agent - 统筹任务拆解与报表组装"""

    def __init__(self):
        super().__init__(name="supervisor")
        self.business_expert = BusinessExpertAgent()
        self.compliance_expert = ComplianceExpertAgent()
        self.org_expert = OrgExpertAgent()
        self.pr_expert = PRExpertAgent()
        self.fact_checker = FactCheckerAgent()

    def research(self, card: BusinessCard) -> ResearchReport:
        """执行完整调研流程"""
        # 1. 并行派发任务给专家Agent
        results = self._run_parallel_research(card)

        # 2. 事实风控审计
        verified_results = self.fact_checker.verify(results)

        # 3. 组装报告
        report = self._assemble_report(card.company_name, verified_results)

        return report

    def _run_parallel_research(self, card: BusinessCard) -> List[AgentResult]:
        """并行执行所有专家Agent的调研"""
        # 使用同步方式依次执行（简化实现）
        results = []
        results.append(self.business_expert.research(card))
        results.append(self.compliance_expert.research(card))
        results.append(self.org_expert.research(card))
        results.append(self.pr_expert.research(card))
        return results

    def _assemble_report(self, company_name: str, results: List[AgentResult]) -> ResearchReport:
        """组装调研报告"""
        # 根据agent_name分类结果
        content_map = {}
        all_sources = []

        for result in results:
            content_map[result.agent_name] = result.content
            all_sources.extend(result.sources)

        return ResearchReport(
            company_name=company_name,
            basic_info=content_map.get("business_expert", ""),
            business_track=content_map.get("business_expert", ""),
            financial_health=content_map.get("compliance_expert", ""),
            org_structure=content_map.get("org_expert", ""),
            news_reputation=content_map.get("pr_expert", ""),
            sources=list(set(all_sources)),  # 去重
            verified=True
        )
