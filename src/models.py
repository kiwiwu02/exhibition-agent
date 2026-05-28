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
    company_name_en: str = ""
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
    report_url: str = ""
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
    supply_chain: str = ""
    sales_opportunity: str = ""
    full_report_content: str = ""  # 完整 markdown 报告内容
    sources: list = field(default_factory=list)
    verified: bool = False
    crm_supplements: dict = field(default_factory=dict)  # CRM 字段补充 {field_name: value}

@dataclass
class AgentResult:
    """Agent调研结果"""
    agent_name: str = ""
    content: str = ""
    sources: list = field(default_factory=list)
    confidence: str = "medium"  # high/medium/low
    source_content_map: dict = field(default_factory=dict)  # URL -> 内容摘要
    source_index: object = None  # SourceIndex 实例，用于准确引用
    source_urls: list = field(default_factory=list)  # 带唯一引用ID的来源URL列表
