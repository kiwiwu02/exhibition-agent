# tests/test_duplicate_checker.py
import pytest
from src.duplicate_checker import check_duplicate, similar_ratio, normalize_phone
from src.models import BusinessCard, CRMSession

def test_check_duplicate_no_match():
    new_card = BusinessCard(
        company_name="New Corp",
        email="new@example.com"
    )
    existing_records = [
        CRMSession(company_name="Old Corp", email="old@example.com")
    ]
    result = check_duplicate(new_card, existing_records)
    assert result["is_duplicate"] == False

def test_check_duplicate_email_match():
    new_card = BusinessCard(
        company_name="Tech Corp",
        email="john@techcorp.com"
    )
    existing_records = [
        CRMSession(record_id="123", company_name="Tech Corp", email="john@techcorp.com")
    ]
    result = check_duplicate(new_card, existing_records)
    assert result["is_duplicate"] == True
    assert result["confidence"] == "high"

# 测试 similar_ratio() 函数
def test_similar_ratio_identical():
    result = similar_ratio("Tech Corp", "Tech Corp")
    assert result == 1.0

def test_similar_ratio_similar():
    result = similar_ratio("Tech Corp", "Tech Corporation")
    assert result > 0.7

def test_similar_ratio_different():
    result = similar_ratio("Tech Corp", "ABC Inc")
    assert result < 0.5

# 测试 normalize_phone() 函数
def test_normalize_phone_with_symbols():
    result = normalize_phone("+1-555-123-4567")
    assert result == "+15551234567"

def test_normalize_phone_with_spaces():
    result = normalize_phone("+49 30 12345678")
    assert result == "+493012345678"

# 测试公司名+联系人匹配
def test_check_duplicate_company_contact_match():
    new_card = BusinessCard(
        company_name="Tech Corp",
        contact_name="John Smith",
        email=""
    )
    existing_records = [
        CRMSession(record_id="456", company_name="Tech Corp.", contact_name="John Smith", email="")
    ]
    result = check_duplicate(new_card, existing_records)
    assert result["is_duplicate"] == True
    assert result["confidence"] == "medium"

# 测试公司名+电话匹配
def test_check_duplicate_company_phone_match():
    new_card = BusinessCard(
        company_name="Tech Corp",
        phone="+1-555-123-4567",
        email=""
    )
    existing_records = [
        CRMSession(record_id="789", company_name="Tech Corp.", phone="+15551234567", email="")
    ]
    result = check_duplicate(new_card, existing_records)
    assert result["is_duplicate"] == True
    assert result["confidence"] == "medium"
