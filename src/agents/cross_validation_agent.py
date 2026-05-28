"""交叉验证 Agent - 多源信息一致性校验、可信度评分"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .base import BaseAgent
from ..models import BusinessCard, AgentResult

logger = logging.getLogger(__name__)

# 来源可信度权重
SOURCE_WEIGHTS = {
    "名片": 1.0,
    "人工补充": 1.0,
    "官网": 0.9,
    "SEC EDGAR": 0.85,
    "工商信息": 0.85,
    "OpenCorporates": 0.85,
    "Wikidata": 0.8,
    "yfinance": 0.8,
    "LinkedIn": 0.7,
    "社媒": 0.7,
    "Google Maps": 0.7,
    "Trustpilot": 0.6,
    "Sitejabber": 0.6,
    "Wayback Machine": 0.6,
    "WHOIS": 0.6,
    "第三方平台": 0.6,
    "搜索引擎": 0.5,
}


@dataclass
class FieldVerification:
    """字段验证结果"""
    field_name: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    consistency: bool = False
    credibility_score: float = 0.0
    verification_status: str = "未验证"
    recommended_value: str = ""


class CrossValidationAgent(BaseAgent):
    """交叉验证 Agent"""

    def __init__(self):
        super().__init__("cross_validation")

    def research(self, card: BusinessCard) -> AgentResult:
        """执行交叉验证"""
        # 这个 Agent 不直接调用外部 API，而是验证其他 Agent 的结果
        # 返回验证框架和规则
        content = self._generate_validation_framework(card)
        return self._create_result(
            content=content,
            sources=["交叉验证框架"],
            confidence="high",
            source_content_map={}
        )

    def validate_field(
        self,
        field_name: str,
        field_values: List[Dict[str, Any]],
    ) -> FieldVerification:
        """验证单个字段的多源一致性

        Args:
            field_name: 字段名称
            field_values: 该字段的多个来源值
                [{"source": "名片", "value": "..."}, {"source": "官网", "value": "..."}]

        Returns:
            FieldVerification 验证结果
        """
        verification = FieldVerification(field_name=field_name)

        if not field_values:
            verification.verification_status = "无数据"
            return verification

        verification.sources = field_values

        # 提取所有值
        values = [fv.get("value", "") for fv in field_values if fv.get("value")]

        if not values:
            verification.verification_status = "无有效数据"
            return verification

        # 检查一致性
        unique_values = set(v.strip().lower() for v in values if v.strip())
        verification.consistency = len(unique_values) <= 1

        # 计算可信度评分
        total_weight = 0.0
        weight_count = 0
        for fv in field_values:
            source = fv.get("source", "搜索引擎")
            weight = SOURCE_WEIGHTS.get(source, 0.5)
            total_weight += weight
            weight_count += 1

        if weight_count > 0:
            # 归一化到 1-5 分
            avg_weight = total_weight / weight_count
            consistency_bonus = 0.5 if verification.consistency else 0
            verification.credibility_score = min(5, int((avg_weight + consistency_bonus) * 5))

        # 确定推荐值
        if verification.consistency:
            verification.recommended_value = values[0]
            verification.verification_status = "已验证"
        else:
            # 多个不同值，展示所有
            verification.recommended_value = " | ".join(set(values))
            verification.verification_status = "待人工确认"

        return verification

    def calculate_consistency(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算多个来源的一致性

        Args:
            sources: 来源列表 [{"source": "...", "value": "...", "url": "..."}]

        Returns:
            一致性结果
        """
        if not sources:
            return {
                "consistent": False,
                "score": 0,
                "reason": "无数据",
            }

        values = [s.get("value", "") for s in sources if s.get("value")]
        unique_values = set(v.strip().lower() for v in values if v.strip())

        if len(unique_values) <= 1:
            # 所有来源一致
            weights = [SOURCE_WEIGHTS.get(s.get("source", ""), 0.5) for s in sources]
            avg_weight = sum(weights) / len(weights) if weights else 0.5
            score = min(5, int(avg_weight * 5))
            return {
                "consistent": True,
                "score": score,
                "reason": "所有来源一致",
                "sources": sources,
            }
        else:
            return {
                "consistent": False,
                "score": 0,
                "reason": f"发现 {len(unique_values)} 个不同值",
                "sources": sources,
                "unique_values": list(unique_values),
            }

    def generate_verification_report(self, verifications: List[FieldVerification]) -> str:
        """生成交叉验证报告"""
        if not verifications:
            return "无交叉验证数据"

        report = "## 交叉验证结果\n\n"
        report += "| 字段 | 来源数 | 一致性 | 可信度 | 状态 | 推荐值 |\n"
        report += "|------|--------|--------|--------|------|--------|\n"

        for v in verifications:
            consistency_icon = "✅" if v.consistency else "⚠️"
            report += f"| {v.field_name} | {len(v.sources)} | {consistency_icon} | {v.credibility_score}/5 | {v.verification_status} | {v.recommended_value[:50]} |\n"

        # 统计
        total = len(verifications)
        verified = sum(1 for v in verifications if v.verification_status == "已验证")
        needs_review = sum(1 for v in verifications if v.verification_status == "待人工确认")
        no_data = sum(1 for v in verifications if v.verification_status in ("无数据", "无有效数据"))

        report += f"\n**统计**：{verified}/{total} 已验证，{needs_review}/{total} 待人工确认，{no_data}/{total} 无数据\n"

        return report

    def _generate_validation_framework(self, card: BusinessCard) -> str:
        """生成验证框架说明"""
        framework = "# 交叉验证框架\n\n"
        framework += "## 来源可信度权重\n\n"
        framework += "| 来源 | 权重 |\n"
        framework += "|------|------|\n"

        for source, weight in sorted(SOURCE_WEIGHTS.items(), key=lambda x: -x[1]):
            framework += f"| {source} | {weight} |\n"

        framework += "\n## 验证规则\n\n"
        framework += "1. 同一字段多个来源一致时，可信度加权求和\n"
        framework += "2. 不一致时，展示所有来源，标记为待人工确认\n"
        framework += "3. 权重越高来源的信息越可信\n"
        framework += "4. 建议优先采用高权重来源的信息\n"

        return framework
