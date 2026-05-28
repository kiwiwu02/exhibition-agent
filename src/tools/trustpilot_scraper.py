"""Trustpilot 公司评价查询工具"""
import logging
import re
from typing import Dict, Any, List

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TRUSTPILOT_SEARCH_URL = "https://www.google.com/search"
TRUSTPILOT_COMPANY_URL = "https://www.trustpilot.com/review"


def search_company_reviews(
    company_name: str,
    domain: str = "",
    limit: int = 5,
) -> Dict[str, Any]:
    """搜索公司在 Trustpilot 上的评价

    Args:
        company_name: 公司名称
        domain: 可选，公司域名（用于精确匹配）
        limit: 最大返回数量

    Returns:
        评价信息字典
    """
    if not company_name or not company_name.strip():
        return {"error": "Company name is required", "reviews": []}

    query = f'"{company_name.strip()}" site:trustpilot.com/review'
    if domain:
        query += f" {domain}"

    try:
        results = _search_google(query, limit)
        reviews = []
        for r in results:
            url = r.get("url", "")
            if "trustpilot.com/review/" in url:
                company_slug = url.split("trustpilot.com/review/")[-1].split("?")[0]
                rating = _extract_rating(r.get("description", ""))
                reviews.append({
                    "company_name": company_name,
                    "company_slug": company_slug,
                    "url": url,
                    "rating": rating,
                    "description": r.get("description", ""),
                    "source": "Trustpilot",
                })

        logger.info(f"Trustpilot search for '{company_name}': found {len(reviews)} results")
        return {"reviews": reviews}

    except Exception as e:
        logger.warning(f"Trustpilot search failed for '{company_name}': {e}")
        return {"error": str(e), "reviews": []}


def get_company_rating(company_slug: str) -> Dict[str, Any]:
    """获取公司在 Trustpilot 上的评分详情

    Args:
        company_slug: Trustpilot 公司标识符（如 'example.com'）

    Returns:
        评分详情字典
    """
    if not company_slug or not company_slug.strip():
        return {"error": "Company slug is required"}

    url = f"{TRUSTPILOT_COMPANY_URL}/{company_slug.strip()}"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        rating = _parse_page_rating(soup)
        review_count = _parse_review_count(soup)
        star_distribution = _parse_star_distribution(soup)
        trust_score = _parse_trust_score(soup)

        return {
            "company_slug": company_slug,
            "rating": rating,
            "review_count": review_count,
            "star_distribution": star_distribution,
            "trust_score": trust_score,
            "url": url,
            "source": "Trustpilot",
        }

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.info(f"Trustpilot page not found for '{company_slug}'")
            return {"company_slug": company_slug, "rating": None, "error": "Not found"}
        logger.warning(f"Trustpilot fetch failed for '{company_slug}': {e}")
        return {"error": str(e), "company_slug": company_slug}
    except Exception as e:
        logger.warning(f"Trustpilot fetch failed for '{company_slug}': {e}")
        return {"error": str(e), "company_slug": company_slug}


def _search_google(query: str, limit: int = 5) -> List[Dict[str, str]]:
    """使用 Google 搜索获取结果"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    params = {"q": query, "num": limit}

    with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
        response = client.get(TRUSTPILOT_SEARCH_URL, params=params)
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


def _extract_rating(description: str) -> float | None:
    """从搜索结果描述中提取评分"""
    patterns = [
        r"(\d+\.?\d*)\s*(?:out of|/)\s*5",
        r"rated\s+(\d+\.?\d*)",
        r"Rating:\s*(\d+\.?\d*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            try:
                rating = float(match.group(1))
                if 0 <= rating <= 5:
                    return rating
            except ValueError:
                continue
    return None


def _parse_page_rating(soup: BeautifulSoup) -> float | None:
    """从 Trustpilot 页面解析评分"""
    rating_el = soup.select_one("p.typography_heading-xl__T28xz")
    if rating_el:
        match = re.search(r"(\d+\.?\d*)", rating_el.get_text())
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
    return None


def _parse_review_count(soup: BeautifulSoup) -> int | None:
    """从 Trustpilot 页面解析评价数量"""
    count_el = soup.select_one("p.typography_body-l__KUYFJ")
    if count_el:
        text = count_el.get_text()
        match = re.search(r"([\d,]+)\s*(?:reviews?|total)", text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


def _parse_star_distribution(soup: BeautifulSoup) -> Dict[str, int]:
    """解析评分分布"""
    distribution = {}
    bars = soup.select("div.styles_reviewsContainer__3_GQw")
    for bar in bars:
        star_el = bar.select_one("span.typography_body-m__xgxZ_")
        count_el = bar.select_one("span.typography_body-m__xgxZ_")
        if star_el and count_el:
            star_text = star_el.get_text(strip=True)
            count_text = count_el.get_text(strip=True)
            match_count = re.search(r"([\d,]+)", count_text)
            if match_count:
                try:
                    distribution[star_text] = int(match_count.group(1).replace(",", ""))
                except ValueError:
                    pass
    return distribution


def _parse_trust_score(soup: BeautifulSoup) -> float | None:
    """解析 TrustScore"""
    score_el = soup.select_one("div.styles_fractionalValue__35WbH")
    if score_el:
        match = re.search(r"(\d+\.?\d*)", score_el.get_text())
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
    return None
