import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from src.agents.supervisor import SupervisorAgent
from src.models import BusinessCard, AgentResult, ResearchReport


def test_supervisor_initialization():
    agent = SupervisorAgent()
    assert agent.name == "supervisor"


def test_supervisor_assemble_report():
    agent = SupervisorAgent()
    results = [
        AgentResult(agent_name="business_expert", content="Business info", sources=["https://example.com"]),
        AgentResult(agent_name="compliance_expert", content="Compliance info", sources=["https://example.com"]),
        AgentResult(agent_name="org_expert", content="Org info", sources=["https://example.com"]),
        AgentResult(agent_name="pr_expert", content="PR info", sources=["https://example.com"]),
    ]

    report = agent._assemble_report("Test Corp", results)
    assert isinstance(report, ResearchReport)
    assert report.company_name == "Test Corp"
    assert "Business info" in report.basic_info
    assert "Compliance info" in report.financial_health
    assert "Org info" in report.org_structure
    assert "PR info" in report.news_reputation


def test_supervisor_assemble_report_deduplicates_sources():
    agent = SupervisorAgent()
    results = [
        AgentResult(agent_name="business_expert", content="Business", sources=["https://a.com"]),
        AgentResult(agent_name="compliance_expert", content="Compliance", sources=["https://a.com", "https://b.com"]),
        AgentResult(agent_name="org_expert", content="Org", sources=["https://c.com"]),
        AgentResult(agent_name="pr_expert", content="PR", sources=[]),
    ]

    report = agent._assemble_report("Test Corp", results)
    assert len(report.sources) == 3  # "https://a.com" should appear only once


def test_supervisor_research_integration():
    """集成测试: supervisor.research 能串联调用所有专家Agent"""
    agent = SupervisorAgent()

    # Mock所有专家Agent的research方法
    mock_results = [
        AgentResult(agent_name="business_expert", content="Business [来源: https://a.com]", sources=["https://a.com"]),
        AgentResult(agent_name="compliance_expert", content="Compliance [来源: https://b.com]", sources=["https://b.com"]),
        AgentResult(agent_name="org_expert", content="Org [来源: https://c.com]", sources=["https://c.com"]),
        AgentResult(agent_name="pr_expert", content="PR [来源: https://d.com]", sources=["https://d.com"]),
    ]

    with patch.object(agent.business_expert, 'research', return_value=mock_results[0]), \
         patch.object(agent.compliance_expert, 'research', return_value=mock_results[1]), \
         patch.object(agent.org_expert, 'research', return_value=mock_results[2]), \
         patch.object(agent.pr_expert, 'research', return_value=mock_results[3]), \
         patch.object(agent.fact_checker, 'verify', side_effect=lambda r: r) as mock_verify:

        card = BusinessCard(company_name="Test Corp")
        report = agent.research(card)

        assert isinstance(report, ResearchReport)
        assert report.company_name == "Test Corp"
        assert mock_verify.called
