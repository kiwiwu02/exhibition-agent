"""SupervisorAgent 新版测试"""
import pytest
from unittest.mock import patch, MagicMock
from src.agents.supervisor import SupervisorAgent
from src.models import BusinessCard, AgentResult


@pytest.fixture
def agent():
    return SupervisorAgent()


@pytest.fixture
def sample_card():
    return BusinessCard(
        company_name="Example Corp",
        company_name_en="Example Corporation",
        contact_name="John Smith",
        address="123 Main St, New York, NY",
        country="USA",
    )


def test_agent_name(agent):
    assert agent.name == "supervisor"


def test_agents_initialized(agent):
    assert agent.basic_info_agent is not None
    assert len(agent.agents) == 5
    assert agent.cross_validation_agent is not None
    assert agent.report_writer is not None


def test_research_calls_all_groups(agent, sample_card):
    with patch.object(agent, '_run_parallel_research', return_value=[AgentResult(agent_name="test", content="test")]) as mock_parallel:
        with patch.object(agent, '_cross_validate', return_value=[]) as mock_cross:
            with patch.object(agent.report_writer, 'write_report', return_value=MagicMock()) as mock_write:
                result = agent.research(sample_card)

                mock_parallel.assert_called_once()
                mock_cross.assert_called_once()
                mock_write.assert_called_once()


def test_cross_validate(agent, sample_card):
    results = [
        AgentResult(agent_name="basic_info", content="Company info"),
        AgentResult(agent_name="business_legal", content="Legal info"),
    ]

    validations = agent._cross_validate(sample_card, results)
    assert isinstance(validations, list)
    assert len(validations) > 0


def test_extract_fields_for_validation(agent, sample_card):
    results = [AgentResult(agent_name="test", content="test")]

    fields = agent._extract_fields_for_validation(sample_card, results)
    assert "公司名称" in fields
    assert fields["公司名称"][0]["value"] == "Example Corp"
    assert "地址" in fields
    assert "联系人" in fields


def test_get_validation_report(agent):
    from src.agents.cross_validation_agent import FieldVerification

    validations = [
        FieldVerification(
            field_name="公司名称",
            sources=[{"source": "名片", "value": "Example"}],
            consistency=True,
            credibility_score=4,
            verification_status="已验证",
            recommended_value="Example",
        ),
    ]

    report = agent.get_validation_report(validations)
    assert "交叉验证结果" in report
    assert "公司名称" in report
