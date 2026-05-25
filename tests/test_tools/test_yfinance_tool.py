import pytest
from src.tools.yfinance_tool import query_company_financials

def test_query_company_financials():
    result = query_company_financials("AAPL")
    assert isinstance(result, dict)
    assert "ticker" in result
