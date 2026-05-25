# tests/test_background_checker.py
import pytest
from src.background_checker import search_company_info

def test_search_company_info():
    result = search_company_info("Apple Inc.", "USA")
    assert "company_name" in result
    assert "basic_info" in result
