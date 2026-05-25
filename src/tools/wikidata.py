import httpx
from typing import Dict, Optional

def query_wikidata_company(company_name: str) -> Dict:
    """查询Wikidata获取公司结构化信息

    Args:
        company_name: 公司名称

    Returns:
        包含公司信息的字典
    """
    try:
        # 使用Wikidata搜索API
        search_url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": company_name,
            "language": "en",
            "format": "json",
            "limit": 1
        }

        response = httpx.get(search_url, params=params, timeout=10)
        data = response.json()

        results = data.get("search", [])
        if not results:
            return {"company_name": company_name, "found": False}

        entity_id = results[0].get("id")

        # 获取实体详情
        entity_url = "https://www.wikidata.org/w/api.php"
        entity_params = {
            "action": "wbgetentities",
            "ids": entity_id,
            "format": "json",
            "props": "claims|labels|descriptions"
        }

        entity_response = httpx.get(entity_url, params=entity_params, timeout=10)
        entity_data = entity_response.json()

        entity = entity_data.get("entities", {}).get(entity_id, {})
        claims = entity.get("claims", {})

        # 提取关键信息
        return {
            "company_name": company_name,
            "found": True,
            "wikidata_id": entity_id,
            "description": entity.get("descriptions", {}).get("en", {}).get("value", ""),
            "website": _extract_claim_value(claims, "P856"),
            "industry": _extract_claim_value(claims, "P452"),
            "founders": _extract_claim_value(claims, "P112"),
            "country": _extract_claim_value(claims, "P17"),
        }

    except Exception as e:
        print(f"Wikidata查询失败: {e}")
        return {"company_name": company_name, "found": False, "error": str(e)}

def _extract_claim_value(claims: dict, property_id: str) -> Optional[str]:
    """从claims中提取属性值"""
    claim_list = claims.get(property_id, [])
    if not claim_list:
        return None

    try:
        mainsnak = claim_list[0].get("mainsnak", {})
        datavalue = mainsnak.get("datavalue", {})
        value = datavalue.get("value", {})

        # 处理不同类型的价值
        if isinstance(value, dict):
            return value.get("id") or value.get("text") or value.get("time")
        return str(value)
    except Exception:
        return None
