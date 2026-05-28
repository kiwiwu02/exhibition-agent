import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    FEISHU_APP_ID: str = os.getenv("FEISHU_APP_ID", "")
    FEISHU_APP_SECRET: str = os.getenv("FEISHU_APP_SECRET", "")
    ATTACHMENTS_DIR: str = os.getenv(
        "ATTACHMENTS_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", ".cc-connect", "attachments"),
    )
    PROCESS_CARD_TIMEOUT: int = 600  # 10 minutes
    CONTEXT_TIMEOUT: int = 600  # 10 minutes


config = Config()
