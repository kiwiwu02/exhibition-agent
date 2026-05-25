# tests/test_card_recognizer.py
import pytest
import os
from src.card_recognizer import recognize_business_card
from src.models import BusinessCard

def test_recognize_business_card_signature():
    """测试名片识别函数是否返回正确的数据结构"""
    import inspect
    sig = inspect.signature(recognize_business_card)
    assert "image_path" in sig.parameters


def test_recognize_business_card_file_not_found():
    """测试文件不存在时抛出FileNotFoundError"""
    with pytest.raises(FileNotFoundError, match="名片图片文件不存在"):
        recognize_business_card("/nonexistent/path/image.jpg")


def test_parse_valid_json():
    """测试解析有效JSON"""
    from src.card_recognizer import parse_recognition_result
    test_json = '''
    {
        "company_name": "测试公司",
        "contact_name": "张三",
        "email": "zhangsan@test.com",
        "phone": "+86-13800138000"
    }
    '''
    result = parse_recognition_result(test_json)
    assert isinstance(result, BusinessCard)
    assert result.company_name == "测试公司"
    assert result.contact_name == "张三"
    assert result.email == "zhangsan@test.com"
    assert result.phone == "+86-13800138000"


def test_parse_invalid_json():
    """测试解析无效JSON返回空BusinessCard"""
    from src.card_recognizer import parse_recognition_result
    result = parse_recognition_result("这不是有效的JSON内容")
    assert isinstance(result, BusinessCard)
    assert result.company_name == ""
    assert result.contact_name == ""


def test_parse_empty_input():
    """测试解析空输入返回空BusinessCard"""
    from src.card_recognizer import parse_recognition_result
    result = parse_recognition_result("")
    assert isinstance(result, BusinessCard)
    assert result.company_name == ""
    assert result.contact_name == ""