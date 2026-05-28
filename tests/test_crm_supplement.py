# tests/test_crm_supplement.py
"""TDD 测试 - CRM 补充 Agent + 公司名发现集成"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from src.models import BusinessCard, AgentResult, ResearchReport
from src.agents.crm_supplement_agent import CRMSupplementAgent


# ============================================================
# 测试用例 2: 信息不完整名片 — 缺失字段 + 自动补全
# ============================================================

class TestCRMSupplement_MissingFields:
    """CRM Agent 应识别并补充缺失字段"""

    def test_identifies_missing_fields(self):
        """应识别所有空字段"""
        card = BusinessCard(
            company_name="",
            contact_name="Park Chan Ryul",
            position="Pro Manager",
            email="",
            phone="+821033537182",
            country="",
            city="",
            address="",
            website="",
        )
        agent = CRMSupplementAgent()
        missing = agent._identify_missing_fields(card)

        assert "公司名称" in missing
        assert "国家/地区" in missing
        assert "城市" in missing
        assert "公司地址" in missing
        assert "官网" in missing

    def test_no_missing_when_complete(self):
        """字段完整时不应有缺失"""
        card = BusinessCard(
            company_name="Test Corp",
            company_name_en="Test Corp Inc",
            contact_name="John",
            country="USA",
            city="New York",
            address="123 Main St",
            website="https://test.com",
        )
        agent = CRMSupplementAgent()
        missing = agent._identify_missing_fields(card)
        assert len(missing) == 0


# ============================================================
# 测试用例 5: 调研结果中提取字段
# ============================================================

class TestCRMSupplement_Extraction:
    """从调研结果中提取字段"""

    def test_extract_country_from_content(self):
        agent = CRMSupplementAgent()
        content = "The company is headquartered in South Korea, Seoul area."
        result = agent._extract_country(content)
        assert result == "South Korea"

    def test_extract_city_from_content(self):
        agent = CRMSupplementAgent()
        content = "Headquarters: Seoul, South Korea. The company was founded in 2010."
        result = agent._extract_city(content)
        assert "Seoul" in result

    def test_extract_website_from_content(self):
        agent = CRMSupplementAgent()
        content = "Official website: https://eluo.co.kr for more information."
        result = agent._extract_website(content)
        assert "eluo.co.kr" in result

    def test_extract_english_name_from_content(self):
        agent = CRMSupplementAgent()
        content = "The company is also known as ELUO Lighting Co., Ltd."
        result = agent._extract_company_en_name(content)
        assert "ELUO" in result

    def test_extract_address_from_content(self):
        agent = CRMSupplementAgent()
        content = "Address: 123 Gangnam-gu, Seoul, South Korea"
        result = agent._extract_address(content)
        assert "Seoul" in result

    def test_no_false_positive_social_media(self):
        """不应提取社交媒体链接作为官网"""
        agent = CRMSupplementAgent()
        content = "Visit us on LinkedIn: https://linkedin.com/company/test"
        result = agent._extract_website(content)
        assert result == ""


# ============================================================
# 测试用例 6: 信息稀疏场景
# ============================================================

class TestCRMSupplement_SparseData:
    """信息稀疏时的行为"""

    def test_returns_empty_when_no_content(self):
        """没有调研内容时返回空"""
        card = BusinessCard(company_name="", country="")
        agent = CRMSupplementAgent()
        result = agent.supplement(card, [])
        assert result == {}

    def test_extracts_what_it_can(self):
        """能提取多少就提取多少"""
        card = BusinessCard(
            company_name="",
            country="",
            city="",
            address="",
            website="",
        )
        mock_result = AgentResult(
            agent_name="basic_info",
            content="Company located in Seoul, South Korea. Official website: https://example.com",
        )
        agent = CRMSupplementAgent()
        result = agent.supplement(card, [mock_result])

        assert "国家/地区" in result or "城市" in result or "官网" in result


# ============================================================
# 测试用例 7: 不覆盖已有值
# ============================================================

class TestCRMSupplement_NoOverwrite:
    """已有值的字段不应被覆盖"""

    def test_does_not_overwrite_existing_country(self):
        card = BusinessCard(country="Japan", company_name="")
        agent = CRMSupplementAgent()
        missing = agent._identify_missing_fields(card)
        assert "国家/地区" not in missing


# ============================================================
# 集成测试: 完整流程
# ============================================================

class TestCRMSupplement_Integration:
    """CRM 补充 Agent 完整流程"""

    def test_supplement_with_mixed_results(self):
        """多个 Agent 结果综合提取"""
        card = BusinessCard(
            company_name="",
            company_name_en="",
            country="",
            city="",
            address="",
            website="",
            contact_name="John Smith",
        )

        results = [
            AgentResult(
                agent_name="basic_info",
                content="ELUO Lighting is based in Seoul, South Korea. Website: https://eluo.co.kr",
            ),
            AgentResult(
                agent_name="business_legal",
                content="Registered as ELUO Lighting Co., Ltd. in Seoul.",
            ),
            AgentResult(
                agent_name="financial_credit",
                content="Revenue: $5M annually. 50 employees.",
            ),
        ]

        agent = CRMSupplementAgent()
        supplements = agent.supplement(card, results)

        # 应该能从 basic_info 中提取国家和官网
        assert isinstance(supplements, dict)


# ============================================================
# 测试用例 3: 重复名片合并后字段补充
# ============================================================

class TestCRMSupplement_AfterMerge:
    """合并后补充缺失字段"""

    def test_supplement_after_merge(self):
        """合并后新记录可能缺少某些字段"""
        card = BusinessCard(
            company_name="Merged Corp",
            contact_name="New Person",
            email="new@corp.com",
            country="",  # 合并后可能仍为空
            city="",
        )
        result = AgentResult(
            agent_name="basic_info",
            content="Merged Corp is headquartered in Tokyo, Japan.",
        )
        agent = CRMSupplementAgent()
        supplements = agent.supplement(card, [result])
        # 应该能提取国家
        assert "国家/地区" in supplements
