"""Agent 基类 - 提供 LLM 总结和智能评估补充搜索能力"""
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import List

from openai import OpenAI
from ..models import BusinessCard, AgentResult
from ..config import config

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent基类，所有调研Agent应继承此类"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def research(self, card: BusinessCard) -> AgentResult:
        """执行调研任务，返回结果。子类应重写此方法以提供具体调研逻辑。"""
        pass

    def _create_result(self, content: str, sources: list = None, confidence: str = "medium", source_content_map: dict = None) -> AgentResult:
        """创建标准结果"""
        return AgentResult(
            agent_name=self.name,
            content=content,
            sources=sources or [],
            confidence=confidence,
            source_content_map=source_content_map or {}
        )

    def _llm_summarize(self, prompt: str, max_tokens: int = 2000) -> str:
        """调用 LLM 总结内容，失败返回空字符串"""
        try:
            client = OpenAI(api_key=config.mimo.api_key, base_url=config.mimo.api_base)
            response = client.chat.completions.create(
                model=config.mimo.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.1,
            )
            result = response.choices[0].message.content
            return result.strip() if result else ""
        except Exception as e:
            logger.warning(f"LLM 总结失败: {e}")
            return ""

    def _evaluate_and_search(
        self,
        company_name: str,
        raw_findings: str,
        source_index,
        agent_role: str,
        search_categories: List[str],
        country: str = "",
        agent_prefix: str = "",
    ) -> tuple:
        """LLM 评估信息充足性 + 补充搜索 + 最终总结（带唯一引用 ID）

        Args:
            company_name: 公司名称
            raw_findings: 已收集的原始调研内容
            source_index: SourceIndex 实例（会自动追加新来源）
            agent_role: Agent 角色描述（如"基础信息调研"）
            search_categories: 需要搜索的维度列表
            country: 国家
            agent_prefix: 引用前缀（如 B, L, F, O, N, S）

        Returns:
            (总结内容, 来源URL列表)
        """
        if not raw_findings:
            return raw_findings, []

        # Step 1: LLM 评估信息是否充足
        eval_prompt = f"""你是一位资深商业分析师，负责评估对 {company_name} 的{agent_role}调研信息是否充足。

已收集的信息：
{raw_findings[:6000]}

需要评估的维度：
{chr(10).join(f'- {cat}' for cat in search_categories)}

请判断：
1. 上述每个维度的信息是否充足（有具体数据/事实支撑）
2. 列出信息不足的维度
3. 对信息不足的维度，给出具体的补充搜索建议（搜索关键词，英文）

严格用以下 JSON 格式回答，不要添加任何其他文字：
{{"gaps": ["维度1: 缺少什么", "维度2: 缺少什么"], "supplement_queries": ["search keyword 1", "search keyword 2"], "sufficient": false}}"""

        eval_result = self._llm_summarize(eval_prompt, max_tokens=1000)

        # Step 2: 解析评估结果，执行补充搜索
        if eval_result:
            try:
                json_match = re.search(r'\{[^{}]*"supplement_queries"[^{}]*\}', eval_result, re.DOTALL)
                if json_match:
                    eval_data = json.loads(json_match.group())
                    queries = eval_data.get("supplement_queries", [])
                    is_sufficient = eval_data.get("sufficient", True)

                    if queries and not is_sufficient:
                        logger.info(f"{self.name}: 信息不足，执行补充搜索: {queries[:3]}")
                        from ..tools.deep_search import deep_search
                        supp_content, supp_index = deep_search(
                            queries=queries[:3],
                            max_results_per_query=3,
                            crawl_top_n=3,
                            category=f"{self.name}_supplement",
                        )
                        for src in supp_index.get_all_sources():
                            source_index.add_source(
                                url=src["url"],
                                title=src.get("title", ""),
                                content=src.get("content", ""),
                                category=src.get("category", ""),
                            )
                        if supp_content:
                            raw_findings += f"\n\n**补充调研**\n{supp_content}"
            except (json.JSONDecodeError, KeyError, Exception) as e:
                logger.warning(f"{self.name}: LLM 评估结果解析失败，跳过补充搜索: {e}")

        # 收集来源 URL 并构建带前缀的来源列表
        source_list_lines = []
        all_sources = source_index.get_all_sources()
        for i, src in enumerate(all_sources):
            url = src.get("url", "")
            title = src.get("title", "")
            if url:
                source_list_lines.append(f"[{agent_prefix}{i + 1}] {url} - {title}")

        source_list = "\n".join(source_list_lines) if source_list_lines else "（无来源）"
        source_urls = [src.get("url", "") for src in all_sources if src.get("url")]

        # Step 3: LLM 最终总结（带唯一引用 ID）
        final_prompt = f"""你是一位专业的{agent_role}分析师。请根据以下调研数据，为 {company_name} 生成专业的调研总结。

要求：
- 用 3-5 个要点总结关键发现，每个要点控制在 1-2 句话以内
- 每个要点用 markdown 列表格式（- 开头）
- 关键数据用 **加粗** 标注
- 不要编造信息，只基于提供的数据
- 引用来源时必须使用 [{agent_prefix}N] 格式（N为序号），例如 [{agent_prefix}1]、[{agent_prefix}2]
- 每个引用必须对应下方来源列表中的一个条目
- 不要包含章节标题，直接输出要点内容
- 语言专业、精炼，**总字数控制在 400 字以内**
- **重要**：只总结与 {company_name} 直接相关的信息。如果调研数据中包含其他公司或实体的信息（如同名但不同地址/业务的公司），请明确区分或忽略
- 如果调研数据中没有与 {company_name} 直接相关的信息，只输出"未找到该公司在该维度的具体信息"这一句话，不要描述搜索过程、不要解释原因、不要使用行业通用数据
- 过滤掉明显与 {company_name} 无关的搜索结果（如其他同名学校、其他地区的同名机构等）

来源列表（引用时使用方括号中的编号）：
{source_list}

调研数据：
{raw_findings[:10000]}"""

        summary = self._llm_summarize(final_prompt)
        if summary:
            if source_list and source_list != "（无来源）":
                content_with_sources = f"{summary}\n\n来源列表（引用时使用方括号中的编号）：\n{source_list}"
            else:
                content_with_sources = summary
            return content_with_sources, source_urls
        return raw_findings, source_urls
