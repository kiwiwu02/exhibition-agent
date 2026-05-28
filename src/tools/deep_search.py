"""深度搜索模块 - 多轮迭代搜索"""
import logging
import re
from typing import Dict, Any, List, Tuple
from .duckduckgo_search import ddgs_search

logger = logging.getLogger(__name__)


def _clean_content(text: str) -> str:
    """清理网页内容：移除 HTML 标签、CSS、JS、导航栏等噪音"""
    if not text:
        return ""
    # 移除 script 和 style 标签及其内容
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 解码常见 HTML 实体
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    # 清理多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    # 移除常见的导航/页脚噪音（精确匹配短语，不用 .*? 避免过度匹配）
    noise_phrases = [
        'Get directions', 'My saved places', 'Send feedback',
        'Learn more about our mobile apps', 'Enterprise solutions',
        'Claim your business', 'Developer resources',
        'Advertise with us', 'Terms of use', 'Privacy policy',
        'Data and licenses', 'About our ads', 'Do not sell',
    ]
    for phrase in noise_phrases:
        text = text.replace(phrase, '')
    # 移除版权行
    text = re.sub(r'©\d{4}[^.]*\.', '', text)
    # 移除 Advertisement 标记
    text = re.sub(r'\bAdvertisement\b', '', text, flags=re.IGNORECASE)
    # 移除嵌套 markdown 图片链接
    text = re.sub(r'\[!?\[.*?\]\(.*?\)\]\(.*?\)', '', text)
    # 清理多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _is_relevant_result(result: Dict, company_name: str) -> bool:
    """判断搜索结果是否与目标公司相关

    通过检查标题和URL是否包含公司名关键词来判断相关性。
    """
    if not company_name:
        return True

    title = result.get("title", "").lower()
    href = result.get("href", "").lower()
    body = result.get("body", "").lower()

    # 提取公司名关键词（去掉停用词）
    company_lower = company_name.lower()
    keywords = [w for w in company_lower.split() if len(w) > 2]

    # 如果标题或URL包含公司名全称，直接通过
    if company_lower in title or company_lower in href:
        return True

    # 如果标题或URL包含大部分关键词（>=60%），也通过
    if keywords:
        match_count = sum(1 for kw in keywords if kw in title or kw in href)
        if match_count >= len(keywords) * 0.6:
            return True

    # 如果 body 包含公司名，通过
    if company_lower in body:
        return True

    return False


def _filter_by_relevance(results: List[Dict], company_name: str) -> List[Dict]:
    """按相关性过滤搜索结果，优先保留与目标公司匹配的结果"""
    if not company_name:
        return results

    relevant = [r for r in results if _is_relevant_result(r, company_name)]
    irrelevant_count = len(results) - len(relevant)

    if irrelevant_count > 0:
        logger.info(f"过滤了 {irrelevant_count} 条与 '{company_name}' 无关的搜索结果")

    # 如果过滤后结果太少（<2条），放宽条件返回原始结果
    if len(relevant) < 2:
        logger.info(f"相关结果不足2条，返回全部 {len(results)} 条结果")
        return results

    return relevant


class SourceIndex:
    """来源索引管理器 - 确保引用准确可追溯"""

    def __init__(self):
        self.sources: List[Dict[str, Any]] = []
        self.url_to_index: Dict[str, int] = {}

    def add_source(self, url: str, title: str = "", content: str = "", category: str = "") -> int:
        """添加来源，返回序号"""
        if not url:
            return -1

        # 如果已存在，返回现有序号
        if url in self.url_to_index:
            return self.url_to_index[url]

        index = len(self.sources) + 1
        cleaned = _clean_content(content)
        self.sources.append({
            "index": index,
            "url": url,
            "title": title,
            "content": cleaned[:10000],
            "content_preview": cleaned[:500] if cleaned else "",
            "category": category,
        })
        self.url_to_index[url] = index
        return index

    def get_source(self, index: int) -> Dict[str, Any]:
        """获取指定序号的来源"""
        if 1 <= index <= len(self.sources):
            return self.sources[index - 1]
        return {}

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """获取所有来源"""
        return self.sources

    def get_citation(self, index: int) -> str:
        """获取引用标记"""
        source = self.get_source(index)
        if source:
            return f"[{index}]"
        return ""

    def verify_citation(self, index: int, claimed_info: str) -> bool:
        """验证引用是否准确 - 检查来源内容是否包含声称的信息"""
        source = self.get_source(index)
        if not source:
            return False

        content = source.get("content", "").lower()
        # 简单验证：检查关键信息是否出现在来源内容中
        keywords = claimed_info.lower().split()
        match_count = sum(1 for kw in keywords if kw in content)
        return match_count >= len(keywords) * 0.3  # 30% 关键词匹配


def deep_search(
    queries: List[str],
    max_results_per_query: int = 5,
    crawl_top_n: int = 5,
    max_content_length: int = 50000,
    category: str = "",
    company_name: str = "",
) -> Tuple[str, SourceIndex]:
    """深度搜索 - 多轮查询 + 网页爬取

    Args:
        queries: 搜索查询列表（多轮）
        max_results_per_query: 每个查询最大结果数
        crawl_top_n: 爬取前N个最相关结果
        max_content_length: 每页最大内容长度
        category: 来源分类标签
        company_name: 目标公司名（用于相关性过滤）

    Returns:
        (合并后的内容摘要, 来源索引)
    """
    source_index = SourceIndex()
    all_results = []

    # 第一轮：执行所有查询
    for query in queries:
        try:
            results = ddgs_search(query, max_results=max_results_per_query)
            all_results.extend(results)
        except Exception as e:
            logger.warning(f"Search failed for query '{query}': {e}")

    # 去重（按URL）
    seen_urls = set()
    unique_results = []
    for r in all_results:
        url = r.get("href", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(r)

    # 按相关性过滤（如果提供了公司名）
    if company_name:
        unique_results = _filter_by_relevance(unique_results, company_name)

    # 第二轮：获取前N个结果的详细内容（优先用raw_content，无需爬虫）
    crawled_contents = []
    for r in unique_results[:crawl_top_n]:
        url = r.get("href", "")
        title = r.get("title", "")
        body = r.get("body", "")
        raw_content = r.get("raw_content", "")

        if not url:
            continue

        # 优先用Tavily返回的全文内容，其次用摘要，清理后使用
        raw = raw_content if raw_content else (body or "")
        content = _clean_content(raw)

        # 添加到来源索引
        index = source_index.add_source(url, title, content, category)

        if content:
            crawled_contents.append({
                "index": index,
                "title": title,
                "url": url,
                "content": content,
            })

    # 第三轮：基于已有内容生成补充查询
    if crawled_contents:
        supplemental_queries = _generate_supplemental_queries(crawled_contents)
        for query in supplemental_queries[:2]:  # 只取前2个补充查询
            try:
                results = ddgs_search(query, max_results=3)
                for r in results[:2]:
                    url = r.get("href", "")
                    title = r.get("title", "")
                    body = r.get("body", "")
                    raw_content = r.get("raw_content", "")
                    if url and url not in source_index.url_to_index:
                        raw = raw_content if raw_content else (body or "")
                        content = _clean_content(raw)
                        source_index.add_source(url, title, content, category)
                        if content:
                            crawled_contents.append({
                                "index": source_index.url_to_index[url],
                                "title": title,
                                "url": url,
                                "content": content,
                            })
            except Exception as e:
                logger.warning(f"Supplemental search failed: {e}")

    # 合并所有内容
    summary = _merge_contents(crawled_contents)

    return summary, source_index


def _generate_supplemental_queries(crawled_contents: List[Dict]) -> List[str]:
    """基于已爬取内容生成补充查询"""
    queries = []

    for item in crawled_contents[:3]:
        content = item.get("content", "")
        # 提取可能的公司名、人名等实体
        lines = content.split("\n")
        for line in lines[:10]:
            # 查找包含关键信息的行
            if any(kw in line.lower() for kw in ["ceo", "founded", "headquarters", "revenue", "employees"]):
                # 提取关键词生成新查询
                words = line.split()[:5]
                if len(words) >= 3:
                    queries.append(" ".join(words))

    return queries[:3]


def _merge_contents(crawled_contents: List[Dict]) -> str:
    """合并爬取的内容 - 清理后保留"""
    if not crawled_contents:
        return ""

    sections = []
    for item in crawled_contents:
        index = item.get("index", 0)
        title = item.get("title", "")
        content = _clean_content(item.get("content", ""))

        if content:
            preview = content[:5000] if len(content) > 5000 else content
            sections.append(f"[{index}] **{title}**\n{preview}")

    return "\n\n".join(sections)


def search_company_deep(
    company_name: str,
    country: str = "",
    contact_name: str = "",
) -> Tuple[str, SourceIndex]:
    """公司深度搜索 - 多维度、多轮搜索

    Args:
        company_name: 公司名称
        country: 国家
        contact_name: 联系人姓名

    Returns:
        (合并后的内容摘要, 来源索引)
    """
    queries = []

    # 基础信息查询
    queries.append(f'"{company_name}" official website about us')
    queries.append(f'"{company_name}" {country} company profile')

    # 公司规模和业务
    queries.append(f'"{company_name}" revenue employees size')
    queries.append(f'"{company_name}" products services industry')

    # 联系人和组织
    if contact_name:
        queries.append(f'"{contact_name}" "{company_name}" LinkedIn')
    queries.append(f'"{company_name}" CEO management team')

    # 信用和评价
    queries.append(f'"{company_name}" reviews reputation')
    queries.append(f'"{company_name}" supplier customer partner')

    return deep_search(
        queries=queries,
        max_results_per_query=5,
        crawl_top_n=8,
        max_content_length=50000,
        category="company_research",
        company_name=company_name,
    )


def search_person_deep(
    person_name: str,
    company_name: str = "",
) -> Tuple[str, SourceIndex]:
    """人员深度搜索"""
    queries = []

    queries.append(f'"{person_name}" LinkedIn profile')
    if company_name:
        queries.append(f'"{person_name}" "{company_name}"')
    queries.append(f'"{person_name}" CEO OR manager OR director')

    return deep_search(
        queries=queries,
        max_results_per_query=5,
        crawl_top_n=5,
        max_content_length=50000,
        category="person_research",
    )
