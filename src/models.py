# src/models.py
from dataclasses import dataclass, field
from typing import Dict

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

@dataclass
class ResearchReport:
    """调研报告数据模型"""
    company_name: str = ""
    basic_info: str = ""
    business_track: str = ""
    financial_health: str = ""
    org_structure: str = ""
    news_reputation: str = ""
    sources: list = field(default_factory=list)
    verified: bool = False

@dataclass
class AgentResult:
    """Agent调研结果"""
    agent_name: str = ""
    content: str = ""
    sources: list = field(default_factory=list)
    confidence: str = "medium"  # high/medium/low
