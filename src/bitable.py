# src/bitable.py
import httpx
from typing import List, Optional, Dict
from .config import config
from .models import BusinessCard, CRMSession


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
        """查询Bitable记录"""
        token = self.get_tenant_access_token()
        if not token:
            return []

        try:
            url = f"{self.base_url}/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"
            params = {"page_size": 100}

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
                return [self.record_to_session(item) for item in items]
            else:
                print(f"查询记录失败: {data.get('msg')}")
                return []
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

            response = httpx.put(
                url,
                headers=self._get_headers(),
                json={"fields": fields}
            )
            data = response.json()

            if data.get("code") == 0:
                return True
            else:
                print(f"更新记录失败: {data.get('msg')}")
                return False
        except Exception as e:
            print(f"更新记录异常: {e}")
            return False

    def card_to_fields(self, card: BusinessCard) -> Dict:
        """将BusinessCard转换为Bitable字段"""
        fields = {}

        if card.company_name:
            fields["公司名称"] = card.company_name
        if card.company_name_en:
            fields["公司别名"] = card.company_name_en
        if card.company_alias:
            fields["公司别名"] = card.company_alias
        if card.contact_name:
            fields["联系人姓名"] = card.contact_name
        if card.position:
            fields["职位"] = card.position
        if card.email:
            fields["邮箱"] = card.email
        if card.phone:
            fields["电话"] = card.phone
        if card.address:
            fields["公司地址"] = card.address
        if card.website:
            fields["官网"] = card.website
        if card.country:
            fields["国家/地区"] = card.country
        if card.region:
            fields["区域"] = card.region
        if card.city:
            fields["城市"] = card.city
        if card.additional_info:
            fields["补充信息"] = card.additional_info

        return fields

    def record_to_session(self, record: Dict) -> CRMSession:
        """将Bitable记录转换为CRMSession"""
        fields = record.get("fields", {})

        return CRMSession(
            record_id=record.get("record_id", ""),
            company_name=fields.get("公司名称", ""),
            contact_name=fields.get("联系人姓名", ""),
            email=fields.get("邮箱", ""),
            phone=fields.get("电话", "")
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
