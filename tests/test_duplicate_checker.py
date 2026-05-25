# tests/test_duplicate_checker.py
import pytest
from src.duplicate_checker import check_duplicate
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
