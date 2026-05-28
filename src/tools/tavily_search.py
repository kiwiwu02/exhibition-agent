# src/tools/tavily_search.py
from typing import List, Dict
from ..config import config

def tavily_search(query: str, max_results: int = 5) -> List[Dict]:
    """使用Tavily进行语义搜索（返回网页全文内容）

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数

    Returns:
        搜索结果列表，每个结果包含title, url, content(摘要), raw_content(全文)
    """
    if not query:
        return []

    api_key = config.tavily.api_key
    if not api_key:
        print("Tavily API Key未配置")
        return []

    try:
        import httpx

        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": True
            },
            timeout=30
        )
        data = response.json()

        if "results" in data:
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "raw_content": r.get("raw_content", "")
                }
                for r in data["results"]
            ]
        return []
    except Exception as e:
        print(f"Tavily搜索失败: {e}")
        return []
