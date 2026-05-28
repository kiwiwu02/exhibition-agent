"""PR专家 Agent 测试"""
import pytest
from unittest.mock import patch, MagicMock
from src.agents.pr_expert import PRExpertAgent
from src.models import BusinessCard, AgentResult


def test_pr_expert_initialization():
    agent = PRExpertAgent()
    assert agent.name == "pr_expert"


def test_pr_expert_research():
    agent = PRExpertAgent()
    card = BusinessCard(company_name="Apple Inc.")

    with patch('src.agents.pr_expert.ddgs_search') as mock_ddgs:
        mock_ddgs.return_value = [{"title": "Apple reviews", "href": "https://example.com", "body": "Good company"}]

        with patch('src.agents.pr_expert.crawl_and_extract') as mock_crawl:
            mock_crawl.return_value = ({}, {})

            result = agent.research(card)

            assert isinstance(result, AgentResult)
            assert result.agent_name == "pr_expert"
