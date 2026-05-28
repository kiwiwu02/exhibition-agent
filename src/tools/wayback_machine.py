"""Wayback Machine 网站历史快照查询工具"""
import logging
from typing import List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

WAYBACK_API = "https://web.archive.org/cdx/search/cdx"


def get_wayback_snapshots(
    domain: str,
    years: int = 3,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """获取网站的历史快照列表

    Args:
        domain: 域名，如 example.com
        years: 查询近几年的历史
        limit: 最大返回数量

    Returns:
        快照列表，每个快照包含 timestamp, statuscode, original, url 等字段
    """
    try:
        from datetime import datetime, timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)

        params = {
            "url": domain,
            "output": "json",
            "fl": "timestamp,statuscode,original,mimetype",
            "from": start_date.strftime("%Y%m%d"),
            "to": end_date.strftime("%Y%m%d"),
            "limit": limit,
            "collapse": "timestamp:8",  # 按年折叠，避免过多重复
        }

        with httpx.Client(timeout=30) as client:
            response = client.get(WAYBACK_API, params=params)
            response.raise_for_status()

        data = response.json()

        # 第一行是字段名，后续是数据
        if len(data) < 2:
            logger.info(f"No Wayback snapshots found for {domain}")
            return []

        headers = data[0]
        snapshots = []
        for row in data[1:]:
            snapshot = dict(zip(headers, row))
            # 构造可访问的 URL
            snapshot["url"] = f"https://web.archive.org/web/{snapshot['timestamp']}/{snapshot['original']}"
            snapshots.append(snapshot)

        logger.info(f"Found {len(snapshots)} Wayback snapshots for {domain}")
        return snapshots

    except Exception as e:
        logger.warning(f"Wayback Machine query failed for {domain}: {e}")
        return []


def get_snapshot_content(url: str, max_chars: int = 2000) -> str:
    """获取指定快照的内容

    Args:
        url: 快照 URL
        max_chars: 最大字符数

    Returns:
        快照内容文本
    """
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        # 简单提取文本内容
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")

        # 移除 script 和 style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        return text[:max_chars]

    except Exception as e:
        logger.warning(f"Failed to get Wayback snapshot content: {e}")
        return ""
