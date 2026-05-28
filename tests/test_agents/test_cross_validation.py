"""交叉验证 Agent 测试"""
import pytest
from src.agents.cross_validation_agent import CrossValidationAgent, FieldVerification, SOURCE_WEIGHTS
from src.models import BusinessCard


@pytest.fixture
def agent():
    return CrossValidationAgent()


@pytest.fixture
def sample_card():
    return BusinessCard(
        company_name="Example Corp",
        contact_name="John Smith",
    )


def test_agent_name(agent):
    assert agent.name == "cross_validation"


def test_research_returns_framework(agent, sample_card):
    result = agent.research(sample_card)
    assert "交叉验证框架" in result.content
    assert "来源可信度权重" in result.content


def test_validate_field_consistent(agent):
    values = [
        {"source": "名片", "value": "Example Corp"},
        {"source": "官网", "value": "Example Corp"},
        {"source": "OpenCorporates", "value": "Example Corp"},
    ]

    verification = agent.validate_field("公司名称", values)
    assert verification.consistency is True
    assert verification.recommended_value == "Example Corp"
    assert verification.verification_status == "已验证"
    assert verification.credibility_score > 0


def test_validate_field_inconsistent(agent):
    values = [
        {"source": "名片", "value": "Example Corp"},
        {"source": "官网", "value": "Example Corporation"},
        {"source": "LinkedIn", "value": "Example Corp Inc"},
    ]

    verification = agent.validate_field("公司名称", values)
    assert verification.consistency is False
    assert verification.verification_status == "待人工确认"
    assert len(verification.sources) == 3


def test_validate_field_no_data(agent):
    verification = agent.validate_field("公司名称", [])
    assert verification.verification_status == "无数据"


def test_calculate_consistency_consistent(agent):
    sources = [
        {"source": "名片", "value": "123 Main St"},
        {"source": "Google Maps", "value": "123 Main St"},
    ]

    result = agent.calculate_consistency(sources)
    assert result["consistent"] is True
    assert result["score"] > 0


def test_calculate_consistency_inconsistent(agent):
    sources = [
        {"source": "名片", "value": "123 Main St"},
        {"source": "Google Maps", "value": "456 Oak Ave"},
    ]

    result = agent.calculate_consistency(sources)
    assert result["consistent"] is False
    assert len(result["unique_values"]) == 2


def test_generate_verification_report(agent):
    verifications = [
        FieldVerification(
            field_name="公司名称",
            sources=[{"source": "名片", "value": "Example"}, {"source": "官网", "value": "Example"}],
            consistency=True,
            credibility_score=4,
            verification_status="已验证",
            recommended_value="Example",
        ),
        FieldVerification(
            field_name="地址",
            sources=[{"source": "名片", "value": "123 Main"}, {"source": "Google Maps", "value": "456 Oak"}],
            consistency=False,
            credibility_score=0,
            verification_status="待人工确认",
            recommended_value="123 Main | 456 Oak",
        ),
    ]

    report = agent.generate_verification_report(verifications)
    assert "交叉验证结果" in report
    assert "公司名称" in report
    assert "地址" in report
    assert "1/2 已验证" in report
    assert "1/2 待人工确认" in report


def test_source_weights():
    assert SOURCE_WEIGHTS["名片"] == 1.0
    assert SOURCE_WEIGHTS["官网"] == 0.9
    assert SOURCE_WEIGHTS["搜索引擎"] == 0.5
    assert len(SOURCE_WEIGHTS) > 10
