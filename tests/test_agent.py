# tests/test_agent.py
import pytest
from unittest.mock import patch, MagicMock
from src.agent import ExhibitionAgent
from src.models import BusinessCard

def test_agent_init():
    """测试Agent初始化"""
    agent = ExhibitionAgent()
    assert agent is not None
    assert agent.bitable_client is not None
    assert agent.doc_client is not None

@patch('src.agent.recognize_business_card')
@patch('src.agent.query_all_records')
@patch('src.agent.save_card_to_bitable')
def test_process_card(mock_save, mock_query, mock_recognize):
    """测试处理名片流程"""
    # 设置mock
    mock_recognize.return_value = BusinessCard(
        company_name="Test Corp",
        contact_name="John",
        email="john@test.com"
    )
    mock_query.return_value = []
    mock_save.return_value = "record_123"

    agent = ExhibitionAgent()
    result = agent.process_card("test.jpg", "测试文本")

    assert result["success"] == True
    assert result["record_id"] == "record_123"
    assert result["card"].company_name == "Test Corp"
    assert result["card"].additional_info == "测试文本"

@patch('src.agent.recognize_business_card')
@patch('src.agent.query_all_records')
@patch('src.agent.save_card_to_bitable')
@patch('src.agent.search_company_info')
def test_process_card_with_background_check(mock_search, mock_save, mock_query, mock_recognize):
    """测试包含背调的名片处理"""
    mock_recognize.return_value = BusinessCard(
        company_name="Test Corp",
        contact_name="John",
        email="john@test.com",
        country="USA"
    )
    mock_query.return_value = []
    mock_save.return_value = "record_123"
    mock_search.return_value = {
        "basic_info": {"answer": "Tech company"},
        "sources": ["https://example.com"]
    }

    agent = ExhibitionAgent()
    result = agent.process_card("test.jpg")

    assert result["success"] == True
    assert "background_result" in result

@patch('src.agent.recognize_business_card')
@patch('src.agent.query_all_records')
@patch('src.agent.save_card_to_bitable')
def test_process_card_duplicate_detected(mock_save, mock_query, mock_recognize):
    """测试重复检测"""
    mock_recognize.return_value = BusinessCard(
        company_name="Test Corp",
        contact_name="John",
        email="john@test.com"
    )
    # 模拟已存在相同邮箱的记录
    mock_query.return_value = [
        MagicMock(
            record_id="existing_123",
            company_name="Test Corp",
            contact_name="John",
            email="john@test.com",
            phone=""
        )
    ]
    mock_save.return_value = "record_456"

    agent = ExhibitionAgent()
    result = agent.process_card("test.jpg")

    assert result["success"] == True
    assert result["is_duplicate"] == True
    assert result["duplicate_info"]["reason"] == "邮箱完全匹配"

def test_format_response_success():
    """测试格式化成功响应"""
    agent = ExhibitionAgent()
    result = {
        "success": True,
        "card": BusinessCard(
            company_name="Test Corp",
            contact_name="John",
            position="Manager",
            email="john@test.com",
            phone="+1234567890",
            country="USA",
            city="New York"
        ),
        "is_duplicate": False,
        "background_result": {"success": True, "report_url": "https://feishu.cn/docx/123"}
    }

    response = agent.format_response(result)

    assert "Test Corp" in response
    assert "John" in response
    assert "john@test.com" in response
    assert "https://feishu.cn/docx/123" in response

def test_format_response_failure():
    """测试格式化失败响应"""
    agent = ExhibitionAgent()
    result = {"success": False, "error": "识别失败"}

    response = agent.format_response(result)

    assert "处理失败" in response
    assert "识别失败" in response

def test_agent_with_multi_agent():
    """测试Multi-Agent系统集成"""
    agent = ExhibitionAgent()
    card = BusinessCard(company_name="Test Corp", country="USA")

    with patch.object(agent.supervisor, 'research') as mock_research:
        mock_report = MagicMock()
        mock_report.company_name = "Test Corp"
        mock_report.basic_info = "Basic info"
        mock_report.sources = ["https://example.com"]
        mock_research.return_value = mock_report

        with patch.object(agent.doc_client, 'generate_research_report') as mock_doc:
            mock_doc.return_value = "https://feishu.cn/docx/test"

            result = agent._perform_background_check(card)

            assert result["success"] == True
            assert "report_url" in result
