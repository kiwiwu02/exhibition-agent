import pytest
from src.tools.google_news_rss import fetch_google_news

def test_fetch_google_news():
    results = fetch_google_news("Apple Inc.", max_results=5)
    assert isinstance(results, list)
    assert len(results) <= 5
