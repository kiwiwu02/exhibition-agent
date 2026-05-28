# src/tools/web_crawler.py
"""
网页爬取工具 - 使用 crawl4ai + Scrapling 进行深度爬取
"""
import asyncio
import httpx
from typing import Optional


def _crawl4ai_fetch(url: str, max_length: int = 100000) -> str:
    """使用 crawl4ai 爬取网页（LLM友好markdown输出）"""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        browser_config = BrowserConfig(
            headless=True,
            browser_type="chromium"
        )

        crawler_config = CrawlerRunConfig(
            word_count_threshold=10,
            exclude_external_links=True
        )

        # 检查是否有正在运行的事件循环
        try:
            loop = asyncio.get_running_loop()
            # 如果有正在运行的事件循环，使用同步方式
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    asyncio.run,
                    _async_crawl4ai(url, browser_config, crawler_config, max_length)
                ).result(timeout=30)
                return result
        except RuntimeError:
            # 没有正在运行的事件循环，直接使用asyncio.run
            result = asyncio.run(
                _async_crawl4ai(url, browser_config, crawler_config, max_length)
            )
            return result

    except Exception as e:
        print(f"crawl4ai 爬取失败 {url}: {e}")
        return ""


async def _async_crawl4ai(url: str, browser_config, crawler_config, max_length: int) -> str:
    """异步crawl4ai爬取"""
    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(
                url=url,
                config=crawler_config
            )

            if result.success and result.markdown:
                content = result.markdown
                # 仅在内容极长时截断，保留完整内容用于分析
                if max_length and len(content) > max_length:
                    content = content[:max_length]
                return content

            return ""
    except Exception as e:
        print(f"crawl4ai 异步爬取失败 {url}: {e}")
        return ""


def _scrapling_fetch(url: str, max_length: int = 100000) -> str:
    """使用 Scrapling StealthyFetcher 爬取反爬网站"""
    try:
        from scrapling.fetchers import StealthyFetcher

        # 使用异步方式避免事件循环冲突
        try:
            loop = asyncio.get_running_loop()
            # 如果有正在运行的事件循环，使用线程池
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    _sync_scrapling_fetch, url, max_length
                ).result(timeout=30)
                return result
        except RuntimeError:
            # 没有正在运行的事件循环，直接同步调用
            return _sync_scrapling_fetch(url, max_length)

    except Exception as e:
        print(f"Scrapling 爬取失败 {url}: {e}")
        return ""


def _sync_scrapling_fetch(url: str, max_length: int) -> str:
    """同步Scrapling爬取"""
    try:
        from scrapling.fetchers import StealthyFetcher

        page = StealthyFetcher.fetch(url, headless=True, network_idle=True)

        if page and page.text:
            content = page.text
            if max_length and len(content) > max_length:
                content = content[:max_length]
            return content

        return ""
    except Exception as e:
        print(f"Scrapling 同步爬取失败 {url}: {e}")
        return ""


def _httpx_fetch(url: str, max_length: int = 100000) -> str:
    """使用 httpx 爬取普通网站（最终回退方案）"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

        response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        response.raise_for_status()

        html = response.text
        text = _extract_text_from_html(html)

        if max_length and len(text) > max_length:
            text = text[:max_length]

        return text
    except Exception as e:
        print(f"httpx 爬取失败 {url}: {e}")
        return ""


def _extract_text_from_html(html: str) -> str:
    """从HTML中提取纯文本（用于httpx回退）"""
    import re

    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL)
    html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL)
    html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL)
    html = re.sub(r'<aside[^>]*>.*?</aside>', '', html, flags=re.DOTALL)

    text = re.sub(r'<[^>]+>', ' ', html)

    text = re.sub(r'\s+', ' ', text).strip()

    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")

    return text


def _clean_web_content(text: str) -> str:
    """清理网页爬取内容 - 移除导航、图片、噪音元素"""
    import re
    if not text:
        return ""

    # 移除 markdown 图片引用 ![...](...)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # 移除 HTML 图片标签
    text = re.sub(r'<img[^>]*>', '', text)
    # 移除导航链接行（通常是连续的短链接）
    text = re.sub(r'^\s*\[.*?\]\(.*?\)\s*[|·•]\s*\[.*?\]\(.*?\)', '', text, flags=re.MULTILINE)
    # 移除 "Sign In"、"Login"、"Get Started" 等导航文本
    nav_patterns = [
        r'\[Sign In\].*',
        r'\[Login\].*',
        r'\[Get .*? →\].*',
        r'\[Search\].*',
        r'\[View (?:Map|Post|Profile)\].*',
        r'\[Apply Now\].*',
        r'\[Contact Us\].*',
    ]
    for pat in nav_patterns:
        text = re.sub(pat, '', text, flags=re.IGNORECASE)
    # 移除连续的空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 移除 HTML 实体残留
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    # 移除 CSS/JS 残留
    text = re.sub(r'\{[^}]{0,200}\}', '', text)
    # 限制长度
    if len(text) > 15000:
        text = text[:15000]
    return text.strip()


def fetch_web_content(url: str, max_length: int = 100000) -> str:
    """爬取网页内容 - 使用多层回退策略

    Args:
        url: 网页URL
        max_length: 最大文本长度（默认100K字符，尽可能获取完整内容）

    Returns:
        爬取的markdown格式内容
    """
    if not url:
        return ""

    if not url.startswith(('http://', 'https://')):
        return ""

    # 1. 尝试 crawl4ai（LLM友好markdown输出）
    content = _crawl4ai_fetch(url, max_length)
    if content:
        return _clean_web_content(content)

    # 2. 尝试 Scrapling（反爬绕过）
    content = _scrapling_fetch(url, max_length)
    if content:
        return _clean_web_content(content)

    # 3. 回退到 httpx
    content = _httpx_fetch(url, max_length)
    return _clean_web_content(content)


def crawl_and_extract(urls: list, max_length_per_page: int = 50000) -> tuple:
    """批量爬取多个网页并合并内容

    Args:
        urls: URL列表
        max_length_per_page: 每页最大文本长度

    Returns:
        tuple: (合并后的内容, source_content_map)
            - 合并后的markdown格式内容（带序号引用）
            - source_content_map: dict mapping URL to content summary
    """
    contents = []
    sources = []
    source_content_map = {}

    for i, url in enumerate(urls[:5], 1):
        if not url.startswith(('http://', 'https://')):
            continue

        content = fetch_web_content(url, max_length_per_page)
        if content:
            sources.append(url)
            contents.append(f"[{i}] {content}")
            # 保存URL到内容摘要的映射（截取前2000字作为摘要）
            source_content_map[url] = content[:2000] + "..." if len(content) > 2000 else content

    if not contents:
        return "", {}

    # 添加参考来源列表
    source_list = "\n".join([f"[{i}] {url}" for i, url in enumerate(sources, 1)])
    return f"{chr(10).join(contents)}\n\n**参考来源：**\n{source_list}", source_content_map
