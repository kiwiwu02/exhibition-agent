# src/config.py
import os
from dataclasses import dataclass

@dataclass
class MiMoConfig:
    api_base: str = os.getenv("MIMO_API_BASE", "https://api.mimo.ai/v1")
    model: str = os.getenv("MIMO_MODEL", "mimo-v2.5")
    api_key: str = os.getenv("MIMO_API_KEY", "")
    max_tokens: int = 2000
    temperature: float = 0.1

@dataclass
class TavilyConfig:
    api_key: str = os.getenv("TAVILY_API_KEY", "")

@dataclass
class FeishuConfig:
    app_id: str = os.getenv("FEISHU_APP_ID", "cli_aa9ecb3fb4b89cb1")
    app_secret: str = os.getenv("FEISHU_APP_SECRET", "")
    bitable_app_token: str = os.getenv("FEISHU_BITABLE_APP_TOKEN", "")
    bitable_table_id: str = os.getenv("FEISHU_BITABLE_TABLE_ID", "")

@dataclass
class Config:
    mimo: MiMoConfig = None
    tavily: TavilyConfig = None
    feishu: FeishuConfig = None

    def __post_init__(self):
        self.mimo = self.mimo or MiMoConfig()
        self.tavily = self.tavily or TavilyConfig()
        self.feishu = self.feishu or FeishuConfig()

config = Config()
