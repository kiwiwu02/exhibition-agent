from duckduckgo_search import DDGS
from typing import List, Dict
from .tavily_search import tavily_search

def ddgs_search(query: str, max_results: int = 5) -> List[Dict]:
    """使用DuckDuckGo搜索，失败时回退到Tavily

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数

    Returns:
        搜索结果列表，每个结果包含title, href, body, raw_content
    """
    if not query:
        return []

    # 尝试DuckDuckGo
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=max_results)]
            if results:
                return [{"title": r.get("title", ""), "href": r.get("href", ""), "body": r.get("body", ""), "raw_content": ""} for r in results]
    except Exception as e:
        print(f"DuckDuckGo搜索失败: {e}")

    # 回退到Tavily（含全文内容）
    print("使用Tavily搜索...")
    tavily_results = tavily_search(query, max_results)
    return [{"title": r.get("title", ""), "href": r.get("url", ""), "body": r.get("content", ""), "raw_content": r.get("raw_content", "")} for r in tavily_results]


def ddgs_news_search(query: str, max_results: int = 5) -> List[Dict]:
    """使用DuckDuckGo搜索新闻，失败时回退到Tavily

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数

    Returns:
        新闻结果列表
    """
    if not query:
        return []

    # 尝试DuckDuckGo
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.news(query, max_results=max_results)]
            if results:
                return [{"title": r.get("title", ""), "href": r.get("url", ""), "body": r.get("body", ""), "raw_content": ""} for r in results]
    except Exception as e:
        print(f"DuckDuckGo新闻搜索失败: {e}")

    # 回退到Tavily
    print("使用Tavily新闻搜索...")
    tavily_results = tavily_search(f"{query} news", max_results)
    return [{"title": r.get("title", ""), "href": r.get("url", ""), "body": r.get("content", ""), "raw_content": r.get("raw_content", "")} for r in tavily_results]
