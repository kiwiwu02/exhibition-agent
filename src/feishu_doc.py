# src/feishu_doc.py
import httpx
import logging
from typing import Optional
from .config import config

logger = logging.getLogger(__name__)

class FeishuDocClient:
    """飞书文档客户端"""

    def __init__(self):
        self.app_id = config.feishu.app_id
        self.app_secret = config.feishu.app_secret
        self.base_url = "https://open.feishu.cn/open-apis"
        self.tenant_token = None

    def _get_tenant_token(self) -> str:
        """获取tenant_access_token"""
        if self.tenant_token:
            return self.tenant_token

        try:
            response = httpx.post(
                f"{self.base_url}/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret
                }
            )
            response.raise_for_status()
            data = response.json()
            self.tenant_token = data.get("tenant_access_token")
            return self.tenant_token
        except Exception as e:
            logger.error(f"获取tenant_token失败: {e}")
            raise

    def _get_headers(self) -> dict:
        """获取请求头"""
        token = self._get_tenant_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def create_document(self, title: str, content: str) -> Optional[str]:
        """创建飞书文档并返回文档链接"""
        try:
            # 创建文档
            response = httpx.post(
                f"{self.base_url}/docx/v1/documents",
                headers=self._get_headers(),
                json={"title": title}
            )
            response.raise_for_status()
            data = response.json()
            # 飞书API返回格式: data.document.document_id
            document_id = data.get("data", {}).get("document", {}).get("document_id")

            if not document_id:
                logger.error("创建文档失败：未获取到document_id")
                return None

            # 写入内容（简化版，实际需要根据飞书API格式化）
            # 这里先返回文档链接
            doc_url = f"https://feishu.cn/docx/{document_id}"
            logger.info(f"创建文档成功: {doc_url}")
            return doc_url

        except Exception as e:
            logger.error(f"创建文档失败: {e}")
            return None

    def generate_report(self, company_name: str, report_data: dict) -> Optional[str]:
        """生成调研报告文档"""
        title = f"{company_name} 公司调研报告"

        # 构建报告内容
        content = f"""# {company_name} 公司调研报告

## 基本信息
- 公司名称：{company_name}
- 国家/地区：{report_data.get('country', '未知')}
- 城市：{report_data.get('city', '未知')}

## 基本面与赛道定位
- 主营业务：{report_data.get('main_business', '待补充')}
- 行业地位：{report_data.get('industry_position', '待补充')}

## 规模与健康度
- 公司规模：{report_data.get('company_size', '待补充')}
- 信用评级：{report_data.get('credit_rating', '待评估')}

## 近期动态
{report_data.get('recent_news', '暂无近期动态')}

## 信息来源
{report_data.get('sources', '暂无信息来源')}

## 信息可信度
- 基本信息：★★★★☆
- 财务信息：★★☆☆☆
- 人员信息：★★★☆☆
"""

        return self.create_document(title, content)
