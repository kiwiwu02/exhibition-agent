# tests/test_integration.py
import pytest
from unittest.mock import patch, MagicMock
from src.agents.supervisor import SupervisorAgent
from src.models import BusinessCard


def test_full_research_pipeline():
    """测试完整调研流程 - 从SupervisorAgent到报告生成"""
    supervisor = SupervisorAgent()
    card = BusinessCard(
        company_name="Apple Inc.",
        country="USA",
        website="https://apple.com"
    )

    # Mock所有外部API调用 - 使用正确的模块路径
    with patch('src.agents.business_expert.query_wikidata_company') as mock_wikidata, \
         patch('src.agents.business_expert.ddgs_search') as mock_ddgs_business, \
         patch('src.agents.compliance_expert.ddgs_search') as mock_ddgs_compliance, \
         patch('src.agents.org_expert.ddgs_search') as mock_ddgs_org, \
         patch('src.agents.pr_expert.ddgs_search') as mock_ddgs_pr, \
         patch('src.agents.pr_expert.fetch_google_news') as mock_news:

        mock_wikidata.return_value = {
            "found": True,
            "description": "Technology company",
            "industry": "Technology",
            "country": "United States",
            "wikidata_id": "Q312"
        }
        mock_ddgs_business.return_value = [
            {"title": "Apple Inc.", "href": "https://example.com", "body": "Technology company"}
        ]
        mock_ddgs_compliance.return_value = [
            {"title": "Apple Financial Report", "href": "https://finance.example.com", "body": "Revenue data"}
        ]
        mock_ddgs_org.return_value = [
            {"title": "Apple CEO", "href": "https://linkedin.example.com", "body": "Tim Cook"}
        ]
        mock_ddgs_pr.return_value = [
            {"title": "Apple Reviews", "href": "https://reviews.example.com", "body": "Good company"}
        ]
        mock_news.return_value = [
            {"title": "Apple launches new product", "link": "https://news.example.com"}
        ]

        report = supervisor.research(card)

        assert report.company_name == "Apple Inc."
        assert report.verified == True
        assert len(report.sources) > 0
        assert report.basic_info != ""
        assert report.financial_health != ""


def test_all_experts_called():
    """测试所有专家Agent都被调用"""
    supervisor = SupervisorAgent()
    card = BusinessCard(company_name="Google LLC", country="USA")

    with patch.object(supervisor.business_expert, 'research') as mock_business, \
         patch.object(supervisor.compliance_expert, 'research') as mock_compliance, \
         patch.object(supervisor.org_expert, 'research') as mock_org, \
         patch.object(supervisor.pr_expert, 'research') as mock_pr, \
         patch.object(supervisor.fact_checker, 'verify') as mock_verify:

        mock_business.return_value = MagicMock(agent_name="business_expert", content="Business info", sources=["url1"])
        mock_compliance.return_value = MagicMock(agent_name="compliance_expert", content="Compliance info", sources=["url2"])
        mock_org.return_value = MagicMock(agent_name="org_expert", content="Org info", sources=["url3"])
        mock_pr.return_value = MagicMock(agent_name="pr_expert", content="PR info", sources=["url4"])
        mock_verify.return_value = [MagicMock(agent_name="business_expert", content="Verified", sources=["url1"])]

        supervisor.research(card)

        mock_business.assert_called_once()
        mock_compliance.assert_called_once()
        mock_org.assert_called_once()
        mock_pr.assert_called_once()
        mock_verify.assert_called_once()


def test_fact_checker_validation():
    """测试事实风控审计Agent验证逻辑"""
    from src.agents.fact_checker import FactCheckerAgent

    checker = FactCheckerAgent()

    # 有来源的结果
    result_with_source = MagicMock()
    result_with_source.content = "This is verified [来源: https://example.com]"
    result_with_source.sources = ["https://example.com"]

    # 无来源的结果
    result_no_source = MagicMock()
    result_no_source.content = "This is unverified"
    result_no_source.sources = []

    results = [result_with_source, result_no_source]

    with patch.object(checker, '_validate_sources', return_value=True):
        verified = checker.verify(results)
        assert len(verified) > 0


def test_report_assembly():
    """测试报告组装逻辑"""
    supervisor = SupervisorAgent()

    results = [
        MagicMock(agent_name="business_expert", content="Business content", sources=["url1"]),
        MagicMock(agent_name="compliance_expert", content="Compliance content", sources=["url2"]),
        MagicMock(agent_name="org_expert", content="Org content", sources=["url3"]),
        MagicMock(agent_name="pr_expert", content="PR content", sources=["url4"]),
    ]

    report = supervisor._assemble_report("Test Company", results)

    assert report.company_name == "Test Company"
    assert report.basic_info == "Business content"
    assert report.financial_health == "Compliance content"
    assert report.org_structure == "Org content"
    assert report.news_reputation == "PR content"
    assert len(report.sources) == 4
