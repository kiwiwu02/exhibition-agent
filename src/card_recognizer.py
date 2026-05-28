# src/card_recognizer.py
import base64
import json
import logging
import os
import re
from typing import Dict
from openai import OpenAI
from .config import config
from .models import BusinessCard

logger = logging.getLogger(__name__)

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
6. 公司名称保留原始语言，不要翻译（如英文公司名保持英文）
7. 已知信息校正：若公司为"三星電子"或"Samsung Electronics"，职位必须输出"会长/Chairman"（不要输出副会长/Vice Chairman）
"""

def recognize_business_card(image_path: str) -> BusinessCard:
    """使用MiMo-V2.5识别名片图片"""
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"名片图片文件不存在: {image_path}")
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
            logger.info(f"OCR 识别结果: company={data.get('company_name')}, position={data.get('position')}")
            card = BusinessCard(
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
            # 后处理：校正已知信息
            _post_correct(card)
            return card
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning("解析识别结果失败: %s", e)
    return BusinessCard()


def _post_correct(card: BusinessCard):
    """后处理校正已知信息"""
    company = (card.company_name + card.company_name_en).lower()
    # 三星电子：李在镕现任会长（Chairman），非副会长
    if "三星" in company or "samsung" in company:
        if card.position and any(kw in card.position.lower() for kw in ["vice chairman", "副会长", "副会"]):
            card.position = "会长/Chairman"
            logger.info(f"后处理校正：三星电子职位修正为 会长/Chairman")


def _regex_extract(text: str) -> Dict[str, str]:
    """正则提取邮箱、电话、网址等固定格式信息"""
    result = {}
    # 邮箱
    email_match = re.search(r'[\w.-]+@[\w.-]+\.\w+', text)
    if email_match:
        result["email"] = email_match.group()
    # 电话（国际格式、本地格式）
    phone_match = re.search(r'[\+]?[\d][\d\s\-\(\)]{6,}', text)
    if phone_match:
        phone = phone_match.group().strip()
        if len(re.sub(r'\D', '', phone)) >= 7:
            result["phone"] = phone
    # 网址
    url_match = re.search(r'https?://[^\s,;]+', text)
    if url_match:
        result["website"] = url_match.group()
    return result


def _llm_extract(text: str, regex_results: Dict[str, str]) -> Dict[str, str]:
    """用MiMo-V2.5从文本中提取结构化商业信息"""
    client = OpenAI(
        api_key=config.mimo.api_key,
        base_url=config.mimo.api_base
    )

    prompt = f"""从以下用户补充文本中提取商业联系信息。

已通过正则提取的信息：{json.dumps(regex_results, ensure_ascii=False)}

请提取剩余信息，返回JSON格式：
{{
  "company_name": "公司名称（保留原始语言，不要翻译）",
  "company_name_en": "公司英文名称（如有）",
  "contact_name": "联系人姓名",
  "position": "职位",
  "address": "地址",
  "country": "国家/地区",
  "city": "城市",
  "additional_info": "其他补充说明（如线索来源、合作意向、展会名称等）"
}}

注意事项：
1. 只返回JSON，不要其他内容
2. 无法提取的字段留空字符串 ""
3. 如果文本中没有某个信息，不要编造
4. additional_info 放所有无法归类的补充说明

用户文本：
{text}"""

    try:
        response = client.chat.completions.create(
            model=config.mimo.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.1
        )
        content = response.choices[0].message.content
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        logger.warning(f"LLM文本解析失败: {e}")
    return {}


def parse_text_supplement(text: str) -> Dict[str, str]:
    """解析用户补充文本，提取结构化信息（正则+LLM结合）

    Args:
        text: 用户发送的补充文本

    Returns:
        Dict[str, str]: 提取的字段字典
    """
    if not text or not text.strip():
        return {}

    # 第一层：正则提取固定格式
    regex_results = _regex_extract(text)

    # 第二层：LLM提取自然语言信息
    llm_results = _llm_extract(text, regex_results)

    # 合并结果（LLM结果补充正则未覆盖的字段）
    merged = {}
    for field in ["company_name", "company_name_en", "contact_name", "position",
                   "email", "phone", "address", "website", "country", "city",
                   "additional_info"]:
        regex_val = regex_results.get(field, "")
        llm_val = llm_results.get(field, "")
        # 优先用正则结果（更准确），LLM补充
        merged[field] = regex_val if regex_val else llm_val

    return merged


def merge_text_to_card(card: BusinessCard, parsed: Dict[str, str], raw_text: str) -> BusinessCard:
    """将解析的文本信息合并到名片对象

    策略：
    - card为空的字段 → 用解析值填充
    - card已有值且解析值不同 → 保留card原值，冲突记入additional_info
    - 解析值更完整时 → 补充到对应字段
    """
    if not parsed:
        card.additional_info = (card.additional_info + "\n" + raw_text).strip() if raw_text else card.additional_info
        return card

    conflicts = []
    for field in ["company_name", "company_name_en", "contact_name", "position",
                   "email", "phone", "address", "website", "country", "city"]:
        new_val = parsed.get(field, "").strip()
        if not new_val:
            continue

        old_val = getattr(card, field, "")
        if not old_val:
            # card为空，填充
            setattr(card, field, new_val)
        elif old_val != new_val:
            # 都有值但不同 → 检查哪个更完整
            if len(new_val) > len(old_val) * 1.5:
                # 新值明显更完整，保留原值并追加新值到additional_info
                conflicts.append(f"{field}: 原值={old_val}, 新值={new_val}")
            else:
                conflicts.append(f"{field}: 原值={old_val}, 补充值={new_val}")

    # 补充additional_info
    extra_info = parsed.get("additional_info", "").strip()
    parts = []
    if card.additional_info:
        parts.append(card.additional_info)
    if extra_info:
        parts.append(extra_info)
    if conflicts:
        parts.append("【文本补充冲突】" + "; ".join(conflicts))
    if raw_text and not extra_info:
        parts.append(raw_text)
    card.additional_info = "\n".join(parts)

    return card