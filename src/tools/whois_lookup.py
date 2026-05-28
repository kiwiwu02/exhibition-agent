"""WHOIS 域名查询工具"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def lookup_whois(domain: str) -> Dict[str, Any]:
    """查询域名 WHOIS 信息

    Args:
        domain: 域名，如 example.com

    Returns:
        包含域名信息的字典
    """
    try:
        import whois
        w = whois.whois(domain)

        result = {
            "domain": domain,
            "registrar": getattr(w, "registrar", None),
            "creation_date": _format_date(getattr(w, "creation_date", None)),
            "expiration_date": _format_date(getattr(w, "expiration_date", None)),
            "name_servers": getattr(w, "name_servers", []) or [],
            "org": getattr(w, "org", None),
            "country": getattr(w, "country", None),
            "state": getattr(w, "state", None),
            "city": getattr(w, "city", None),
            "address": getattr(w, "address", None),
        }

        # 计算域名年龄
        if result["creation_date"]:
            from datetime import datetime
            try:
                if isinstance(result["creation_date"], str):
                    created = datetime.strptime(result["creation_date"], "%Y-%m-%d")
                else:
                    created = result["creation_date"]
                age_years = (datetime.now() - created).days / 365.25
                result["age_years"] = round(age_years, 1)
            except Exception:
                result["age_years"] = None

        logger.info(f"WHOIS lookup for {domain}: registrar={result['registrar']}")
        return result

    except ImportError:
        logger.error("python-whois not installed. Run: pip install python-whois")
        return {"domain": domain, "error": "python-whois not installed"}
    except Exception as e:
        logger.warning(f"WHOIS lookup failed for {domain}: {e}")
        return {"domain": domain, "error": str(e)}


def _format_date(date) -> str:
    """格式化日期"""
    if date is None:
        return None
    if isinstance(date, list):
        date = date[0]
    if hasattr(date, "strftime"):
        return date.strftime("%Y-%m-%d")
    return str(date)
