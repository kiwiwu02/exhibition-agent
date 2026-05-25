import pytest
from unittest.mock import patch
from src.agents.org_expert import OrgExpertAgent
from src.models import BusinessCard, AgentResult

def test_org_expert_initialization():
    agent = OrgExpertAgent()
    assert agent.name == "org_expert"

def test_org_expert_research():
    agent = OrgExpertAgent()
    card = BusinessCard(company_name="Apple Inc.")

    with patch('src.agents.org_expert.ddgs_search') as mock_ddgs:
        mock_ddgs.return_value = [{"title": "Apple CEO", "body": "Tim Cook"}]

        result = agent.research(card)

        assert isinstance(result, AgentResult)
        assert result.agent_name == "org_expert"
