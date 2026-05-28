"""SEC EDGAR 美国上市公司财务数据查询工具"""
import logging
from typing import Dict, Any, List

import httpx

logger = logging.getLogger(__name__)

SEC_EDGAR_API = "https://efts.sec.gov/LATEST"
SEC_EDGAR_COMPANY_API = "https://data.sec.gov"

# SEC EDGAR 要求的 User-Agent
HEADERS = {
    "User-Agent": "ExhibitionAgent/1.0 (research@example.com)",
    "Accept": "application/json",
}


def search_company_filings(
    company_name: str,
    form_type: str = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """搜索公司提交的 SEC 文件

    Args:
        company_name: 公司名称
        form_type: 可选，文件类型（如 10-K, 10-Q, 8-K）
        limit: 最大返回数量

    Returns:
        包含文件列表的字典
    """
    if not company_name or not company_name.strip():
        return {"error": "Company name is required", "filings": []}

    try:
        params = {
            "q": f'"{company_name.strip()}"',
            "dateRange": "custom",
            "startdt": "2022-01-01",
            "forms": form_type or "10-K,10-Q,8-K",
        }

        with httpx.Client(timeout=30, headers=HEADERS) as client:
            response = client.get(
                f"{SEC_EDGAR_API}/search-index",
                params=params,
            )
            response.raise_for_status()

        data = response.json()
        hits = data.get("hits", {}).get("hits", [])

        filings = []
        for hit in hits[:limit]:
            source = hit.get("_source", {})
            filings.append({
                "company_name": source.get("entity_name", ""),
                "form_type": source.get("form_type", ""),
                "file_date": source.get("file_date", ""),
                "display_names": source.get("display_names", []),
            })

        logger.info(f"SEC EDGAR search for '{company_name}': found {len(filings)} filings")
        return {"filings": filings}

    except Exception as e:
        logger.warning(f"SEC EDGAR search failed for '{company_name}': {e}")
        return {"error": str(e), "filings": []}


def get_company_info(cik: str) -> Dict[str, Any]:
    """获取公司基本信息

    Args:
        cik: 公司 CIK 编号

    Returns:
        公司信息字典
    """
    try:
        with httpx.Client(timeout=30, headers=HEADERS) as client:
            response = client.get(
                f"{SEC_EDGAR_API}/submissions/CIK{cik.zfill(10)}.json",
            )
            response.raise_for_status()

        data = response.json()
        result = {
            "cik": cik,
            "name": data.get("name", ""),
            "tickers": data.get("tickers", []),
            "exchanges": data.get("exchanges", []),
            "sic": data.get("sic", ""),
            "sic_description": data.get("sic_description", ""),
            "entity_type": data.get("entity_type", ""),
            "phone": data.get("phone", ""),
            "website": data.get("website", ""),
            "state": data.get("state", ""),
            "state_of_incorporation": data.get("state_of_incorporation", ""),
            "fiscal_year_end": data.get("fiscal_year_end", ""),
            "source": "SEC EDGAR",
        }

        logger.info(f"SEC EDGAR company info: {result['name']}")
        return result

    except Exception as e:
        logger.warning(f"SEC EDGAR company info failed for CIK {cik}: {e}")
        return {"error": str(e)}
