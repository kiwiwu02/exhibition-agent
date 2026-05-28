"""CRM 补充 Agent - 综合所有调研结果补齐缺失的 CRM 字段"""
import json
import logging
import re
from typing import Dict, List

from .base import BaseAgent
from ..models import BusinessCard, AgentResult

logger = logging.getLogger(__name__)


class CRMSupplementAgent(BaseAgent):
    """CRM 字段补充 Agent

    在所有调研完成后运行，综合所有信息源（调研结果、搜索、LLM 推断）
    自动补齐 Bitable 中缺失的字段。
    """

    def __init__(self):
        super().__init__("crm_supplement")

    def research(self, card: BusinessCard) -> AgentResult:
        return self._create_result(content="", sources=[])

    def supplement(
        self,
        card: BusinessCard,
        all_results: List[AgentResult],
    ) -> Dict[str, str]:
        """分析所有调研结果，提取可补充到 CRM 的字段

        Returns:
            {bitable_field_name: value} 需要更新的字段
        """
        # 1. 收集所有调研内容
        all_content = "\n\n".join(r.content for r in all_results if r.content)

        # 2. 识别缺失字段
        missing = self._identify_missing_fields(card)
        if not missing:
            logger.info("CRM 字段已完整，无需补充")
            return {}

        logger.info(f"缺失字段: {list(missing.keys())}")

        # 3. 从调研结果中提取
        supplements = {}
        for field, reason in missing.items():
            value = self._extract_from_research(field, all_content, card)
            if value:
                supplements[field] = value
                logger.info(f"从调研结果补充 {field}: {value[:50]}")

        # 4. 对仍然缺失的关键字段，用 LLM 综合推断
        still_missing = {k: v for k, v in missing.items() if k not in supplements}
        if still_missing and all_content:
            llm_supplements = self._llm_infer_fields(still_missing, all_content, card)
            supplements.update(llm_supplements)
            for field, value in llm_supplements.items():
                logger.info(f"LLM 推断补充 {field}: {value[:50]}")

        return supplements

    def _identify_missing_fields(self, card: BusinessCard) -> Dict[str, str]:
        """识别缺失的 CRM 字段及其重要性"""
        missing = {}

        if not card.company_name:
            missing["公司名称"] = "公司名称是核心字段，必须补充"

        if not card.country:
            missing["国家/地区"] = "国家信息用于区域分类"

        if not card.city:
            missing["城市"] = "城市信息用于定位"

        if not card.address:
            missing["公司地址"] = "地址用于联系和验证"

        if not card.website:
            missing["官网"] = "官网是重要联系渠道"

        return missing

    def _extract_from_research(self, field: str, content: str, card: BusinessCard) -> str:
        """从调研结果中提取特定字段"""
        if not content:
            return ""

        if field == "国家/地区":
            return self._extract_country(content)

        if field == "城市":
            return self._extract_city(content)

        if field == "公司地址":
            return self._extract_address(content)

        if field == "官网":
            return self._extract_website(content)

        if field == "公司名称":
            return self._extract_company_name(content, card)

        return ""

    def _extract_company_en_name(self, content: str) -> str:
        """从内容中提取公司英文名"""
        patterns = [
            r'(?:also known as|AKA|trading as|T/A)\s+([A-Z][A-Za-z\s&.,]+?)(?:\.|,|\n)',
            r'(?:English name|公司英文名|英文名称|company name in English)[：:]\s*(.+?)(?:\n|$)',
            r'(?:officially (?:known|called) as)\s+([A-Z][A-Za-z\s&.,]+?)(?:\.|,|\n)',
            r'(?:公司名称英文|英文公司名)[：:]\s*(.+?)(?:\n|$)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 2 and len(name) < 100:
                    return name
        return ""

    def _extract_country(self, content: str) -> str:
        """从内容中提取国家"""
        countries = [
            "China", "Japan", "South Korea", "Korea", "India", "Singapore",
            "Thailand", "Vietnam", "Indonesia", "Malaysia", "Philippines",
            "United States", "USA", "Canada", "United Kingdom", "UK",
            "Germany", "France", "Italy", "Spain", "Netherlands",
            "Australia", "New Zealand", "Brazil", "Mexico", "Argentina",
            "UAE", "Saudi Arabia", "Israel", "Turkey", "South Africa",
            "Nigeria", "Egypt", "Kenya", "Morocco",
        ]
        content_lower = content.lower()
        for country in countries:
            if country.lower() in content_lower:
                return country
        return ""

    def _extract_city(self, content: str) -> str:
        """从内容中提取城市"""
        # 先检查常见城市名
        known_cities = ["Seoul", "Tokyo", "Osaka", "Shanghai", "Beijing", "Shenzhen",
                       "Singapore", "Bangkok", "Jakarta", "Hanoi", "Ho Chi Minh",
                       "Taipei", "Hong Kong", "Mumbai", "Delhi", "Dubai"]
        for city in known_cities:
            if city.lower() in content.lower():
                return city

        patterns = [
            r'(?:headquarters?|head office|main office|located in|based in|office in)\s*[:：]?\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)',
            r'(?:总部|位于|设在|办公地点)\s*[:：]?\s*(.+?)(?:[，,。\n])',
            r'(?:city|城市)[：:]\s*(.+?)(?:\n|$)',
            r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*(?:South\s+)?Korea',
            r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*(?:United States|USA|Japan|China|Singapore)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                city = match.group(1).strip()
                if len(city) > 1 and len(city) < 50:
                    return city
        return ""

    def _extract_address(self, content: str) -> str:
        """从内容中提取地址"""
        patterns = [
            r'(?:address|地址|located at|headquarters at|headquarters:|office address)[：:]\s*(.+?)(?:\n|$)',
            r'(?:\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln)[^,\n]*(?:,\s*[A-Za-z\s]+)?(?:,\s*[A-Z]{2}\s+\d{5})?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                addr = match.group(1) if match.lastindex else match.group(0)
                addr = addr.strip()
                # 验证：地址应包含数字或常见地址关键词
                if len(addr) > 5 and len(addr) < 200:
                    has_number = bool(re.search(r'\d', addr))
                    has_addr_word = bool(re.search(
                        r'(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|'
                        r'gu|dong|gu|ro|ga|myeon|ri|si|do|gun|city|town|village|'
                        r'区|路|街|巷|号|弄|栋|楼|室)',
                        addr, re.IGNORECASE
                    ))
                    if has_number or has_addr_word:
                        return addr
        return ""

    def _extract_website(self, content: str) -> str:
        """从内容中提取官网"""
        patterns = [
            r'(?:official website|官网|website)[：:]\s*(https?://[^\s\)]+)',
            r'(?:official website|官网|website)[：:]\s*([^\s\)]+\.[a-z]{2,})',
            r'(https?://(?:www\.)?[a-zA-Z0-9-]+\.[a-z]{2,}(?:/[^\s\)]*)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                url = match.group(1)
                # 排除社交媒体和通用网站
                excluded = ["linkedin.com", "facebook.com", "twitter.com",
                           "instagram.com", "youtube.com", "google.com",
                           "bloomberg.com", "reuters.com", "wikipedia.org"]
                if not any(ex in url.lower() for ex in excluded):
                    return url
        return ""

    def _extract_company_name(self, content: str, card: BusinessCard) -> str:
        """从内容中提取公司名（中英文）"""
        # 用 LLM 提取
        try:
            from openai import OpenAI
            from ..config import config

            client = OpenAI(
                api_key=config.mimo.api_key,
                base_url=config.mimo.api_base
            )

            # 构造上下文
            context_parts = []
            if card.contact_name:
                context_parts.append(f"联系人: {card.contact_name}")
            if card.email:
                context_parts.append(f"邮箱: {card.email}")
            if card.phone:
                context_parts.append(f"电话: {card.phone}")
            if card.position:
                context_parts.append(f"职位: {card.position}")

            context = "\n".join(context_parts) if context_parts else "无"

            prompt = f"""从以下调研结果中，提取与该联系人相关的公司名称。

联系人信息：
{context}

调研结果（前2000字）：
{content[:2000]}

请返回JSON格式：
{{
  "company_name": "公司名称（保留原始语言，不要翻译）",
  "company_name_en": "公司英文名称（如有）"
}}

注意：
1. 只返回JSON，不要其他内容
2. 如果无法确定公司名，两个字段都返回空字符串 ""
3. 优先提取与联系人直接相关的公司名
4. 公司名应与联系人的邮箱域名、职位、所在国家等信息一致
5. 保留原始语言，不要将英文公司名翻译成中文"""

            response = client.chat.completions.create(
                model=config.mimo.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1,
            )

            result_text = response.choices[0].message.content
            match = re.search(r'\{[\s\S]*\}', result_text)
            if match:
                data = json.loads(match.group())
                cn = data.get("company_name", "").strip()
                cn_en = data.get("company_name_en", "").strip()
                if cn:
                    return cn
                if cn_en:
                    return cn_en

            return ""

        except Exception as e:
            logger.warning(f"LLM 提取公司名失败: {e}")
            return ""

    def _llm_infer_fields(
        self, missing: Dict[str, str], content: str, card: BusinessCard
    ) -> Dict[str, str]:
        """用 LLM 综合推断缺失字段"""
        if not content:
            return {}

        try:
            from openai import OpenAI
            from ..config import config

            client = OpenAI(
                api_key=config.mimo.api_key,
                base_url=config.mimo.api_base
            )

            # 已有字段信息
            existing = {
                "company_name": card.company_name,
                "contact_name": card.contact_name,
                "email": card.email,
                "phone": card.phone,
                "position": card.position,
                "country": card.country,
                "city": card.city,
                "address": card.address,
                "website": card.website,
            }
            existing_str = json.dumps(
                {k: v for k, v in existing.items() if v}, ensure_ascii=False
            )

            fields_str = ", ".join(missing.keys())

            prompt = f"""根据调研结果，推断以下缺失的 CRM 字段。

已有信息：
{existing_str}

缺失字段：{fields_str}

调研结果（前3000字）：
{content[:3000]}

请返回JSON格式，只包含能确定的字段：
{{
  "公司名称": "推断的公司名（如能确定）",
  "国家/地区": "国家（如能确定）",
  "城市": "城市（如能确定）",
  "公司地址": "地址（如能确定）",
  "官网": "官网URL（如能确定）"
}}

注意：
1. 只返回JSON，不要其他内容
2. 只包含你能从调研结果中明确推断的字段
3. 不确定的字段不要包含
4. 推断必须有依据（如邮箱域名、LinkedIn信息、新闻报道等）"""

            response = client.chat.completions.create(
                model=config.mimo.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1,
            )

            result_text = response.choices[0].message.content
            match = re.search(r'\{[\s\S]*\}', result_text)
            if match:
                data = json.loads(match.group())
                # 只保留缺失的字段
                return {k: v for k, v in data.items() if k in missing and v}

            return {}

        except Exception as e:
            logger.warning(f"LLM 推断字段失败: {e}")
            return {}
