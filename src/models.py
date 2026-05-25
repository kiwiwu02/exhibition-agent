# src/models.py
from dataclasses import dataclass, field
from typing import Optional, Dict
from datetime import datetime

@dataclass
class BusinessCard:
    company_name: str = ""
    company_name_en: str = ""
    company_alias: str = ""
    contact_name: str = ""
    position: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    website: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    additional_info: str = ""
    confidence: Dict[str, str] = field(default_factory=dict)

@dataclass
class CRMSession:
    record_id: str = ""
    company_name: str = ""
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    is_duplicate: bool = False
    duplicate_record_id: str = ""
