import pytest
from unittest.mock import patch, MagicMock
import httpx
from src.feishu_doc import FeishuDocClient

def test_feishu_doc_client_init():
    client = FeishuDocClient()
    assert client is not None

@patch('src.feishu_doc.httpx.post')
def test_feishu_doc_client_create_document(mock_post):
    # 模拟获取tenant_token的响应
    token_response = MagicMock()
    token_response.raise_for_status.return_value = None
    token_response.json.return_value = {"tenant_access_token": "test_token"}

    # 模拟创建文档的响应
    doc_response = MagicMock()
    doc_response.raise_for_status.return_value = None
    doc_response.json.return_value = {"data": {"document_id": "doc123"}}

    # 设置mock_post的side_effect，根据URL返回不同的响应
    def side_effect(*args, **kwargs):
        if "auth/v3/tenant_access_token/internal" in args[0]:
            return token_response
        elif "docx/v1/documents" in args[0]:
            return doc_response
        else:
            return MagicMock()

    mock_post.side_effect = side_effect

    client = FeishuDocClient()
    result = client.create_document("测试报告", "# 测试报告\n\n这是测试内容")
    assert result == "https://feishu.cn/docx/doc123"

def test_generate_research_report():
    client = FeishuDocClient()
    report_data = {
        "basic_info": "Basic company info",
        "business_track": "Business track info",
        "financial_health": "Financial health info",
        "org_structure": "Org structure info",
        "news_reputation": "News reputation info",
        "sources": ["https://example.com"]
    }

    with patch.object(client, 'create_document') as mock_create:
        mock_create.return_value = "https://feishu.cn/docx/test123"
        result = client.generate_research_report("Test Corp", report_data)
        assert result == "https://feishu.cn/docx/test123"
