"""Google Maps 地址查询工具"""
import logging
import os
from typing import Dict, Any

import httpx

logger = logging.getLogger(__name__)

GOOGLE_MAPS_API = "https://maps.googleapis.com/maps/api/geocode/json"


def get_address_info(
    address: str,
    api_key: str = None,
) -> Dict[str, Any]:
    """查询地址信息

    Args:
        address: 地址字符串
        api_key: Google Maps API 密钥（可选，从环境变量读取）

    Returns:
        地址信息字典
    """
    if not address or not address.strip():
        return {"error": "Address is required", "address": ""}

    api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        logger.warning("Google Maps API key not configured, using fallback")
        return _fallback_address_info(address)

    try:
        params = {
            "address": address.strip(),
            "key": api_key,
        }

        with httpx.Client(timeout=30) as client:
            response = client.get(GOOGLE_MAPS_API, params=params)
            response.raise_for_status()

        data = response.json()
        status = data.get("status", "")

        if status != "OK" or not data.get("results"):
            logger.warning(f"Google Maps geocoding failed: {status}")
            return {"error": f"Geocoding failed: {status}", "address": address}

        result = data["results"][0]
        components = {
            comp["types"][0]: comp["long_name"]
            for comp in result.get("address_components", [])
            if comp.get("types")
        }

        location = result.get("geometry", {}).get("location", {})

        return {
            "status": "OK",
            "address": result.get("formatted_address", address),
            "city": components.get("locality", ""),
            "state": components.get("administrative_area_level_1", ""),
            "country": components.get("country", ""),
            "postal_code": components.get("postal_code", ""),
            "lat": location.get("lat"),
            "lng": location.get("lng"),
            "source": "Google Maps",
        }

    except Exception as e:
        logger.warning(f"Google Maps geocoding failed: {e}")
        return _fallback_address_info(address)


def _fallback_address_info(address: str) -> Dict[str, Any]:
    """无 API 密钥时的回退处理"""
    # 简单解析地址
    parts = [p.strip() for p in address.split(",")]
    return {
        "status": "fallback",
        "address": address,
        "city": parts[-3] if len(parts) >= 3 else "",
        "state": parts[-2] if len(parts) >= 2 else "",
        "country": parts[-1] if parts else "",
        "postal_code": "",
        "lat": None,
        "lng": None,
        "source": "fallback_parsing",
    }
