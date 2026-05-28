"""SupervisorAgent 测试"""
import pytest
from unittest.mock import patch, MagicMock
from src.agents.supervisor import SupervisorAgent
from src.models import BusinessCard, AgentResult, ResearchReport


def test_supervisor_initialization():
    agent = SupervisorAgent()
    assert agent.name == "supervisor"
    assert agent.basic_info_agent is not None
    assert len(agent.agents) == 5
    assert agent.cross_validation_agent is not None
    assert agent.report_writer is not None


def test_supervisor_research_integration():
    """集成测试: supervisor.research 能串联调用所有专家Agent"""
    agent = SupervisorAgent()

    # Mock 所有 agent 的 research 方法
    mock_basic_result = AgentResult(
        agent_name="basic_info",
        content="基础信息",
        sources=["https://a.com"],
    )
    mock_agent_results = [
        AgentResult(agent_name="business_legal", content="工商法律", sources=["https://b.com"]),
        AgentResult(agent_name="financial_credit", content="财务信用", sources=["https://c.com"]),
        AgentResult(agent_name="org_structure", content="组织架构", sources=["https://d.com"]),
        AgentResult(agent_name="dynamic_news", content="动态新闻", sources=["https://e.com"]),
        AgentResult(agent_name="supply_chain", content="供应链", sources=["https://f.com"]),
    ]

    with patch.object(agent.basic_info_agent, 'research', return_value=mock_basic_result), \
         patch.object(agent, '_run_parallel_research', return_value=mock_agent_results), \
         patch.object(agent.cross_validation_agent, 'validate_field', return_value=MagicMock()), \
         patch.object(agent.report_writer, 'write_report', return_value=ResearchReport(
             company_name="Test Corp",
             basic_info="基础信息",
             business_track="工商法律",
             financial_health="财务信用",
             org_structure="组织架构",
             news_reputation="动态新闻",
             sources=["[1] https://a.com"],
             verified=True,
         )):

        card = BusinessCard(company_name="Test Corp")
        report = agent.research(card)

        assert isinstance(report, ResearchReport)
        assert report.company_name == "Test Corp"
        assert report.verified is True


def test_merge_source_index():
    """测试来源索引合并"""
    agent = SupervisorAgent()
    from src.tools.deep_search import SourceIndex

    target = SourceIndex()
    source = SourceIndex()
    source.add_source(url="https://example.com", title="Test", content="Content", category="test")

    agent._merge_source_index(target, source)

    assert len(target.get_all_sources()) == 1
    assert target.get_all_sources()[0]["url"] == "https://example.com"


def test_extract_fields_for_validation():
    """测试提取验证字段"""
    agent = SupervisorAgent()
    card = BusinessCard(
        company_name="Test Corp",
        company_name_en="Test Corporation",
        address="123 Main St",
        contact_name="John Smith",
    )
    results = []

    fields = agent._extract_fields_for_validation(card, results)

    assert "公司名称" in fields
    assert "地址" in fields
    assert "联系人" in fields
