import pytest
from unittest.mock import patch, MagicMock
from src.tools.trustpilot_scraper import search_company_reviews, get_company_rating


def test_search_company_reviews_returns_dict():
    result = search_company_reviews("Example Corp")
    assert isinstance(result, dict)


def test_search_company_reviews_empty_query():
    result = search_company_reviews("")
    assert isinstance(result, dict)
    assert result.get("error") is not None or result.get("reviews") is not None


def test_get_company_rating_returns_dict():
    result = get_company_rating("example.com")
    assert isinstance(result, dict)


def test_get_company_rating_empty_slug():
    result = get_company_rating("")
    assert isinstance(result, dict)
    assert result.get("error") is not None


@patch("src.tools.trustpilot_scraper.httpx.Client")
def test_search_company_reviews_success(mock_client_class):
    mock_response = MagicMock()
    mock_response.text = """
    <html><body>
    <div class="g">
        <h3>Example Corp Reviews - Trustpilot</h3>
        <a href="https://www.trustpilot.com/review/example.com">link</a>
        <div class="VwiC3b">Example Corp rated 4.2 out of 5 based on 120 reviews...</div>
    </div>
    </body></html>
    """
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_class.return_value = mock_client

    result = search_company_reviews("Example Corp")
    assert "reviews" in result
    assert len(result["reviews"]) > 0
    assert result["reviews"][0]["company_slug"] == "example.com"
    assert result["reviews"][0]["rating"] == 4.2


@patch("src.tools.trustpilot_scraper.httpx.Client")
def test_get_company_rating_success(mock_client_class):
    mock_response = MagicMock()
    mock_response.text = """
    <html><body>
    <p class="typography_heading-xl__T28xz">4.2</p>
    <p class="typography_body-l__KUYFJ">Total reviews: 120</p>
    <div class="styles_fractionalValue__35WbH">4.5</div>
    </body></html>
    """
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_class.return_value = mock_client

    result = get_company_rating("example.com")
    assert result["rating"] == 4.2
    assert result["trust_score"] == 4.5
    assert result["company_slug"] == "example.com"
