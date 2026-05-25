import pytest
from unittest.mock import patch
from src.agents.pr_expert import PRExpertAgent
from src.models import BusinessCard, AgentResult

def test_pr_expert_initialization():
    agent = PRExpertAgent()
    assert agent.name == "pr_expert"

def test_pr_expert_research():
    agent = PRExpertAgent()
    card = BusinessCard(company_name="Apple Inc.")

    with patch('src.agents.pr_expert.fetch_google_news') as mock_news, \
         patch('src.agents.pr_expert.ddgs_search') as mock_ddgs:
        mock_news.return_value = [{"title": "Apple news", "link": "https://example.com"}]
        mock_ddgs.return_value = [{"title": "Apple reviews", "body": "Good company"}]

        result = agent.research(card)

        assert isinstance(result, AgentResult)
        assert result.agent_name == "pr_expert"
