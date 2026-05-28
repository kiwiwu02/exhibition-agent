"""基础信息调研 Agent 测试"""
import pytest
from unittest.mock import patch, MagicMock
from src.agents.basic_info_agent import BasicInfoAgent
from src.models import BusinessCard


@pytest.fixture
def agent():
    return BasicInfoAgent()


@pytest.fixture
def sample_card():
    return BusinessCard(
        company_name="Example Corp",
        website="https://example.com",
        address="123 Main St, New York, NY",
        country="USA",
    )


def test_agent_name(agent):
    assert agent.name == "basic_info"


def test_research_empty_card(agent):
    card = BusinessCard()
    result = agent.research(card)
    assert result.agent_name == "basic_info"
    assert "公司名称缺失" in result.content


@patch("src.agents.basic_info_agent.lookup_whois")
def test_research_with_whois(mock_whois, agent, sample_card):
    mock_whois.return_value = {
        "domain": "example.com",
        "registrar": "GoDaddy",
        "creation_date": "2010-03-20",
        "age_years": 16,
        "name_servers": ["ns1.example.com"],
    }

    with patch("src.agents.basic_info_agent.get_wayback_snapshots", return_value=[]):
        with patch("src.agents.basic_info_agent.get_address_info", return_value={"error": "no key"}):
            with patch("src.agents.basic_info_agent.search_company_deep", return_value=("", MagicMock())):
                with patch("src.agents.basic_info_agent.fetch_web_content", return_value=""):
                    result = agent.research(sample_card)

    assert "WHOIS" in result.content
    assert "GoDaddy" in result.content
    assert "16 年" in result.content


@patch("src.agents.basic_info_agent.get_address_info")
def test_research_with_google_maps(mock_maps, agent, sample_card):
    mock_maps.return_value = {
        "status": "OK",
        "address": "123 Main St, New York, NY 10001, USA",
        "city": "New York",
        "state": "NY",
        "country": "USA",
        "lat": 40.7128,
        "lng": -74.006,
    }

    with patch("src.agents.basic_info_agent.lookup_whois", return_value=None):
        with patch("src.agents.basic_info_agent.get_wayback_snapshots", return_value=[]):
            with patch("src.agents.basic_info_agent.search_company_deep", return_value=("", MagicMock())):
                with patch("src.agents.basic_info_agent.fetch_web_content", return_value=""):
                    result = agent.research(sample_card)

    assert "Google Maps" in result.content
    assert "New York" in result.content


def test_extract_domain(agent):
    assert agent._extract_domain("https://example.com") == "example.com"
    assert agent._extract_domain("http://www.example.com/path") == "example.com"
    assert agent._extract_domain("example.com") == "example.com"
    assert agent._extract_domain("example.com?q=1") == "example.com"
