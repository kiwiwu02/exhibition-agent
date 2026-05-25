import pytest
from src.tools.wikidata import query_wikidata_company

def test_query_wikidata_company():
    result = query_wikidata_company("Apple Inc.")
    assert isinstance(result, dict)
    assert "company_name" in result
