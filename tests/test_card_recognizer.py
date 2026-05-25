# tests/test_card_recognizer.py
import pytest
from src.card_recognizer import recognize_business_card
from src.models import BusinessCard

def test_recognize_business_card():
    """测试名片识别函数是否返回正确的数据结构"""
    # 注意：这个测试需要有效的图片文件和API密钥
    # 在实际使用中，可以创建一个测试图片文件进行测试
    # 这里我们测试函数签名和返回类型
    import inspect
    sig = inspect.signature(recognize_business_card)
    assert "image_path" in sig.parameters

    # 测试parse_recognition_result函数
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