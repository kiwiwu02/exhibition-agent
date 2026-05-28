from .base import BaseAgent
from ..models import BusinessCard, AgentResult
from ..tools.duckduckgo_search import ddgs_search
from ..tools.web_crawler import crawl_and_extract
from ..config import config

class PRExpertAgent(BaseAgent):
    """新闻与声誉专家Agent - 负责调研动态、新闻与口碑"""

    def __init__(self):
        super().__init__(name="pr_expert")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行新闻与声誉调研"""
        sources = []
        content_parts = []
        source_content_map = {}

        # 1. 搜索新闻 - 多维度
        news_queries = [
            f"{card.company_name} news latest",
            f"{card.company_name} {card.city} announcement",
        ]
        if card.contact_name:
            news_queries.append(f"{card.contact_name} {card.company_name} news")

        news_results = []
        for query in news_queries[:2]:
            results = ddgs_search(query, max_results=3)
            news_results.extend(results)

        if news_results:
            urls = [r.get('href', '') for r in news_results if r.get('href')]
            unique_urls = list(dict.fromkeys(urls))
            sources.extend(unique_urls[:3])
            crawled, crawled_map = crawl_and_extract(unique_urls[:3], max_length_per_page=50000)
            if crawled:
                # 使用LLM总结新闻内容
                summarized = self._summarize_content(crawled, "新闻动态")
                content_parts.append("**近期新闻**：")
                content_parts.append(summarized)
                source_content_map.update(crawled_map)
            else:
                content_parts.append("**近期新闻**：")
                for r in news_results[:3]:
                    content_parts.append(f"- {r.get('title', '')}: {r.get('body', '')[:100]}")

        # 2. 搜索口碑和评价 - 多维度
        reputation_queries = [
            f"{card.company_name} reviews reputation rating",
            f"{card.company_name} customer feedback",
        ]
        if card.website:
            domain = card.website.split('//')[-1].split('/')[0]
            reputation_queries.append(f"site:google.com/maps {domain}")

        reputation_results = []
        for query in reputation_queries[:2]:
            results = ddgs_search(query, max_results=3)
            reputation_results.extend(results)

        if reputation_results:
            urls = [r.get('href', '') for r in reputation_results if r.get('href')]
            unique_urls = list(dict.fromkeys(urls))
            sources.extend(unique_urls[:2])
            crawled, crawled_map = crawl_and_extract(unique_urls[:2], max_length_per_page=50000)
            if crawled:
                # 使用LLM总结口碑内容
                summarized = self._summarize_content(crawled, "口碑评价")
                content_parts.append("**行业口碑**：")
                content_parts.append(summarized)
                source_content_map.update(crawled_map)
            else:
                content_parts.append("**行业口碑**：")
                for r in reputation_results[:2]:
                    content_parts.append(f"- {r.get('title', '')}: {r.get('body', '')[:100]}")

        # 3. 搜索合作案例
        case_queries = [
            f"{card.company_name} customer case study success story",
            f"{card.company_name} client portfolio",
        ]
        case_results = []
        for query in case_queries[:2]:
            results = ddgs_search(query, max_results=3)
            case_results.extend(results)

        if case_results:
            urls = [r.get('href', '') for r in case_results if r.get('href')]
            unique_urls = list(dict.fromkeys(urls))
            sources.extend(unique_urls[:2])
            crawled, crawled_map = crawl_and_extract(unique_urls[:2], max_length_per_page=50000)
            if crawled:
                # 使用LLM总结案例内容
                summarized = self._summarize_content(crawled, "合作案例")
                content_parts.append("**合作案例**：")
                content_parts.append(summarized)
                source_content_map.update(crawled_map)
            else:
                content_parts.append("**合作案例**：")
                for r in case_results[:2]:
                    content_parts.append(f"- {r.get('title', '')}: {r.get('body', '')[:100]}")

        # 4. 组装内容
        content = "\n".join(content_parts) if content_parts else "未找到相关新闻与声誉信息"

        return self._create_result(
            content=content,
            sources=sources[:5],
            confidence="medium",
            source_content_map=source_content_map
        )

    def _summarize_content(self, content: str, content_type: str) -> str:
        """使用LLM总结内容，提取关键信息，保留来源引用"""
        try:
            import httpx

            prompt = f"""请总结以下{content_type}信息，提取关键要点，用简洁的中文回答（控制在300字以内）。

**重要要求：**
1. 必须保留[1][2][3]等序号引用，每个要点都要标注来源
2. 格式示例：据[1]报道，该公司近期...；根据[2]的信息，...
3. 如果有负面信息，要特别标注
4. 用要点形式呈现

**原始内容：**
{content[:3000]}"""

            response = httpx.post(
                f"{config.mimo.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.mimo.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": config.mimo.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 600,
                    "temperature": 0.3
                },
                timeout=30
            )
            data = response.json()

            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0].get("message", {}).get("content", content[:500])
            return content[:500]
        except Exception as e:
            print(f"内容总结失败: {e}")
            # 如果LLM调用失败，返回带来源的清理内容
            return self._clean_raw_content(content)

    def _clean_raw_content(self, content: str) -> str:
        """清理原始内容，保留来源引用"""
        import re
        # 移除裸URL（但保留[来源: URL]标记）
        content = re.sub(r'(?<!\[来源: )https?://\S+', '', content)
        # 移除多余空白
        content = re.sub(r'\s+', ' ', content)
        # 限制长度
        if len(content) > 500:
            content = content[:500] + "..."
        return content.strip()
