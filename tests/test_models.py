# tests/test_models.py
import pytest
from src.models import ResearchReport, AgentResult

def test_research_report_creation():
    report = ResearchReport(
        company_name="Test Corp",
        basic_info="Basic info content",
        business_track="Business track content",
        financial_health="Financial health content",
        org_structure="Org structure content",
        news_reputation="News reputation content",
        sources=["https://example.com"]
    )
    assert report.company_name == "Test Corp"
    assert len(report.sources) == 1

def test_agent_result_creation():
    result = AgentResult(
        agent_name="business_expert",
        content="Analysis content",
        sources=["https://example.com"],
        confidence="high"
    )
    assert result.agent_name == "business_expert"
    assert result.confidence == "high"
