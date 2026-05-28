# src/duplicate_checker.py
"""重复检测与合并策略"""
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Tuple, Dict
from .models import BusinessCard, CRMSession


# BusinessCard 字段到 CRMSession 字段的映射
FIELD_MAP = {
    "company_name": "公司名称",
    "company_name_en": "公司别名",
    "contact_name": "联系人姓名",
    "position": "职位",
    "email": "邮箱",
    "phone": "电话",
    "address": "公司地址",
    "website": "官网",
    "country": "国家/地区",
    "region": "区域",
    "city": "城市",
    "additional_info": "补充信息",
}

COMPARE_FIELDS = ["company_name", "company_name_en", "contact_name", "position",
                  "email", "phone", "address", "website", "country", "region", "city"]


@dataclass
class DuplicateResult:
    """重复检测结果"""
    action: str = "create"  # "create" | "ask_user" | "create_new_contact"
    confidence: str = ""    # "high" | "medium" | "low"
    matched_record_id: str = ""
    matched_record: CRMSession = None
    reason: str = ""
    conflict_fields: List[str] = field(default_factory=list)


def check_duplicate(new_card: BusinessCard, existing_records: List[CRMSession]) -> DuplicateResult:
    """检测新名片是否与现有记录重复，并分类决策

    Returns:
        DuplicateResult: 包含决策动作、匹配置信度、冲突字段等
    """
    # 规则1：邮箱完全匹配（高置信度）→ 询问用户
    if new_card.email:
        for record in existing_records:
            if record.email and record.email.lower() == new_card.email.lower():
                conflicts = _find_conflict_fields(new_card, record)
                return DuplicateResult(
                    action="ask_user",
                    confidence="high",
                    matched_record_id=record.record_id,
                    matched_record=record,
                    reason=f"邮箱完全匹配: {new_card.email}",
                    conflict_fields=conflicts,
                )

    # 规则2：公司名 + 联系人名均>80%匹配（中置信度）→ 询问用户
    if new_card.company_name and new_card.contact_name:
        for record in existing_records:
            if (record.company_name and record.contact_name and
                _similar(new_card.company_name, record.company_name) > 0.8 and
                _similar(new_card.contact_name, record.contact_name) > 0.8):
                conflicts = _find_conflict_fields(new_card, record)
                return DuplicateResult(
                    action="ask_user",
                    confidence="medium",
                    matched_record_id=record.record_id,
                    matched_record=record,
                    reason=f"公司名+联系人匹配: {record.company_name}-{record.contact_name}",
                    conflict_fields=conflicts,
                )

    # 规则3：公司名>80%匹配 + 电话匹配（中置信度）→ 询问用户
    if new_card.company_name and new_card.phone:
        for record in existing_records:
            if (record.company_name and record.phone and
                _similar(new_card.company_name, record.company_name) > 0.8 and
                _normalize_phone(new_card.phone) == _normalize_phone(record.phone)):
                conflicts = _find_conflict_fields(new_card, record)
                return DuplicateResult(
                    action="ask_user",
                    confidence="medium",
                    matched_record_id=record.record_id,
                    matched_record=record,
                    reason=f"公司名+电话匹配: {record.company_name}",
                    conflict_fields=conflicts,
                )

    # 规则4：公司名匹配但联系人不同（中置信度）→ 同公司新联系人
    if new_card.company_name:
        for record in existing_records:
            if record.company_name and _similar(new_card.company_name, record.company_name) > 0.8:
                return DuplicateResult(
                    action="create_new_contact",
                    confidence="medium",
                    matched_record_id=record.record_id,
                    matched_record=record,
                    reason=f"同公司新联系人: {record.company_name}",
                )

    # 无匹配 → 创建新记录
    return DuplicateResult(action="create")


def merge_card_to_record(
    new_card: BusinessCard, existing_record: CRMSession
) -> Tuple[Dict[str, str], List[str]]:
    """将新名片信息合并到已有记录

    Returns:
        (updates, conflicts):
            updates: 需要更新的字段 {bitable_field_name: new_value}
            conflicts: 冲突字段描述列表
    """
    updates = {}
    conflicts = []

    for field in COMPARE_FIELDS:
        new_val = getattr(new_card, field, "")
        old_val = getattr(existing_record, field, "")

        if not new_val:
            continue

        if not old_val:
            # 旧记录为空，新值填充
            bitable_field = FIELD_MAP.get(field, field)
            updates[bitable_field] = new_val
        elif old_val != new_val and _similar(str(old_val), str(new_val)) < 0.9:
            # 都有值但明显不同 → 冲突
            conflicts.append(f"{field}: 原值=\"{old_val}\", 新值=\"{new_val}\"")

    # 如果有冲突，将冲突信息追加到补充信息
    if conflicts:
        conflict_text = "【合并冲突】" + "; ".join(conflicts)
        existing_additional = existing_record.additional_info or ""
        if conflict_text not in existing_additional:
            updates["补充信息"] = (existing_additional + "\n" + conflict_text).strip()

    return updates, conflicts


def _find_conflict_fields(new_card: BusinessCard, existing_record: CRMSession) -> List[str]:
    """找出新旧记录之间有冲突的字段"""
    conflicts = []
    for field in COMPARE_FIELDS:
        new_val = getattr(new_card, field, "")
        old_val = getattr(existing_record, field, "")
        if new_val and old_val and new_val != old_val and _similar(str(new_val), str(old_val)) < 0.9:
            conflicts.append(field)
    return conflicts


def _similar(a: str, b: str) -> float:
    """计算字符串相似度"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _normalize_phone(phone: str) -> str:
    """标准化电话号码（只保留数字和+）"""
    return re.sub(r'[^0-9+]', '', phone)
