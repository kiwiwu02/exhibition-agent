import pytest
from unittest.mock import patch
from src.agents.compliance_expert import ComplianceExpertAgent
from src.models import BusinessCard, AgentResult

def test_compliance_expert_initialization():
    agent = ComplianceExpertAgent()
    assert agent.name == "compliance_expert"

def test_compliance_expert_research():
    agent = ComplianceExpertAgent()
    card = BusinessCard(company_name="Apple Inc.", country="USA")

    with patch('src.agents.compliance_expert.ddgs_search') as mock_ddgs:
        mock_ddgs.return_value = [{"title": "Apple financial report", "body": "Revenue data"}]

        result = agent.research(card)

        assert isinstance(result, AgentResult)
        assert result.agent_name == "compliance_expert"
