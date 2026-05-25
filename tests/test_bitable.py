# tests/test_bitable.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.bitable import BitableClient
from src.models import BusinessCard, CRMSession
from src.config import config


class TestBitableClient:
    """Bitable客户端测试"""

    def setup_method(self):
        """测试前设置"""
        # 设置测试配置
        config.feishu.app_id = "test_app_id"
        config.feishu.app_secret = "test_app_secret"
        config.feishu.bitable_app_token = "test_app_token"
        config.feishu.bitable_table_id = "test_table_id"

    def test_init_client(self):
        """测试初始化客户端"""
        client = BitableClient()
        assert client.app_token == "test_app_token"
        assert client.table_id == "test_table_id"

    @patch('src.bitable.httpx')
    def test_get_tenant_access_token_success(self, mock_httpx):
        """测试获取tenant_access_token成功"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token_123"
        }
        mock_httpx.post.return_value = mock_response

        client = BitableClient()
        token = client.get_tenant_access_token()

        assert token == "test_token_123"
        mock_httpx.post.assert_called_once()

    @patch('src.bitable.httpx')
    def test_get_tenant_access_token_failure(self, mock_httpx):
        """测试获取tenant_access_token失败"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 10003,
            "msg": "invalid app_id"
        }
        mock_httpx.post.return_value = mock_response

        client = BitableClient()
        token = client.get_tenant_access_token()

        assert token is None

    @patch.object(BitableClient, 'get_tenant_access_token')
    @patch('src.bitable.httpx')
    def test_query_records_success(self, mock_httpx, mock_get_token):
        """测试查询记录成功"""
        mock_get_token.return_value = "test_token"
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "items": [
                    {
                        "record_id": "rec123",
                        "fields": {
                            "公司名称": "Tech Corp",
                            "联系人": "John",
                            "邮箱": "john@tech.com",
                            "电话": "+86-123456789"
                        }
                    }
                ]
            }
        }
        mock_httpx.get.return_value = mock_response

        client = BitableClient()
        records = client.query_records()

        assert len(records) == 1
        assert records[0].record_id == "rec123"
        assert records[0].company_name == "Tech Corp"

    @patch.object(BitableClient, 'get_tenant_access_token')
    @patch('src.bitable.httpx')
    def test_query_records_empty(self, mock_httpx, mock_get_token):
        """测试查询记录为空"""
        mock_get_token.return_value = "test_token"
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "items": []
            }
        }
        mock_httpx.get.return_value = mock_response

        client = BitableClient()
        records = client.query_records()

        assert len(records) == 0

    @patch.object(BitableClient, 'get_tenant_access_token')
    @patch('src.bitable.httpx')
    def test_create_record_success(self, mock_httpx, mock_get_token):
        """测试创建记录成功"""
        mock_get_token.return_value = "test_token"
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "record": {
                    "record_id": "rec_new_123"
                }
            }
        }
        mock_httpx.post.return_value = mock_response

        client = BitableClient()
        card = BusinessCard(
            company_name="New Corp",
            contact_name="Alice",
            email="alice@new.com"
        )
        record_id = client.create_record(card)

        assert record_id == "rec_new_123"

    @patch.object(BitableClient, 'get_tenant_access_token')
    @patch('src.bitable.httpx')
    def test_create_record_failure(self, mock_httpx, mock_get_token):
        """测试创建记录失败"""
        mock_get_token.return_value = "test_token"
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 1254043,
            "msg": "FieldNameNotFound"
        }
        mock_httpx.post.return_value = mock_response

        client = BitableClient()
        card = BusinessCard(company_name="Test Corp")
        record_id = client.create_record(card)

        assert record_id is None

    @patch.object(BitableClient, 'get_tenant_access_token')
    @patch('src.bitable.httpx')
    def test_update_record_success(self, mock_httpx, mock_get_token):
        """测试更新记录成功"""
        mock_get_token.return_value = "test_token"
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "record": {
                    "record_id": "rec123"
                }
            }
        }
        mock_httpx.put.return_value = mock_response

        client = BitableClient()
        fields = {"公司名称": "Updated Corp"}
        result = client.update_record("rec123", fields)

        assert result == True

    @patch.object(BitableClient, 'get_tenant_access_token')
    @patch('src.bitable.httpx')
    def test_update_record_failure(self, mock_httpx, mock_get_token):
        """测试更新记录失败"""
        mock_get_token.return_value = "test_token"
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 1254043,
            "msg": "FieldNameNotFound"
        }
        mock_httpx.put.return_value = mock_response

        client = BitableClient()
        fields = {"InvalidField": "value"}
        result = client.update_record("rec123", fields)

        assert result == False

    def test_card_to_fields(self):
        """测试BusinessCard转Bitable字段"""
        client = BitableClient()
        card = BusinessCard(
            company_name="Tech Corp",
            company_name_en="Tech Corporation",
            contact_name="John Doe",
            position="Manager",
            email="john@tech.com",
            phone="+86-123456789",
            address="123 Main St",
            website="https://tech.com",
            country="China",
            city="Beijing"
        )

        fields = client.card_to_fields(card)

        assert fields["公司名称"] == "Tech Corp"
        assert fields["公司英文名称"] == "Tech Corporation"
        assert fields["联系人"] == "John Doe"
        assert fields["职位"] == "Manager"
        assert fields["邮箱"] == "john@tech.com"
        assert fields["电话"] == "+86-123456789"
        assert fields["地址"] == "123 Main St"
        assert fields["网站"] == "https://tech.com"
        assert fields["国家"] == "China"
        assert fields["城市"] == "Beijing"

    def test_record_to_session(self):
        """测试Bitable记录转CRMSession"""
        client = BitableClient()
        record = {
            "record_id": "rec123",
            "fields": {
                "公司名称": "Tech Corp",
                "联系人": "John",
                "邮箱": "john@tech.com",
                "电话": "+86-123456789"
            }
        }

        session = client.record_to_session(record)

        assert session.record_id == "rec123"
        assert session.company_name == "Tech Corp"
        assert session.contact_name == "John"
        assert session.email == "john@tech.com"
        assert session.phone == "+86-123456789"

    @patch.object(BitableClient, 'get_tenant_access_token')
    def test_query_records_no_token(self, mock_get_token):
        """测试获取token失败时查询记录"""
        mock_get_token.return_value = None

        client = BitableClient()
        records = client.query_records()

        assert len(records) == 0

    @patch.object(BitableClient, 'get_tenant_access_token')
    def test_create_record_no_token(self, mock_get_token):
        """测试获取token失败时创建记录"""
        mock_get_token.return_value = None

        client = BitableClient()
        card = BusinessCard(company_name="Test Corp")
        record_id = client.create_record(card)

        assert record_id is None
