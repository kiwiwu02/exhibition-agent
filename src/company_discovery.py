"""公司名自动发现模块 - 当 OCR 未能提取公司名时，通过其他字段推断"""
import logging
import re
from urllib.parse import urlparse
from typing import Tuple

from .models import BusinessCard

logger = logging.getLogger(__name__)

# 公共邮箱域名，不能用于推断公司
FREE_EMAIL_DOMAINS = {
    "gmail.com", "qq.com", "163.com", "126.com", "sina.com",
    "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "foxmail.com", "yeah.net", "sohu.com", "aliyun.com",
    "live.com", "msn.com", "aol.com", "protonmail.com",
}

# WHOIS 隐私保护关键词
WHOIS_PRIVACY_KEYWORDS = [
    "redacted", "privacy", "whoisguard", "dataguard",
    "contactprivacy", "domainsbyproxy", "perfectprivacy",
    "withheld", "private registration",
]


def discover_company_name(card: BusinessCard) -> Tuple[str, str, str]:
    """自动发现公司名

    按优先级依次尝试 5 种策略：
    1. website 域名 WHOIS
    2. email 域名 WHOIS
    3. 网页爬取 + LLM 提取
    4. LinkedIn 人名搜索
    5. DuckDuckGo/Tavily 搜索

    Returns:
        (company_name, company_name_en, source_strategy)
    """
    # 已有公司名，无需发现
    if card.company_name or card.company_name_en:
        return ("", "", "")

    # 策略 1: website 域名 WHOIS
    if card.website:
        domain = _extract_domain(card.website)
        if domain:
            cn, cn_en = _whois_strategy(domain)
            if cn or cn_en:
                logger.info(f"策略1 WHOIS(website) 发现: {cn or cn_en}")
                return (cn, cn_en, "whois_website")

    # 策略 2: email 域名 WHOIS
    if card.email:
        email_domain = _extract_email_domain(card.email)
        if email_domain and email_domain not in FREE_EMAIL_DOMAINS:
            cn, cn_en = _whois_strategy(email_domain)
            if cn or cn_en:
                logger.info(f"策略2 WHOIS(email) 发现: {cn or cn_en}")
                return (cn, cn_en, "whois_email")

    # 策略 3: 网页爬取 + LLM
    website_url = card.website
    if not website_url and card.email:
        email_domain = _extract_email_domain(card.email)
        if email_domain and email_domain not in FREE_EMAIL_DOMAINS:
            website_url = f"https://{email_domain}"

    if website_url:
        cn, cn_en = _webpage_strategy(website_url)
        if cn:
            logger.info(f"策略3 网页爬取 发现: {cn}")
            return (cn, cn_en, "webpage_crawl")

    # 策略 4: LinkedIn 人名搜索
    if card.contact_name:
        cn, cn_en = _linkedin_people_strategy(card.contact_name, card.position)
        if cn or cn_en:
            logger.info(f"策略4 LinkedIn人名 发现: {cn or cn_en}")
            return (cn, cn_en, "linkedin_people")

    # 策略 5: DuckDuckGo/Tavily 搜索
    cn, cn_en = _search_strategy(card)
    if cn or cn_en:
        logger.info(f"策略5 搜索引擎 发现: {cn or cn_en}")
        return (cn, cn_en, "search_engine")

    logger.info("所有策略均未能发现公司名")
    return ("", "", "")


def _extract_domain(url_or_domain: str) -> str:
    """从 URL 或域名字符串中提取纯净域名"""
    if not url_or_domain:
        return ""
    url_or_domain = url_or_domain.strip()
    if not url_or_domain.startswith("http"):
        url_or_domain = "https://" + url_or_domain
    try:
        parsed = urlparse(url_or_domain)
        domain = parsed.netloc or parsed.path
        domain = domain.split(":")[0]  # 去掉端口
        domain = domain.lstrip("www.")
        return domain
    except Exception:
        return ""


def _extract_email_domain(email: str) -> str:
    """从邮箱地址中提取域名"""
    if not email or "@" not in email:
        return ""
    return email.split("@")[-1].strip().lower()


def _whois_strategy(domain: str) -> Tuple[str, str]:
    """通过 WHOIS 查询域名注册组织名"""
    try:
        from .tools.whois_lookup import lookup_whois
        result = lookup_whois(domain)

        if "error" in result:
            return ("", "")

        org = result.get("org")
        if not org or not isinstance(org, str):
            # org 可能是列表
            if isinstance(org, list) and org:
                org = org[0]
            else:
                return ("", "")

        org = org.strip()
        if len(org) < 3:
            return ("", "")

        # 检查隐私保护
        org_lower = org.lower()
        if any(kw in org_lower for kw in WHOIS_PRIVACY_KEYWORDS):
            return ("", "")

        # 通常 WHOIS org 返回英文公司名
        return ("", org)

    except Exception as e:
        logger.warning(f"WHOIS 策略失败 ({domain}): {e}")
        return ("", "")


def _webpage_strategy(url: str) -> Tuple[str, str]:
    """爬取网页并用 LLM 提取公司名"""
    try:
        import httpx
        from bs4 import BeautifulSoup

        # 先尝试抓取首页
        domain = _extract_domain(url)
        if not domain:
            return ("", "")

        homepage = f"https://{domain}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        }

        with httpx.Client(timeout=10, headers=headers, follow_redirects=True) as client:
            resp = client.get(homepage)
            if resp.status_code != 200:
                return ("", "")

        soup = BeautifulSoup(resp.text, "html.parser")

        # 提取 title
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

        # 提取 meta description
        desc = ""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            desc = meta.get("content", "")

        # 提取 og:site_name
        site_name = ""
        og = soup.find("meta", attrs={"property": "og:site_name"})
        if og:
            site_name = og.get("content", "")

        # 组合信息给 LLM
        info = f"Title: {title}\nDescription: {desc}\nSite Name: {site_name}"
        if not info.strip():
            return ("", "")

        return _llm_extract_company_name(info)

    except Exception as e:
        logger.warning(f"网页爬取策略失败 ({url}): {e}")
        return ("", "")


def _linkedin_people_strategy(contact_name: str, position: str = "") -> Tuple[str, str]:
    """通过 LinkedIn 搜索人名，从结果中提取公司名"""
    try:
        from .tools.linkedin_scraper import search_people
        result = search_people(contact_name, limit=3)

        people = result.get("people", [])
        for person in people:
            desc = person.get("description", "")
            title = person.get("title", "")

            # 从描述中提取公司名：通常是 "Name - Company - Title" 格式
            company = _extract_company_from_linkedin_desc(desc, title)
            if company:
                return ("", company)

        return ("", "")

    except Exception as e:
        logger.warning(f"LinkedIn 人名搜索策略失败 ({contact_name}): {e}")
        return ("", "")


def _extract_company_from_linkedin_desc(description: str, title: str) -> str:
    """从 LinkedIn 搜索结果描述中提取公司名"""
    # 描述格式通常是: "Name · Title at Company · Location"
    # 或: "Name - Company - Title"
    text = f"{title} {description}"

    # 尝试 "at Company" 模式
    match = re.search(r'at\s+([A-Z][\w\s&.,]+?)(?:\s*[·•|\-]|$)', text)
    if match:
        company = match.group(1).strip()
        if len(company) > 2 and len(company) < 80:
            return company

    # 尝试 "Company - Title" 模式
    parts = re.split(r'\s*[·•|\-]\s*', text)
    if len(parts) >= 2:
        # 第二部分通常是公司或职位
        for part in parts[1:3]:
            part = part.strip()
            if part and not any(kw in part.lower() for kw in ["engineer", "manager", "director", "ceo", "cto", "vp"]):
                if len(part) > 2 and len(part) < 80:
                    return part

    return ""


def _search_strategy(card: BusinessCard) -> Tuple[str, str]:
    """通过搜索引擎搜索公司名"""
    try:
        from .tools.deep_search import deep_search

        # 构造搜索查询
        queries = []
        if card.contact_name:
            queries.append(f'"{card.contact_name}" company')
            if card.position:
                queries.append(f'"{card.contact_name}" "{card.position}" company')
        if card.phone:
            queries.append(f'"{card.phone}" company')
        if card.address:
            queries.append(f'"{card.address}" company')

        if not queries:
            return ("", "")

        content, _ = deep_search(
            queries[:3],
            max_results_per_query=3,
            crawl_top_n=2,
            max_content_length=5000,
        )

        if not content:
            return ("", "")

        return _llm_extract_company_name(content)

    except Exception as e:
        logger.warning(f"搜索策略失败: {e}")
        return ("", "")


def _llm_extract_company_name(text: str) -> Tuple[str, str]:
    """用 LLM 从文本中提取公司名"""
    try:
        from openai import OpenAI
        from .config import config

        client = OpenAI(
            api_key=config.mimo.api_key,
            base_url=config.mimo.api_base
        )

        prompt = f"""从以下文本中提取公司名称。

文本内容：
{text[:3000]}

请返回JSON格式：
{{
  "company_name": "公司名称（保留原始语言，不要翻译）",
  "company_name_en": "公司英文名称（如有）"
}}

注意：
1. 只返回JSON，不要其他内容
2. 如果无法确定公司名，两个字段都返回空字符串 ""
3. 优先提取正式的公司全称
4. 保留原始语言，不要将英文公司名翻译成中文"""

        response = client.chat.completions.create(
            model=config.mimo.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.1,
        )

        result_text = response.choices[0].message.content
        import json
        match = re.search(r'\{[\s\S]*\}', result_text)
        if match:
            data = json.loads(match.group())
            cn = data.get("company_name", "").strip()
            cn_en = data.get("company_name_en", "").strip()
            if cn or cn_en:
                return (cn, cn_en)

        return ("", "")

    except Exception as e:
        logger.warning(f"LLM 提取公司名失败: {e}")
        return ("", "")
