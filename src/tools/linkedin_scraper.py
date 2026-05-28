"""LinkedIn 公司与人员信息查询工具"""
import logging
import re
from typing import Dict, Any, List

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

LINKEDIN_SEARCH_URL = "https://www.google.com/search"


def search_company(
    company_name: str,
    location: str = "",
    limit: int = 5,
) -> Dict[str, Any]:
    """通过搜索引擎查找 LinkedIn 公司页面信息

    Args:
        company_name: 公司名称
        location: 可选，地点
        limit: 最大返回数量

    Returns:
        公司信息字典
    """
    if not company_name or not company_name.strip():
        return {"error": "Company name is required", "companies": []}

    query = f'"{company_name.strip()}" site:linkedin.com/company'
    if location:
        query += f" {location}"

    try:
        results = _search_google(query, limit)
        companies = []
        for r in results:
            if "/company/" in r.get("url", ""):
                companies.append({
                    "name": _extract_company_name(r.get("title", "")),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                    "source": "LinkedIn",
                })

        logger.info(f"LinkedIn search for '{company_name}': found {len(companies)} companies")
        return {"companies": companies}

    except Exception as e:
        logger.warning(f"LinkedIn search failed for '{company_name}': {e}")
        return {"error": str(e), "companies": []}


def search_people(
    person_name: str,
    company_name: str = "",
    limit: int = 5,
) -> Dict[str, Any]:
    """通过搜索引擎查找 LinkedIn 人员页面

    Args:
        person_name: 人名
        company_name: 可选，公司名称
        limit: 最大返回数量

    Returns:
        人员信息列表
    """
    if not person_name or not person_name.strip():
        return {"error": "Person name is required", "people": []}

    query = f'"{person_name.strip()}" site:linkedin.com/in'
    if company_name:
        query += f' "{company_name.strip()}"'

    try:
        results = _search_google(query, limit)
        people = []
        for r in results:
            if "/in/" in r.get("url", ""):
                people.append({
                    "name": _extract_person_name(r.get("title", "")),
                    "url": r.get("url", ""),
                    "title": _extract_job_title(r.get("description", "")),
                    "description": r.get("description", ""),
                    "source": "LinkedIn",
                })

        logger.info(f"LinkedIn people search for '{person_name}': found {len(people)} results")
        return {"people": people}

    except Exception as e:
        logger.warning(f"LinkedIn people search failed for '{person_name}': {e}")
        return {"error": str(e), "people": []}


def get_company_employees(company_name: str) -> Dict[str, Any]:
    """估算公司员工规模

    Args:
        company_name: 公司名称

    Returns:
        员工规模信息
    """
    if not company_name or not company_name.strip():
        return {"error": "Company name is required"}

    query = f'"{company_name.strip()}" site:linkedin.com/company employees'

    try:
        results = _search_google(query, 3)
        employee_count = None
        company_url = ""

        for r in results:
            desc = r.get("description", "")
            url = r.get("url", "")
            if "/company/" in url:
                company_url = url
                count = _parse_employee_count(desc)
                if count:
                    employee_count = count
                    break

        return {
            "company": company_name,
            "employee_count": employee_count,
            "linkedin_url": company_url,
            "source": "LinkedIn",
        }

    except Exception as e:
        logger.warning(f"LinkedIn employee count failed for '{company_name}': {e}")
        return {"error": str(e), "company": company_name}


def _search_google(query: str, limit: int = 5) -> List[Dict[str, str]]:
    """使用 Google 搜索获取结果"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    params = {"q": query, "num": limit}

    with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
        response = client.get(LINKEDIN_SEARCH_URL, params=params)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for g in soup.select("div.g"):
        title_el = g.select_one("h3")
        link_el = g.select_one("a")
        desc_el = g.select_one("div.VwiC3b") or g.select_one("span.aCOpRe")

        if title_el and link_el:
            results.append({
                "title": title_el.get_text(strip=True),
                "url": link_el.get("href", ""),
                "description": desc_el.get_text(strip=True) if desc_el else "",
            })

    return results[:limit]


def _extract_company_name(title: str) -> str:
    """从搜索标题中提取公司名"""
    parts = title.split(" - ")
    if len(parts) >= 2:
        return parts[0].strip()
    parts = title.split(" | ")
    if len(parts) >= 2:
        return parts[0].strip()
    return title.split("LinkedIn")[0].strip()


def _extract_person_name(title: str) -> str:
    """从搜索标题中提取人名"""
    parts = title.split(" - ")
    if len(parts) >= 2:
        return parts[0].strip()
    parts = title.split(" | ")
    if len(parts) >= 2:
        return parts[0].strip()
    return title.split("LinkedIn")[0].strip()


def _extract_job_title(description: str) -> str:
    """从描述中提取职位信息"""
    patterns = [
        r"(?:Title|Position|Role)[:\s]+([^\n|]+)",
        r"((?:CEO|CTO|CFO|COO|VP|Director|Manager|Engineer|Developer|Analyst)[^\n|]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:100]
    return ""


def _parse_employee_count(text: str) -> int | None:
    """从文本中解析员工数量"""
    patterns = [
        r"(\d[\d,]*)\s*(?:employees?|staff|people|members)",
        r"(\d[\d,]*)\s*(?:on LinkedIn|linkedin)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            count_str = match.group(1).replace(",", "")
            try:
                return int(count_str)
            except ValueError:
                continue
    return None
