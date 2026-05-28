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
    doc_response.json.return_value = {"data": {"document": {"document_id": "doc123"}}}

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


def test_parse_inline_format_no_bold():
    """测试无粗体标记的文本"""
    client = FeishuDocClient()
    elements = client._parse_inline_format("普通文本")
    assert len(elements) == 1
    assert elements[0]["text_run"]["content"] == "普通文本"
    assert "text_element_style" not in elements[0]["text_run"]


def test_parse_inline_format_single_bold():
    """测试单个粗体标记"""
    client = FeishuDocClient()
    elements = client._parse_inline_format("公司规模：**100-500人**")
    assert len(elements) == 2
    assert elements[0]["text_run"]["content"] == "公司规模："
    assert elements[1]["text_run"]["content"] == "100-500人"
    assert elements[1]["text_run"]["text_element_style"]["bold"] is True


def test_parse_inline_format_multiple_bold():
    """测试多个粗体标记"""
    client = FeishuDocClient()
    elements = client._parse_inline_format("**A** 和 **B**")
    assert len(elements) == 3
    assert elements[0]["text_run"]["content"] == "A"
    assert elements[0]["text_run"]["text_element_style"]["bold"] is True
    assert elements[1]["text_run"]["content"] == " 和 "
    assert elements[2]["text_run"]["content"] == "B"
    assert elements[2]["text_run"]["text_element_style"]["bold"] is True


def test_create_heading_block():
    """测试飞书原生标题块"""
    client = FeishuDocClient()

    block = client._create_heading_block("测试标题", level=1)
    assert block["block_type"] == 3
    assert "heading1" in block
    assert block["heading1"]["elements"][0]["text_run"]["content"] == "测试标题"

    block = client._create_heading_block("二级标题", level=2)
    assert block["block_type"] == 4
    assert "heading2" in block

    block = client._create_heading_block("三级标题", level=3)
    assert block["block_type"] == 5
    assert "heading3" in block


def test_create_heading_block_with_bold():
    """测试标题块中的内联粗体"""
    client = FeishuDocClient()
    block = client._create_heading_block("公司：**Test Corp**", level=2)
    assert block["block_type"] == 4
    elements = block["heading2"]["elements"]
    assert len(elements) == 2
    assert elements[1]["text_run"]["text_element_style"]["bold"] is True


def test_create_bullet_block():
    """测试飞书原生无序列表块"""
    client = FeishuDocClient()
    block = client._create_bullet_block("列表项")
    assert block["block_type"] == 12
    assert "bullet" in block
    assert block["bullet"]["elements"][0]["text_run"]["content"] == "列表项"


def test_create_bullet_block_with_bold():
    """测试列表块中的内联粗体"""
    client = FeishuDocClient()
    block = client._create_bullet_block("**关键**信息")
    elements = block["bullet"]["elements"]
    assert len(elements) == 2
    assert elements[0]["text_run"]["text_element_style"]["bold"] is True


def test_create_divider_block():
    """测试飞书原生分割线块"""
    client = FeishuDocClient()
    block = client._create_divider_block()
    assert block["block_type"] == 22
    assert "divider" in block


def test_create_text_block():
    """测试文本块"""
    client = FeishuDocClient()
    block = client._create_text_block("普通文本")
    assert block["block_type"] == 2
    assert "text" in block


def test_create_text_block_with_bold():
    """测试文本块中的内联粗体"""
    client = FeishuDocClient()
    block = client._create_text_block("规模：**500人**")
    elements = block["text"]["elements"]
    assert len(elements) == 2
    assert elements[1]["text_run"]["text_element_style"]["bold"] is True


def test_parse_markdown_to_blocks():
    """测试完整 markdown 解析"""
    client = FeishuDocClient()
    markdown = "# 一级标题\n## 二级标题\n### 三级标题\n- 列表项1\n- 列表项2\n普通文本\n---"
    blocks = client._parse_markdown_to_blocks(markdown)

    assert len(blocks) == 7
    assert blocks[0]["block_type"] == 3  # heading1
    assert blocks[1]["block_type"] == 4  # heading2
    assert blocks[2]["block_type"] == 5  # heading3
    assert blocks[3]["block_type"] == 12  # bullet
    assert blocks[4]["block_type"] == 12  # bullet
    assert blocks[5]["block_type"] == 2   # text
    assert blocks[6]["block_type"] == 22  # divider


def test_generate_research_report_with_full_content():
    """测试使用 full_report_content 生成报告"""
    client = FeishuDocClient()
    full_content = "# Test Corp 公司调研报告\n\n## 1. 基础信息\n\n测试内容\n"
    report_data = {
        "full_report_content": full_content,
        "basic_info": "Basic info",
        "sources": ["https://example.com"]
    }

    with patch.object(client, 'create_document') as mock_create:
        mock_create.return_value = "https://feishu.cn/docx/test123"
        result = client.generate_research_report("Test Corp", report_data)
        assert result == "https://feishu.cn/docx/test123"
        # 验证传给 create_document 的内容是 full_report_content
        call_args = mock_create.call_args
        assert call_args[0][1] == full_content


def test_generate_research_report_fallback():
    """测试 fallback 模板（无 full_report_content）"""
    client = FeishuDocClient()
    report_data = {
        "basic_info": "Basic info",
        "business_track": "Business track",
        "sources": ["https://example.com"]
    }

    with patch.object(client, 'create_document') as mock_create:
        mock_create.return_value = "https://feishu.cn/docx/test123"
        result = client.generate_research_report("Test Corp", report_data)
        assert result == "https://feishu.cn/docx/test123"
        # 验证 fallback 内容包含标题
        call_args = mock_create.call_args
        assert "Test Corp" in call_args[0][1]
