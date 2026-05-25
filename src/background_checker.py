# src/background_checker.py
import httpx
from .config import config

def search_company_info(company_name: str, country: str = "") -> dict:
    """使用Tavily搜索公司信息"""

    search_queries = [
        f"{company_name} company overview business",
        f"{company_name} {country} financial status",
        f"{company_name} leadership team executives",
        f"{company_name} recent news 2024"
    ]

    results = {
        "company_name": company_name,
        "basic_info": {},
        "financial_info": {},
        "leadership": {},
        "recent_news": [],
        "sources": []
    }

    for query in search_queries:
        search_result = tavily_search(query)
        if search_result:
            results["sources"].extend(search_result.get("sources", []))
            # 根据查询类型分类结果
            if "overview" in query.lower():
                results["basic_info"] = search_result
            elif "financial" in query.lower():
                results["financial_info"] = search_result
            elif "leadership" in query.lower():
                results["leadership"] = search_result
            elif "news" in query.lower():
                results["recent_news"] = search_result.get("results", [])

    return results

def tavily_search(query: str) -> dict:
    """调用Tavily搜索API"""
    if not config.tavily.api_key:
        return {}

    try:
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": config.tavily.api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": True,
                "max_results": 5
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Tavily搜索失败: {e}")
        return {}
