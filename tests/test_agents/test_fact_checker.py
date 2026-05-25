import pytest
from src.agents.fact_checker import FactCheckerAgent
from src.models import AgentResult


def test_fact_checker_initialization():
    agent = FactCheckerAgent()
    assert agent.name == "fact_checker"


def test_fact_checker_verify():
    agent = FactCheckerAgent()
    results = [
        AgentResult(agent_name="business_expert", content="Test content [来源: https://example.com]", sources=["https://example.com"]),
        AgentResult(agent_name="compliance_expert", content="No source content", sources=[])
    ]

    verified = agent.verify(results)
    assert len(verified) == 2
    assert verified[0].content == "Test content [来源: https://example.com]"
    assert "⚠️" in verified[1].content


def test_fact_checker_verify_marks_low_confidence():
    """无来源内容应被标记为低置信度"""
    agent = FactCheckerAgent()
    results = [
        AgentResult(agent_name="business_expert", content="Unverified claim", sources=[])
    ]

    verified = agent.verify(results)
    assert verified[0].confidence == "low"
    assert "待验证" in verified[0].content


def test_fact_checker_has_source_links():
    """测试来源链接检测"""
    agent = FactCheckerAgent()
    assert agent._has_source_links("Content [来源: https://example.com]") is True
    assert agent._has_source_links("No source here") is False
    assert agent._has_source_links("Partial [来源: invalid]") is False
