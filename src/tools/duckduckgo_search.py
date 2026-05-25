from duckduckgo_search import DDGS
from typing import List, Dict

def ddgs_search(query: str, max_results: int = 5) -> List[Dict]:
    """使用DuckDuckGo搜索

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数

    Returns:
        搜索结果列表，每个结果包含title, href, body
    """
    if not query:
        return []

    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=max_results)]
            return results
    except Exception as e:
        print(f"DuckDuckGo搜索失败: {e}")
        return []

def ddgs_news_search(query: str, max_results: int = 5) -> List[Dict]:
    """使用DuckDuckGo搜索新闻

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数

    Returns:
        新闻结果列表
    """
    if not query:
        return []

    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.news(query, max_results=max_results)]
            return results
    except Exception as e:
        print(f"DuckDuckGo新闻搜索失败: {e}")
        return []