# src/agent.py
import logging
import os
from typing import Dict, Optional
from .card_recognizer import recognize_business_card
from .duplicate_checker import check_duplicate
from .bitable import get_bitable_client, save_card_to_bitable, query_all_records
from .background_checker import search_company_info
from .feishu_doc import FeishuDocClient
from .models import BusinessCard, CRMSession

logger = logging.getLogger(__name__)

class ExhibitionAgent:
    """海外展会线索录入Agent"""

    def __init__(self):
        self.bitable_client = get_bitable_client()
        self.doc_client = FeishuDocClient()

    def process_card(self, image_path: str, text_info: str = "") -> Dict:
        """处理名片图片"""
        try:
            # 1. 识别名片
            logger.info(f"开始识别名片: {image_path}")
            card = recognize_business_card(image_path)

            # 2. 合并文本信息
            if text_info:
                card.additional_info = text_info

            # 3. 检测重复
            existing_records = query_all_records()
            duplicate_result = check_duplicate(card, existing_records)

            # 4. 写入Bitable
            record_id = save_card_to_bitable(card)

            # 5. 触发背调（异步）
            background_result = self._perform_background_check(card)

            return {
                "success": True,
                "record_id": record_id,
                "card": card,
                "is_duplicate": duplicate_result.get("is_duplicate", False),
                "duplicate_info": duplicate_result,
                "background_result": background_result
            }

        except Exception as e:
            logger.error(f"处理名片失败: {e}")
            return {"success": False, "error": str(e)}

    def _perform_background_check(self, card: BusinessCard) -> Dict:
        """执行背调"""
        try:
            # 搜索公司信息
            search_result = search_company_info(
                card.company_name,
                card.country
            )

            # 生成报告
            report_data = {
                "country": card.country,
                "city": card.city,
                "main_business": search_result.get("basic_info", {}).get("answer", "待补充"),
                "company_size": "待补充",
                "credit_rating": "待评估",
                "recent_news": str(search_result.get("recent_news", [])),
                "sources": str(search_result.get("sources", []))
            }

            report_url = self.doc_client.generate_report(
                card.company_name,
                report_data
            )

            return {
                "success": True,
                "report_url": report_url,
                "search_result": search_result
            }

        except Exception as e:
            logger.error(f"背调失败: {e}")
            return {"success": False, "error": str(e)}

    def format_response(self, result: Dict) -> str:
        """格式化回复消息"""
        if not result.get("success"):
            return f"处理失败: {result.get('error', '未知错误')}"

        card = result.get("card")
        is_duplicate = result.get("is_duplicate", False)

        response = f"""名片识别成功！

公司信息：
- 公司名称：{card.company_name}
- 联系人：{card.contact_name}
- 职位：{card.position}
- 邮箱：{card.email}
- 电话：{card.phone}
- 国家/地区：{card.country}
- 城市：{card.city}
"""

        if is_duplicate:
            dup_info = result.get("duplicate_info", {})
            response += f"\n检测到可能重复的记录：{dup_info.get('reason', '')}"

        bg_result = result.get("background_result", {})
        if bg_result.get("success") and bg_result.get("report_url"):
            response += f"\n\n调研报告：{bg_result['report_url']}"

        return response
