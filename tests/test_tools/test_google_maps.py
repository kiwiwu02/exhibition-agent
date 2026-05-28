import pytest
from unittest.mock import patch, MagicMock
from src.tools.google_maps import get_address_info


def test_get_address_info_returns_dict():
    result = get_address_info("123 Main St, New York, NY")
    assert isinstance(result, dict)


def test_get_address_info_empty_query():
    result = get_address_info("")
    assert isinstance(result, dict)
    assert result.get("error") is not None or result.get("address") is not None


@patch("src.tools.google_maps.httpx.Client")
@patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"})
def test_get_address_info_success(mock_client_class):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "formatted_address": "123 Main St, New York, NY 10001, USA",
                "address_components": [
                    {"long_name": "123", "types": ["street_number"]},
                    {"long_name": "Main St", "types": ["route"]},
                    {"long_name": "New York", "types": ["locality"]},
                    {"long_name": "NY", "types": ["administrative_area_level_1"]},
                    {"long_name": "10001", "types": ["postal_code"]},
                    {"long_name": "USA", "types": ["country"]},
                ],
                "geometry": {"location": {"lat": 40.7128, "lng": -74.0060}},
            }
        ],
        "status": "OK",
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_class.return_value = mock_client

    result = get_address_info("123 Main St, New York, NY")
    assert result["status"] == "OK"
    assert result["address"] == "123 Main St, New York, NY 10001, USA"
    assert result["city"] == "New York"
