import pytest
from unittest.mock import patch, MagicMock
from src.tools.wayback_machine import get_wayback_snapshots


def test_get_wayback_snapshots_returns_list():
    result = get_wayback_snapshots("example.com")
    assert isinstance(result, list)


def test_get_wayback_snapshots_invalid_domain():
    result = get_wayback_snapshots("not-a-valid-domain-xyz123.com")
    assert isinstance(result, list)


@patch("src.tools.wayback_machine.httpx.Client")
def test_get_wayback_snapshots_success(mock_client_class):
    mock_response = MagicMock()
    # CDX API returns list of lists: first row is headers, rest are data
    mock_response.json.return_value = [
        ["timestamp", "statuscode", "original", "mimetype"],
        ["20220101", "200", "http://example.com", "text/html"],
        ["20230101", "200", "http://example.com", "text/html"],
        ["20240101", "200", "http://example.com", "text/html"],
    ]
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_class.return_value = mock_client

    result = get_wayback_snapshots("example.com", years=3)
    assert len(result) > 0
    assert "timestamp" in result[0]
    assert "url" in result[0]
