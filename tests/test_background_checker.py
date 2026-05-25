# tests/test_background_checker.py
import pytest
from unittest.mock import patch, MagicMock
import httpx
from src.background_checker import search_company_info, tavily_search

class TestSearchCompanyInfo:
    """测试search_company_info函数"""

    @patch('src.background_checker.tavily_search')
    def test_search_company_info_正常调用(self, mock_tavily_search):
        """测试search_company_info正常调用"""
        # Mock返回数据
        mock_tavily_search.return_value = {
            "results": [{"title": "test", "content": "test content"}],
            "sources": ["https://example.com"]
        }

        result = search_company_info("Apple Inc.", "USA")

        assert result["company_name"] == "Apple Inc."
        assert "basic_info" in result
        assert "financial_info" in result
        assert "leadership" in result
        assert "recent_news" in result
        assert "sources" in result
        # 验证tavily_search被调用了4次（4个查询）
        assert mock_tavily_search.call_count == 4

    @patch('src.background_checker.tavily_search')
    def test_search_company_info_无搜索结果(self, mock_tavily_search):
        """测试无搜索结果的情况"""
        mock_tavily_search.return_value = {}

        result = search_company_info("NonExistent Company")

        assert result["company_name"] == "NonExistent Company"
        assert result["basic_info"] == {}
        assert result["financial_info"] == {}
        assert result["leadership"] == {}
        assert result["recent_news"] == []
        assert result["sources"] == []

class TestTavilySearch:
    """测试tavily_search函数"""

    @patch('src.background_checker.config')
    def test_tavily_search_无API_key返回空dict(self, mock_config):
        """测试无API key时返回空dict"""
        mock_config.tavily.api_key = ""

        result = tavily_search("test query")

        assert result == {}

    @patch('src.background_checker.httpx.post')
    @patch('src.background_checker.config')
    def test_tavily_search_网络错误返回空dict(self, mock_config, mock_post):
        """测试网络错误时返回空dict"""
        mock_config.tavily.api_key = "test_key"
        mock_post.side_effect = httpx.RequestError("Network error")

        result = tavily_search("test query")

        assert result == {}

    @patch('src.background_checker.httpx.post')
    @patch('src.background_checker.config')
    def test_tavily_search_HTTP状态错误返回空dict(self, mock_config, mock_post):
        """测试HTTP状态错误时返回空dict"""
        mock_config.tavily.api_key = "test_key"
        response = MagicMock()
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="401 Unauthorized",
            request=MagicMock(),
            response=MagicMock(status_code=401)
        )
        mock_post.return_value = response

        result = tavily_search("test query")

        assert result == {}

    @patch('src.background_checker.httpx.post')
    @patch('src.background_checker.config')
    def test_tavily_search_JSON解析错误返回空dict(self, mock_config, mock_post):
        """测试JSON解析错误时返回空dict"""
        mock_config.tavily.api_key = "test_key"
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = response

        result = tavily_search("test query")

        assert result == {}

    @patch('src.background_checker.httpx.post')
    @patch('src.background_checker.config')
    def test_tavily_search_成功返回结果(self, mock_config, mock_post):
        """测试成功返回结果"""
        mock_config.tavily.api_key = "test_key"
        expected_result = {
            "results": [{"title": "Test", "content": "Test content"}],
            "answer": "Test answer"
        }
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = expected_result
        mock_post.return_value = response

        result = tavily_search("test query")

        assert result == expected_result
