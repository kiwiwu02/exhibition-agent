import pytest
from unittest.mock import patch, MagicMock
from src.tools.whois_lookup import lookup_whois


def test_lookup_whois_returns_dict():
    result = lookup_whois("example.com")
    assert isinstance(result, dict)


def test_lookup_whois_invalid_domain():
    result = lookup_whois("not-a-valid-domain-xyz123.com")
    assert isinstance(result, dict)
    assert result.get("error") is not None or result.get("domain") is not None


@patch("whois.whois")
def test_lookup_whois_success(mock_whois):
    mock_whois.return_value = MagicMock(
        domain_name="example.com",
        registrar="Example Registrar",
        creation_date="2010-03-20",
        expiration_date="2025-03-20",
        name_servers=["ns1.example.com", "ns2.example.com"],
        org="Example Org",
        country="US",
    )
    result = lookup_whois("example.com")
    assert result["domain"] == "example.com"
    assert result["registrar"] == "Example Registrar"
