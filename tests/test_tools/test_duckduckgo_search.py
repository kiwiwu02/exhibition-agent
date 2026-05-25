import pytest
from src.tools.duckduckgo_search import ddgs_search

def test_ddgs_search_returns_results():
    results = ddgs_search("Python programming", max_results=3)
    assert isinstance(results, list)
    assert len(results) <= 3

def test_ddgs_search_empty_query():
    results = ddgs_search("", max_results=5)
    assert isinstance(results, list)