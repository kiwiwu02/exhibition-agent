import pytest
from unittest.mock import patch, MagicMock
from src.tools.sec_edgar import search_company_filings


def test_search_company_filings_returns_dict():
    result = search_company_filings("Apple Inc.")
    assert isinstance(result, dict)


def test_search_company_filings_empty_query():
    result = search_company_filings("")
    assert isinstance(result, dict)
    assert result.get("error") is not None or result.get("filings") is not None


@patch("src.tools.sec_edgar.httpx.Client")
def test_search_company_filings_success(mock_client_class):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "display_names": ["Apple Inc."],
                        "file_date": "2024-10-25",
                        "form_type": "10-K",
                        "entity_name": "Apple Inc.",
                    }
                }
            ]
        }
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_class.return_value = mock_client

    result = search_company_filings("Apple Inc.")
    assert "filings" in result
    assert len(result["filings"]) > 0
    assert result["filings"][0]["form_type"] == "10-K"
