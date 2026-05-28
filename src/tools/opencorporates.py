"""OpenCorporates 全球企业工商信息查询工具"""
import logging
from typing import Dict, Any, List

import httpx

logger = logging.getLogger(__name__)

OPENCORPORATES_API = "https://api.opencorporates.com/v0.4"


def search_company(
    query: str,
    jurisdiction_code: str = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """搜索公司工商信息

    Args:
        query: 公司名称搜索关键词
        jurisdiction_code: 可选，司法管辖区代码（如 us_de, uk_gb）
        limit: 最大返回数量

    Returns:
        包含公司列表的字典
    """
    if not query or not query.strip():
        return {"error": "Query is required", "companies": []}

    try:
        params = {
            "q": query.strip(),
            "per_page": limit,
        }
        if jurisdiction_code:
            params["jurisdiction_code"] = jurisdiction_code

        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{OPENCORPORATES_API}/companies/search",
                params=params,
            )
            response.raise_for_status()

        data = response.json()
        companies = data.get("results", {}).get("companies", [])

        result = []
        for comp in companies:
            company = comp.get("company", {})
            result.append({
                "name": company.get("name", ""),
                "jurisdiction_code": company.get("jurisdiction_code", ""),
                "company_number": company.get("company_number", ""),
                "status": company.get("current_status", ""),
                "incorporation_date": company.get("incorporation_date", ""),
                "dissolution_date": company.get("dissolution_date", ""),
                "agent_name": company.get("agent_name", ""),
                "registered_address": company.get("registered_address_in_full", ""),
                "type": company.get("type", ""),
                "url": company.get("opencorporates_url", ""),
            })

        logger.info(f"OpenCorporates search for '{query}': found {len(result)} companies")
        return {"companies": result}

    except Exception as e:
        logger.warning(f"OpenCorporates search failed for '{query}': {e}")
        return {"error": str(e), "companies": []}


def get_company_details(
    jurisdiction_code: str,
    company_number: str,
) -> Dict[str, Any]:
    """获取公司详细信息

    Args:
        jurisdiction_code: 司法管辖区代码
        company_number: 公司编号

    Returns:
        公司详细信息字典
    """
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{OPENCORPORATES_API}/companies/{jurisdiction_code}/{company_number}",
            )
            response.raise_for_status()

        data = response.json()
        company = data.get("results", {}).get("company", {})

        result = {
            "name": company.get("name", ""),
            "jurisdiction_code": company.get("jurisdiction_code", ""),
            "company_number": company.get("company_number", ""),
            "status": company.get("current_status", ""),
            "incorporation_date": company.get("incorporation_date", ""),
            "dissolution_date": company.get("dissolution_date", ""),
            "agent_name": company.get("agent_name", ""),
            "registered_address": company.get("registered_address_in_full", ""),
            "type": company.get("type", ""),
            "url": company.get("opencorporates_url", ""),
            "source": "OpenCorporates",
        }

        logger.info(f"OpenCorporates company details: {result['name']}")
        return result

    except Exception as e:
        logger.warning(f"OpenCorporates company details failed: {e}")
        return {"error": str(e)}
