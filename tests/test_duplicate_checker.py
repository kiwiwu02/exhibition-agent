# tests/test_duplicate_checker.py
import pytest
from src.duplicate_checker import (
    check_duplicate, merge_card_to_record,
    _similar, _normalize_phone, DuplicateResult,
)
from src.models import BusinessCard, CRMSession


def test_check_duplicate_no_match():
    new_card = BusinessCard(company_name="New Corp", email="new@example.com")
    existing_records = [CRMSession(company_name="Old Corp", email="old@example.com")]
    result = check_duplicate(new_card, existing_records)
    assert result.action == "create"


def test_check_duplicate_email_match():
    new_card = BusinessCard(company_name="Tech Corp", email="john@techcorp.com")
    existing_records = [
        CRMSession(record_id="123", company_name="Tech Corp", email="john@techcorp.com")
    ]
    result = check_duplicate(new_card, existing_records)
    assert result.action == "ask_user"
    assert result.confidence == "high"
    assert result.matched_record_id == "123"


def test_similar_identical():
    assert _similar("Tech Corp", "Tech Corp") == 1.0


def test_similar_similar():
    assert _similar("Tech Corp", "Tech Corporation") > 0.7


def test_similar_different():
    assert _similar("Tech Corp", "ABC Inc") < 0.5


def test_normalize_phone_with_symbols():
    assert _normalize_phone("+1-555-123-4567") == "+15551234567"


def test_normalize_phone_with_spaces():
    assert _normalize_phone("+49 30 12345678") == "+493012345678"


def test_check_duplicate_company_contact_match():
    new_card = BusinessCard(company_name="Tech Corp", contact_name="John Smith")
    existing_records = [
        CRMSession(record_id="456", company_name="Tech Corp.", contact_name="John Smith")
    ]
    result = check_duplicate(new_card, existing_records)
    assert result.action == "ask_user"
    assert result.confidence == "medium"


def test_check_duplicate_company_phone_match():
    new_card = BusinessCard(company_name="Tech Corp", phone="+1-555-123-4567")
    existing_records = [
        CRMSession(record_id="789", company_name="Tech Corp.", phone="+15551234567")
    ]
    result = check_duplicate(new_card, existing_records)
    assert result.action == "ask_user"
    assert result.confidence == "medium"


def test_check_duplicate_same_company_different_contact():
    new_card = BusinessCard(company_name="Tech Corp", contact_name="Alice Wang")
    existing_records = [
        CRMSession(record_id="100", company_name="Tech Corp", contact_name="John Smith")
    ]
    result = check_duplicate(new_card, existing_records)
    assert result.action == "create_new_contact"
    assert result.matched_record_id == "100"


def test_merge_card_to_record_fills_empty():
    card = BusinessCard(phone="+1234", city="San Francisco")
    record = CRMSession(record_id="r1", company_name="Tech Corp", phone="", city="")
    updates, conflicts = merge_card_to_record(card, record)
    assert "电话" in updates
    assert updates["电话"] == "+1234"
    assert "城市" in updates
    assert updates["城市"] == "San Francisco"
    assert len(conflicts) == 0


def test_merge_card_to_record_conflict():
    card = BusinessCard(email="new@tech.com")
    record = CRMSession(record_id="r1", email="old@tech.com")
    updates, conflicts = merge_card_to_record(card, record)
    assert len(conflicts) == 1
    assert "email" in conflicts[0]


def test_merge_card_to_record_no_updates():
    card = BusinessCard(email="")
    record = CRMSession(record_id="r1", email="existing@tech.com")
    updates, conflicts = merge_card_to_record(card, record)
    assert len(updates) == 0
    assert len(conflicts) == 0
