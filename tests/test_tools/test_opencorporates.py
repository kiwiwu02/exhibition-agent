import pytest
from unittest.mock import patch, MagicMock
from src.tools.opencorporates import search_company


def test_search_company_returns_dict():
    result = search_company("Example Corp")
    assert isinstance(result, dict)


def test_search_company_empty_query():
    result = search_company("")
    assert isinstance(result, dict)
    assert result.get("error") is not None or result.get("companies") is not None


@patch("src.tools.opencorporates.httpx.Client")
def test_search_company_success(mock_client_class):
    mock_response = MagicMock()
    # OpenCorporates API returns nested company objects
    mock_response.json.return_value = {
        "results": {
            "companies": [
                {
                    "company": {
                        "name": "Example Corp",
                        "jurisdiction_code": "us_de",
                        "company_number": "1234567",
                        "current_status": "Active",
                        "incorporation_date": "2010-03-20",
                        "agent_name": "Example Agent",
                        "registered_address_in_full": "123 Main St, Wilmington, DE",
                        "type": "Corporation",
                        "opencorporates_url": "https://opencorporates.com/companies/us_de/1234567",
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

    result = search_company("Example Corp")
    assert "companies" in result
    assert len(result["companies"]) > 0
    assert result["companies"][0]["name"] == "Example Corp"
    assert result["companies"][0]["status"] == "Active"
