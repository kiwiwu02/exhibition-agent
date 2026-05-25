# src/card_recognizer.py
import base64
import json
import re
from openai import OpenAI
from .config import config
from .models import BusinessCard

RECOGNITION_PROMPT = """
请识别这张名片图片，提取以下字段（JSON格式）：

{
  "company_name": "公司名称",
  "company_name_en": "公司英文名称（如有）",
  "company_alias": "公司别名/缩写（如有）",
  "contact_name": "联系人姓名",
  "position": "职位",
  "email": "邮箱",
  "phone": "电话",
  "address": "完整地址",
  "website": "网站",
  "country": "国家/地区",
  "region": "区域（北美/欧洲/亚太/中东/南美）",
  "city": "城市",
  "additional_info": "其他可见信息",
  "confidence": {
    "company_name": "high/medium/low",
    "contact_name": "high/medium/low",
    "email": "high/medium/low",
    "phone": "high/medium/low"
  }
}

注意事项：
1. 如果字段不清晰或无法识别，置信度设为low
2. 多语言名片请同时提取中英文
3. 电话请保留国际区号
4. 地址请尽可能完整
5. 根据公司名称和地址推断区域（region）
"""

def recognize_business_card(image_path: str) -> BusinessCard:
    """使用MiMo-V2.5识别名片图片"""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    client = OpenAI(
        api_key=config.mimo.api_key,
        base_url=config.mimo.api_base
    )

    response = client.chat.completions.create(
        model=config.mimo.model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                    },
                    {"type": "text", "text": RECOGNITION_PROMPT}
                ]
            }
        ],
        max_tokens=config.mimo.max_tokens,
        temperature=config.mimo.temperature
    )

    return parse_recognition_result(response.choices[0].message.content)

def parse_recognition_result(result: str) -> BusinessCard:
    """解析AI识别结果"""
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return BusinessCard(
                company_name=data.get("company_name", ""),
                company_name_en=data.get("company_name_en", ""),
                company_alias=data.get("company_alias", ""),
                contact_name=data.get("contact_name", ""),
                position=data.get("position", ""),
                email=data.get("email", ""),
                phone=data.get("phone", ""),
                address=data.get("address", ""),
                website=data.get("website", ""),
                country=data.get("country", ""),
                region=data.get("region", ""),
                city=data.get("city", ""),
                additional_info=data.get("additional_info", ""),
                confidence=data.get("confidence", {})
            )
    except (json.JSONDecodeError, AttributeError):
        pass
    return BusinessCard()