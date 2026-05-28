# src/agent.py
import logging
from typing import Dict, Optional
from .card_recognizer import recognize_business_card, parse_text_supplement, merge_text_to_card
from .duplicate_checker import check_duplicate, merge_card_to_record, DuplicateResult
from .bitable import get_bitable_client, save_card_to_bitable, query_all_records, update_record_fields
from .feishu_doc import FeishuDocClient
from .models import BusinessCard, CRMSession
from .agents.supervisor import SupervisorAgent

logger = logging.getLogger(__name__)


class ExhibitionAgent:
    """海外展会线索录入Agent"""

    def __init__(self):
        self.bitable_client = get_bitable_client()
        self.doc_client = FeishuDocClient()
        self.supervisor = SupervisorAgent()

    def process_card(self, image_path: str, text_info: str = "", on_progress=None) -> Dict:
        """处理名片图片

        流程：
        1. OCR识别名片
        2. 智能解析文本补充信息
        3. 查询CRM全部记录
        4. 重复检测与分类
        5. 根据决策执行（创建/合并/询问用户）
        6. 背调
        """
        try:
            # 1. 识别名片
            logger.info(f"开始识别名片: {image_path}")
            card = recognize_business_card(image_path)

            # 2. 智能解析文本补充
            if text_info:
                logger.info("解析文本补充信息...")
                parsed = parse_text_supplement(text_info)
                card = merge_text_to_card(card, parsed, text_info)

            # 3. 查询全部CRM记录（分页）
            existing_records = query_all_records()

            # 4. 重复检测与分类
            dup_result = check_duplicate(card, existing_records)

            # 5. 根据决策执行
            if dup_result.action == "ask_user":
                # 返回重复信息，让用户在飞书中选择
                return {
                    "success": True,
                    "action": "ask_duplicate",
                    "card": card,
                    "duplicate_info": dup_result,
                    "existing_records_count": len(existing_records),
                }
            elif dup_result.action == "create_new_contact":
                # 同公司新联系人，创建新记录
                record_id = save_card_to_bitable(card)
                return {
                    "success": True,
                    "action": "created_new_contact",
                    "record_id": record_id,
                    "card": card,
                    "duplicate_info": dup_result,
                    "background_result": self._perform_background_check(card, record_id, on_progress),
                }
            else:
                # 全新记录，创建
                record_id = save_card_to_bitable(card)
                return {
                    "success": True,
                    "action": "created",
                    "record_id": record_id,
                    "card": card,
                    "duplicate_info": dup_result,
                    "background_result": self._perform_background_check(card, record_id, on_progress),
                }

        except Exception as e:
            logger.error(f"处理名片失败: {e}")
            return {"success": False, "error": str(e)}

    def handle_duplicate_decision(
        self, card: BusinessCard, dup_result: DuplicateResult, decision: str
    ) -> Dict:
        """处理用户对重复记录的决策

        Args:
            card: 新名片数据
            dup_result: 重复检测结果
            decision: "merge" 或 "create"
        """
        try:
            if decision == "merge":
                # 合并到已有记录
                existing = dup_result.matched_record
                if not existing:
                    return {"success": False, "error": "未找到匹配的已有记录"}

                updates, conflicts = merge_card_to_record(card, existing)
                if updates:
                    update_record_fields(dup_result.matched_record_id, updates)

                return {
                    "success": True,
                    "action": "merged",
                    "record_id": dup_result.matched_record_id,
                    "updated_fields": list(updates.keys()),
                    "conflicts": conflicts,
                    "card": card,
                }
            else:
                # 创建新记录
                record_id = save_card_to_bitable(card)
                return {
                    "success": True,
                    "action": "created",
                    "record_id": record_id,
                    "card": card,
                    "background_result": self._perform_background_check(card, record_id),
                }
        except Exception as e:
            logger.error(f"处理重复决策失败: {e}")
            return {"success": False, "error": str(e)}

    def _perform_background_check(self, card: BusinessCard, record_id: str, on_progress=None) -> Dict:
        """执行背调（使用Multi-Agent系统）"""
        def _notify(step, msg):
            if on_progress:
                on_progress(step, msg)

        # 自动发现公司名（当 OCR 未能提取时）
        if not card.company_name and not card.company_name_en:
            logger.info(f"公司名为空，尝试自动发现。卡片字段: email={card.email}, website={card.website}, contact={card.contact_name}, phone={card.phone}, address={card.address}")
            _notify("discovery", "🔍 正在通过其他信息发现公司名...")
            from .company_discovery import discover_company_name
            cn, cn_en, source = discover_company_name(card)
            if cn:
                card.company_name = cn
                if cn_en:
                    card.company_name_en = cn_en
                logger.info(f"自动发现公司名: {cn} (来源: {source})")
                # 立即更新 Bitable
                try:
                    update_record_fields(record_id, {"公司名称": cn})
                except Exception as e:
                    logger.warning(f"更新 Bitable 公司名失败: {e}")
            else:
                logger.warning("自动发现公司名失败，将尝试用已有字段继续调研")

        logger.info(f"开始背调: company={card.company_name}, record_id={record_id}")
        try:
            _notify("research_start", "🔍 开始公司背调...")
            report = self.supervisor.research(card, on_progress=on_progress)

            report_data = {
                "basic_info": report.basic_info,
                "business_track": report.business_track,
                "financial_health": report.financial_health,
                "org_structure": report.org_structure,
                "news_reputation": report.news_reputation,
                "supply_chain": report.supply_chain,
                "sales_opportunity": report.sales_opportunity,
                "full_report_content": report.full_report_content,
                "sources": report.sources
            }

            _notify("doc_gen", "📄 文档生成 Agent 正在写入飞书文档...")
            report_url = self.doc_client.generate_research_report(
                card.company_name, report_data
            )
            logger.info(f"报告生成完成, URL: {report_url}")

            # 写入报告链接
            if report_url and record_id:
                logger.info(f"写入报告链接到 Bitable: record_id={record_id}, url={report_url}")
                update_record_fields(record_id, {"背调报告链接": report_url})
            else:
                logger.warning(f"跳过报告链接写入: report_url={report_url}, record_id={record_id}")

            # 写入 CRM 补充字段到 Bitable
            if record_id and report.crm_supplements:
                # URL 类型字段需要特殊格式
                formatted = {}
                for k, v in report.crm_supplements.items():
                    if k == "官网" and v:
                        url = v if v.startswith(("http://", "https://")) else f"https://{v}"
                        formatted[k] = {"link": url, "text": v}
                    else:
                        formatted[k] = v
                logger.info(f"写入 CRM 补充字段: {list(formatted.keys())}")
                update_record_fields(record_id, formatted)

            # 如果公司名在调研过程中被发现（如 BasicInfoAgent），补写到 Bitable
            if record_id and card.company_name:
                try:
                    update_record_fields(record_id, {"公司名称": card.company_name})
                except Exception as e:
                    logger.warning(f"补写公司名到 Bitable 失败: {e}")

            _notify("done", "✅ 背调完成！")
            return {"success": True, "report_url": report_url, "report": report}

        except Exception as e:
            logger.error(f"背调失败: {e}")
            return {"success": False, "error": str(e)}

    def format_response(self, result: Dict) -> dict:
        """格式化回复消息为飞书卡片"""
        if not result.get("success"):
            return self._error_card(result.get("error", "未知错误"))

        action = result.get("action", "created")
        card = result.get("card")
        dup_info = result.get("duplicate_info")

        if action == "ask_duplicate":
            return self._duplicate_card(dup_info)

        if action == "merged":
            return self._merged_card(result)

        return self._created_card(card, dup_info, result)

    def _error_card(self, error: str) -> dict:
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "❌ 处理失败"},
                "template": "red"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"错误信息：{error}"}}
            ]
        }

    def _duplicate_card(self, dup_info) -> dict:
        matched = dup_info.matched_record if dup_info else None
        lines = []
        if matched:
            lines.append(f"**公司**：{matched.company_name}")
            lines.append(f"**联系人**：{matched.contact_name}")
            lines.append(f"**邮箱**：{matched.email}")
        if dup_info and dup_info.reason:
            lines.append(f"\n**匹配原因**：{dup_info.reason}")
        lines.append("\n请回复：\n- 「合并」→ 将新信息合并到已有记录\n- 「新建」→ 忽略重复，创建新记录")

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🔍 检测到已有相似记录"},
                "template": "orange"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}}
            ]
        }

    def _merged_card(self, result: dict) -> dict:
        updated = result.get("updated_fields", [])
        conflicts = result.get("conflicts", [])
        lines = [f"已合并到已有记录"]
        if updated:
            lines.append(f"**补充了**：{', '.join(updated)}")
        if conflicts:
            lines.append(f"**冲突字段（保留原值）**：{', '.join(conflicts)}")

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "✅ 合并完成"},
                "template": "green"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}}
            ]
        }

    def _created_card(self, card, dup_info, result: dict) -> dict:
        # 公司和联系人信息
        info_lines = [
            f"**公司**：{card.company_name}",
            f"**联系人**：{card.contact_name}",
        ]
        if dup_info and dup_info.action == "create_new_contact":
            info_lines.append("（该公司已有其他联系人记录）")

        # 详细字段
        detail_lines = []
        if card.position:
            detail_lines.append(f"- 职位：{card.position}")
        if card.email:
            detail_lines.append(f"- 邮箱：{card.email}")
        if card.phone:
            detail_lines.append(f"- 电话：{card.phone}")
        if card.country:
            detail_lines.append(f"- 国家/地区：{card.country}")

        elements = [
            {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(info_lines)}},
        ]
        if detail_lines:
            elements.append({"tag": "hr"})
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(detail_lines)}})

        # 调研报告链接
        bg_result = result.get("background_result", {})
        if bg_result and bg_result.get("success") and bg_result.get("report_url"):
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "action",
                "actions": [{
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "📄 查看调研报告"},
                    "url": bg_result["report_url"],
                    "type": "primary"
                }]
            })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📋 名片处理完成"},
                "template": "green"
            },
            "elements": elements
        }
