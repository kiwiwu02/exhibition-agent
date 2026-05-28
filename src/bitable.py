# src/bitable.py
import httpx
import logging
from typing import List, Optional, Dict
from .config import config
from .models import BusinessCard, CRMSession

logger = logging.getLogger(__name__)


class BitableClient:
    """飞书Bitable多维表格客户端"""

    def __init__(self):
        self.app_id = config.feishu.app_id
        self.app_secret = config.feishu.app_secret
        self.app_token = config.feishu.bitable_app_token
        self.table_id = config.feishu.bitable_table_id
        self.base_url = "https://open.feishu.cn/open-apis"
        self._tenant_access_token = None

    def get_tenant_access_token(self) -> Optional[str]:
        """获取tenant_access_token"""
        if self._tenant_access_token:
            return self._tenant_access_token

        try:
            response = httpx.post(
                f"{self.base_url}/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret
                }
            )
            data = response.json()

            if data.get("code") == 0:
                self._tenant_access_token = data.get("tenant_access_token")
                return self._tenant_access_token
            else:
                print(f"获取tenant_access_token失败: {data.get('msg')}")
                return None
        except Exception as e:
            print(f"获取tenant_access_token异常: {e}")
            return None

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        token = self.get_tenant_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def query_records(self, filter_condition: Optional[Dict] = None) -> List[CRMSession]:
        """查询Bitable记录（支持分页，获取全部记录）"""
        token = self.get_tenant_access_token()
        if not token:
            return []

        all_records = []
        page_token = None

        try:
            url = f"{self.base_url}/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"

            while True:
                params = {"page_size": 100}
                if page_token:
                    params["page_token"] = page_token
                if filter_condition:
                    params["filter"] = filter_condition

                response = httpx.get(
                    url,
                    headers=self._get_headers(),
                    params=params
                )
                data = response.json()

                if data.get("code") == 0:
                    items = data.get("data", {}).get("items", [])
                    all_records.extend([self.record_to_session(item) for item in items])

                    if data.get("data", {}).get("has_more"):
                        page_token = data["data"].get("page_token")
                    else:
                        break
                else:
                    print(f"查询记录失败: {data.get('msg')}")
                    break

            return all_records
        except Exception as e:
            print(f"查询记录异常: {e}")
            return []

    def create_record(self, card: BusinessCard) -> Optional[str]:
        """创建新记录"""
        token = self.get_tenant_access_token()
        if not token:
            return None

        try:
            url = f"{self.base_url}/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"
            fields = self.card_to_fields(card)

            response = httpx.post(
                url,
                headers=self._get_headers(),
                json={"fields": fields}
            )
            data = response.json()

            if data.get("code") == 0:
                record_id = data.get("data", {}).get("record", {}).get("record_id")
                return record_id
            else:
                print(f"创建记录失败: {data.get('msg')}")
                return None
        except Exception as e:
            print(f"创建记录异常: {e}")
            return None

    def update_record(self, record_id: str, fields: Dict) -> bool:
        """更新记录"""
        token = self.get_tenant_access_token()
        if not token:
            return False

        try:
            url = f"{self.base_url}/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}"

            logger.info(f"Bitable PUT {record_id} fields: {list(fields.keys())}")
            response = httpx.put(
                url,
                headers=self._get_headers(),
                json={"fields": fields}
            )
            data = response.json()

            if data.get("code") == 0:
                logger.info(f"Bitable 更新成功: {data}")
                return True
            else:
                logger.error(f"Bitable 更新失败: code={data.get('code')} msg={data.get('msg')}")
                return False
        except Exception as e:
            logger.error(f"Bitable 更新异常: {e}")
            return False

    def card_to_fields(self, card: BusinessCard) -> Dict:
        """将BusinessCard转换为Bitable字段 - 全部使用文本格式"""
        fields = {}

        if card.company_name:
            fields["公司名称"] = str(card.company_name)
        if card.contact_name:
            fields["联系人姓名"] = str(card.contact_name)
        if card.position:
            fields["职位"] = str(card.position)
        if card.email:
            fields["邮箱"] = str(card.email)
        if card.phone:
            phone = str(card.phone)
            # 处理电话号码格式：如果是列表字符串格式，提取所有号码用逗号分隔
            if phone.startswith("[") and phone.endswith("]"):
                try:
                    import ast
                    phone_list = ast.literal_eval(phone)
                    if isinstance(phone_list, list) and phone_list:
                        cleaned = []
                        for p in phone_list:
                            p = str(p).strip()
                            # 清理括号中的说明文字
                            if "(" in p:
                                p = p.split("(")[0].strip()
                            if p:
                                cleaned.append(p)
                        phone = ", ".join(cleaned) if cleaned else phone
                except (ValueError, SyntaxError):
                    pass
            fields["电话"] = phone
        if card.address:
            fields["公司地址"] = str(card.address)
        if card.website:
            # 官网字段在Bitable中是URL类型，需要特殊格式
            website = str(card.website)
            if not website.startswith(('http://', 'https://')):
                website = 'https://' + website
            fields["官网"] = {"link": website, "text": str(card.website)}
        if card.country:
            fields["国家/地区"] = str(card.country)
        if card.region:
            fields["区域"] = str(card.region)
        if card.city:
            fields["城市"] = str(card.city)
        if card.additional_info:
            fields["补充信息"] = str(card.additional_info)

        return fields

    def update_report_url(self, record_id: str, report_url: str) -> bool:
        """更新调研报告链接"""
        # 使用 URL 类型格式（与"官网"字段相同）
        return self.update_record(record_id, {"背调报告链接": report_url})

    def update_sharing_settings(self) -> bool:
        """更新分享设置，允许组织内所有人可编辑"""
        token = self.get_tenant_access_token()
        if not token:
            return False

        try:
            # 使用Drive API更新权限设置
            url = f"{self.base_url}/drive/v1/permissions/{self.app_token}/public"
            params = {"type": "bitable"}

            payload = {
                "external_access_entity": "open",
                "security_entity": "anyone_can_view",
                "comment_entity": "anyone_can_view",
                "share_entity": "anyone",
                "manage_collaborator_entity": "collaborator_can_manage",
                "link_share_entity": "tenant_editable"
            }

            response = httpx.patch(
                url,
                headers=self._get_headers(),
                params=params,
                json=payload
            )
            data = response.json()

            if data.get("code") == 0:
                print("分享设置更新成功：组织内所有人可编辑")
                return True
            else:
                print(f"更新分享设置失败: {data.get('msg')}")
                return False
        except Exception as e:
            print(f"更新分享设置异常: {e}")
            return False

    def add_report_url_field(self) -> bool:
        """添加报告链接字段到Bitable"""
        token = self.get_tenant_access_token()
        if not token:
            return False

        try:
            url = f"{self.base_url}/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/fields"

            payload = {
                "field_name": "背调报告链接",
                "type": 1  # 1 = 文本类型（与实际字段一致）
            }

            response = httpx.post(
                url,
                headers=self._get_headers(),
                json=payload
            )
            data = response.json()

            if data.get("code") == 0:
                print("背调报告链接字段添加成功")
                return True
            else:
                print(f"添加字段失败: {data.get('msg')}")
                return False
        except Exception as e:
            print(f"添加字段异常: {e}")
            return False

    def record_to_session(self, record: Dict) -> CRMSession:
        """将Bitable记录转换为CRMSession"""
        fields = record.get("fields", {})

        return CRMSession(
            record_id=record.get("record_id", ""),
            company_name=fields.get("公司名称", ""),
            company_name_en="",
            contact_name=fields.get("联系人姓名", ""),
            position=fields.get("职位", ""),
            email=fields.get("邮箱", ""),
            phone=fields.get("电话", ""),
            address=fields.get("公司地址", ""),
            website=fields.get("官网", ""),
            country=fields.get("国家/地区", ""),
            region=fields.get("区域", ""),
            city=fields.get("城市", ""),
            additional_info=fields.get("补充信息", ""),
            report_url=fields.get("背调报告链接", ""),
        )

    def get_existing_sessions(self) -> List[CRMSession]:
        """获取所有现有记录（用于重复检测）"""
        return self.query_records()


# 便捷函数
def get_bitable_client() -> BitableClient:
    """获取Bitable客户端实例"""
    return BitableClient()


def save_card_to_bitable(card: BusinessCard) -> Optional[str]:
    """保存名片到Bitable"""
    client = get_bitable_client()
    return client.create_record(card)


def query_all_records() -> List[CRMSession]:
    """查询所有记录"""
    client = get_bitable_client()
    return client.query_records()


def update_record_fields(record_id: str, fields: Dict) -> bool:
    """更新记录字段"""
    client = get_bitable_client()
    return client.update_record(record_id, fields)


def update_bitable_sharing() -> bool:
    """更新Bitable分享设置，允许组织内所有人可编辑"""
    client = get_bitable_client()
    return client.update_sharing_settings()


def add_report_url_field() -> bool:
    """添加背调报告链接字段"""
    client = get_bitable_client()
    return client.add_report_url_field()
