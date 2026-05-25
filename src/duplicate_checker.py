# src/duplicate_checker.py
from difflib import SequenceMatcher
from .models import BusinessCard, CRMSession

def check_duplicate(new_card: BusinessCard, existing_records: list) -> dict:
    """检查新名片是否与现有记录重复"""

    # 规则1：邮箱完全匹配（高置信度）
    if new_card.email:
        for record in existing_records:
            if record.email and record.email.lower() == new_card.email.lower():
                return {
                    "is_duplicate": True,
                    "confidence": "high",
                    "matched_record_id": record.record_id,
                    "reason": "邮箱完全匹配"
                }

    # 规则2：公司名 + 联系人姓名匹配（中置信度）
    if new_card.company_name and new_card.contact_name:
        for record in existing_records:
            if (record.company_name and record.contact_name and
                similar_ratio(new_card.company_name, record.company_name) > 0.8 and
                similar_ratio(new_card.contact_name, record.contact_name) > 0.8):
                return {
                    "is_duplicate": True,
                    "confidence": "medium",
                    "matched_record_id": record.record_id,
                    "reason": "公司名+联系人匹配"
                }

    # 规则3：公司名 + 电话匹配（中置信度）
    if new_card.company_name and new_card.phone:
        for record in existing_records:
            if (record.company_name and record.phone and
                similar_ratio(new_card.company_name, record.company_name) > 0.8 and
                normalize_phone(new_card.phone) == normalize_phone(record.phone)):
                return {
                    "is_duplicate": True,
                    "confidence": "medium",
                    "matched_record_id": record.record_id,
                    "reason": "公司名+电话匹配"
                }

    return {"is_duplicate": False}

def similar_ratio(a: str, b: str) -> float:
    """计算字符串相似度"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def normalize_phone(phone: str) -> str:
    """标准化电话号码"""
    import re
    return re.sub(r'[^0-9+]', '', phone)
