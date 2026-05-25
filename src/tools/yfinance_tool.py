import yfinance as yf
from typing import Dict, Optional

def query_company_financials(ticker: str) -> Dict:
    """查询上市公司财务信息

    Args:
        ticker: 股票代码（如AAPL, 0005.HK）

    Returns:
        包含财务信息的字典
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        return {
            "ticker": ticker,
            "found": True,
            "name": info.get("longName") or info.get("shortName", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency", ""),
            "employees": info.get("fullTimeEmployees"),
            "website": info.get("website", ""),
            "description": info.get("longBusinessSummary", ""),
            "country": info.get("country", ""),
        }

    except Exception as e:
        print(f"yfinance查询失败: {e}")
        return {"ticker": ticker, "found": False, "error": str(e)}

def search_ticker(company_name: str) -> Optional[str]:
    """根据公司名称搜索股票代码

    Args:
        company_name: 公司名称

    Returns:
        股票代码或None
    """
    try:
        search = yf.Search(company_name)
        if search.tickers:
            return search.tickers[0].symbol
        return None
    except Exception as e:
        print(f"股票代码搜索失败: {e}")
        return None
