# tests/test_company_discovery.py
import pytest
from unittest.mock import patch, MagicMock
from src.company_discovery import (
    discover_company_name,
    _extract_domain,
    _extract_email_domain,
    _extract_company_from_linkedin_desc,
)
from src.models import BusinessCard


class TestExtractDomain:
    def test_extract_from_url(self):
        assert _extract_domain("https://www.example.com/path") == "example.com"

    def test_extract_from_bare_domain(self):
        assert _extract_domain("example.com") == "example.com"

    def test_extract_with_www(self):
        assert _extract_domain("https://www.acme.com") == "acme.com"

    def test_extract_empty(self):
        assert _extract_domain("") == ""
        assert _extract_domain(None) == ""


class TestExtractEmailDomain:
    def test_normal_email(self):
        assert _extract_email_domain("john@example.com") == "example.com"

    def test_empty(self):
        assert _extract_email_domain("") == ""
        assert _extract_email_domain("invalid") == ""


class TestWhoisStrategy:
    @patch("src.tools.whois_lookup.lookup_whois")
    def test_success(self, mock_whois):
        from src.company_discovery import _whois_strategy
        mock_whois.return_value = {"org": "Acme Corporation"}
        cn, cn_en = _whois_strategy("acme.com")
        assert cn_en == "Acme Corporation"

    @patch("src.tools.whois_lookup.lookup_whois")
    def test_privacy_protection(self, mock_whois):
        from src.company_discovery import _whois_strategy
        mock_whois.return_value = {"org": "REDACTED FOR PRIVACY"}
        cn, cn_en = _whois_strategy("example.com")
        assert cn == ""
        assert cn_en == ""

    @patch("src.tools.whois_lookup.lookup_whois")
    def test_error(self, mock_whois):
        from src.company_discovery import _whois_strategy
        mock_whois.return_value = {"error": "not found"}
        cn, cn_en = _whois_strategy("nonexistent.com")
        assert cn == ""


class TestExtractCompanyFromLinkedin:
    def test_at_format(self):
        desc = "John Smith · CEO at Acme Corp · San Francisco"
        result = _extract_company_from_linkedin_desc(desc, "")
        assert "Acme" in result

    def test_dash_format(self):
        desc = "John Smith - Acme Corp - CEO"
        result = _extract_company_from_linkedin_desc(desc, "")
        assert "Acme" in result


class TestDiscoverCompanyName:
    def test_skip_if_already_has_name(self):
        card = BusinessCard(company_name="Existing Corp")
        cn, cn_en, source = discover_company_name(card)
        assert cn == ""

    @patch("src.company_discovery._whois_strategy")
    def test_whois_website_strategy(self, mock_whois):
        card = BusinessCard(website="https://acme.com")
        mock_whois.return_value = ("", "Acme Industries")
        cn, cn_en, source = discover_company_name(card)
        assert cn_en == "Acme Industries"
        assert source == "whois_website"

    @patch("src.company_discovery._whois_strategy")
    def test_whois_email_strategy(self, mock_whois):
        card = BusinessCard(email="john@bigcorp.com")
        mock_whois.return_value = ("", "Big Corp Inc")
        cn, cn_en, source = discover_company_name(card)
        assert cn_en == "Big Corp Inc"
        assert source == "whois_email"

    def test_skip_free_email(self):
        card = BusinessCard(email="john@gmail.com")
        cn, cn_en, source = discover_company_name(card)
        # 不应该触发 WHOIS（公共邮箱跳过）
        assert source != "whois_email"

    @patch("src.company_discovery._linkedin_people_strategy")
    def test_linkedin_people_strategy(self, mock_linkedin):
        card = BusinessCard(contact_name="John Smith")
        mock_linkedin.return_value = ("", "TechCorp")
        cn, cn_en, source = discover_company_name(card)
        assert cn_en == "TechCorp"
        assert source == "linkedin_people"

    def test_no_info_returns_empty(self):
        card = BusinessCard()
        cn, cn_en, source = discover_company_name(card)
        assert cn == ""
        assert cn_en == ""
        assert source == ""


class TestExtractCompanyFromLinkedin:
    def test_at_format(self):
        desc = "John Smith · CEO at Acme Corp · San Francisco"
        result = _extract_company_from_linkedin_desc(desc, "")
        assert "Acme" in result

    def test_dash_format(self):
        desc = "John Smith - Acme Corp - CEO"
        result = _extract_company_from_linkedin_desc(desc, "")
        assert "Acme" in result


class TestDiscoverCompanyName:
    def test_skip_if_already_has_name(self):
        card = BusinessCard(company_name="Existing Corp")
        cn, cn_en, source = discover_company_name(card)
        assert cn == ""

    @patch("src.company_discovery._whois_strategy")
    def test_whois_website_strategy(self, mock_whois):
        card = BusinessCard(website="https://acme.com")
        mock_whois.return_value = ("", "Acme Industries")
        cn, cn_en, source = discover_company_name(card)
        assert cn_en == "Acme Industries"
        assert source == "whois_website"

    @patch("src.company_discovery._whois_strategy")
    def test_whois_email_strategy(self, mock_whois):
        card = BusinessCard(email="john@bigcorp.com")
        mock_whois.return_value = ("", "Big Corp Inc")
        cn, cn_en, source = discover_company_name(card)
        assert cn_en == "Big Corp Inc"
        assert source == "whois_email"

    def test_skip_free_email(self):
        card = BusinessCard(email="john@gmail.com")
        cn, cn_en, source = discover_company_name(card)
        # 不应该触发 WHOIS（公共邮箱跳过）
        assert source != "whois_email"

    @patch("src.company_discovery._linkedin_people_strategy")
    def test_linkedin_people_strategy(self, mock_linkedin):
        card = BusinessCard(contact_name="John Smith")
        mock_linkedin.return_value = ("", "TechCorp")
        cn, cn_en, source = discover_company_name(card)
        assert cn_en == "TechCorp"
        assert source == "linkedin_people"

    def test_no_info_returns_empty(self):
        card = BusinessCard()
        cn, cn_en, source = discover_company_name(card)
        assert cn == ""
        assert cn_en == ""
        assert source == ""
