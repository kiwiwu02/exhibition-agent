"""工商法律调研 Agent 测试"""
import pytest
from unittest.mock import patch, MagicMock
from src.agents.business_legal_agent import BusinessLegalAgent
from src.models import BusinessCard


@pytest.fixture
def agent():
    return BusinessLegalAgent()


@pytest.fixture
def sample_card():
    return BusinessCard(
        company_name="Example Corp",
        country="USA",
    )


def test_agent_name(agent):
    assert agent.name == "business_legal"


def test_research_empty_card(agent):
    card = BusinessCard()
    result = agent.research(card)
    assert "公司名称缺失" in result.content


@patch("src.agents.business_legal_agent.oc_search")
def test_research_with_opencorporates(mock_oc, agent, sample_card):
    mock_oc.return_value = {
        "companies": [
            {
                "name": "Example Corp",
                "status": "Active",
                "type": "Corporation",
                "jurisdiction": "Delaware",
                "incorporation_date": "2010-03-20",
                "company_number": "1234567",
                "registered_address": "123 Main St, Wilmington, DE",
                "opencorporates_url": "https://opencorporates.com/companies/us_de/1234567",
                "jurisdiction_code": "us_de",
            }
        ]
    }

    with patch("src.agents.business_legal_agent.get_company_details", return_value={"agent_name": "John Agent"}):
        with patch("src.agents.business_legal_agent.deep_search", return_value=("", MagicMock())):
            result = agent.research(sample_card)

    assert "OpenCorporates" in result.content
    assert "Example Corp" in result.content
    assert "Active" in result.content


@patch("src.agents.business_legal_agent.deep_search")
def test_research_legal_risk(mock_search, agent, sample_card):
    mock_search.return_value = ("法律风险信息", MagicMock())

    with patch("src.agents.business_legal_agent.oc_search", return_value={"companies": []}):
        result = agent.research(sample_card)

    assert "法律风险" in result.content


def test_map_country_to_jurisdiction(agent):
    assert agent._map_country_to_jurisdiction("USA") == "us_de"
    assert agent._map_country_to_jurisdiction("United Kingdom") == "gb"
    assert agent._map_country_to_jurisdiction("Singapore") == "sg"
    assert agent._map_country_to_jurisdiction("China") == "cn"
    assert agent._map_country_to_jurisdiction("Unknown") is None
