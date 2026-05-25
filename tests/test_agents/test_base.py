import pytest
from src.agents.base import BaseAgent
from src.models import BusinessCard, AgentResult


def test_base_agent_initialization():
    """测试Agent基类初始化"""
    agent = ConcreteAgent(name="test_agent")
    assert agent.name == "test_agent"


class ConcreteAgent(BaseAgent):
    """测试用的具体Agent"""

    def research(self, card: BusinessCard) -> AgentResult:
        return self._create_result(
            content="Test content",
            sources=["https://example.com"]
        )


def test_base_agent_research():
    """测试Agent基类research方法返回AgentResult"""
    agent = ConcreteAgent(name="test_agent")
    card = BusinessCard(company_name="Test Corp")
    result = agent.research(card)
    assert isinstance(result, AgentResult)
    assert result.agent_name == "test_agent"
