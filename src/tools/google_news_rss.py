import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict
from datetime import datetime, timedelta

def fetch_google_news(query: str, max_results: int = 10, months_back: int = 6) -> List[Dict]:
    """从Google News RSS获取新闻

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数
        months_back: 回溯月数

    Returns:
        新闻列表，每条包含title, link, published, source
    """
    try:
        # 构造RSS URL
        encoded_query = query.replace(" ", "+")
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en"

        # 获取RSS内容
        response = httpx.get(rss_url, timeout=15)
        response.raise_for_status()

        # 解析XML
        root = ET.fromstring(response.text)

        # 计算时间 cutoff
        cutoff_date = datetime.now() - timedelta(days=months_back * 30)

        news_items = []
        for item in root.findall(".//item")[:max_results]:
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            source = item.find("source").text if item.find("source") is not None else ""

            # 解析发布日期
            try:
                pub_datetime = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                if pub_datetime < cutoff_date:
                    continue
            except:
                pass

            news_items.append({
                "title": title,
                "link": link,
                "published": pub_date,
                "source": source
            })

        return news_items

    except Exception as e:
        print(f"Google News RSS获取失败: {e}")
        return []
