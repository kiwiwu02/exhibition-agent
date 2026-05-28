import pytest
from unittest.mock import patch, MagicMock
from src.tools.linkedin_scraper import search_company, search_people, get_company_employees


def test_search_company_returns_dict():
    result = search_company("Example Corp")
    assert isinstance(result, dict)


def test_search_company_empty_query():
    result = search_company("")
    assert isinstance(result, dict)
    assert result.get("error") is not None or result.get("companies") is not None


def test_search_people_returns_dict():
    result = search_people("John Smith")
    assert isinstance(result, dict)


def test_search_people_empty_query():
    result = search_people("")
    assert isinstance(result, dict)
    assert result.get("error") is not None or result.get("people") is not None


@patch("src.tools.linkedin_scraper.httpx.Client")
def test_search_company_success(mock_client_class):
    mock_response = MagicMock()
    mock_response.text = """
    <html><body>
    <div class="g">
        <h3>Example Corp - LinkedIn</h3>
        <a href="https://www.linkedin.com/company/example-corp">link</a>
        <div class="VwiC3b">Example Corp is a leading technology company...</div>
    </div>
    <div class="g">
        <h3>Example Corp | LinkedIn</h3>
        <a href="https://www.linkedin.com/company/example-corp-2">link</a>
        <div class="VwiC3b">Another company description...</div>
    </div>
    </body></html>
    """
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_class.return_value = mock_client

    result = search_company("Example Corp")
    assert "companies" in result
    assert len(result["companies"]) > 0
    assert "linkedin.com" in result["companies"][0]["url"]


@patch("src.tools.linkedin_scraper.httpx.Client")
def test_search_people_success(mock_client_class):
    mock_response = MagicMock()
    mock_response.text = """
    <html><body>
    <div class="g">
        <h3>John Smith - CEO at Example Corp - LinkedIn</h3>
        <a href="https://www.linkedin.com/in/john-smith">link</a>
        <div class="VwiC3b">CEO at Example Corp with 10+ years experience...</div>
    </div>
    </body></html>
    """
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_class.return_value = mock_client

    result = search_people("John Smith")
    assert "people" in result
    assert len(result["people"]) > 0
    assert "linkedin.com" in result["people"][0]["url"]


@patch("src.tools.linkedin_scraper.httpx.Client")
def test_get_company_employees(mock_client_class):
    mock_response = MagicMock()
    mock_response.text = """
    <html><body>
    <div class="g">
        <h3>Example Corp - LinkedIn</h3>
        <a href="https://www.linkedin.com/company/example-corp">link</a>
        <div class="VwiC3b">Example Corp has 500-1000 employees on LinkedIn...</div>
    </div>
    </body></html>
    """
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_class.return_value = mock_client

    result = get_company_employees("Example Corp")
    assert "company" in result
    assert result["company"] == "Example Corp"
