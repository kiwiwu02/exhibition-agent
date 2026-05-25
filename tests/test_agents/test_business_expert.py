import pytest
from unittest.mock import patch, MagicMock
from src.agents.business_expert import BusinessExpertAgent
from src.models import BusinessCard, AgentResult

def test_business_expert_initialization():
    agent = BusinessExpertAgent()
    assert agent.name == "business_expert"

def test_business_expert_research():
    agent = BusinessExpertAgent()
    card = BusinessCard(company_name="Apple Inc.", website="https://apple.com")

    with patch('src.agents.business_expert.query_wikidata_company') as mock_wikidata, \
         patch('src.agents.business_expert.ddgs_search') as mock_ddgs:
        mock_wikidata.return_value = {"found": True, "description": "Technology company"}
        mock_ddgs.return_value = [{"title": "Apple Inc.", "body": "Technology company"}]

        result = agent.research(card)

        assert isinstance(result, AgentResult)
        assert result.agent_name == "business_expert"
