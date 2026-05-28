from unittest.mock import patch, MagicMock
from process_card import main_with_progress


@patch("process_card.os.path.exists", return_value=True)
def test_main_with_progress_calls_callback(mock_exists):
    progress_messages = []

    def on_progress(step, message):
        progress_messages.append((step, message))

    with patch("process_card.ExhibitionAgent") as MockAgent:
        mock_instance = MagicMock()
        mock_instance.process_card.return_value = {
            "success": True,
            "record_id": "rec_123",
            "card": MagicMock(
                company_name="Test Corp",
                contact_name="John",
                position="CEO",
                email="john@test.com",
                phone="123",
                country="US",
                city="NY",
            ),
            "is_duplicate": False,
            "duplicate_info": {},
            "background_result": {"success": True, "report_url": "http://example.com"},
        }
        mock_instance.format_response.return_value = "处理成功"
        MockAgent.return_value = mock_instance
        result = main_with_progress("/tmp/test.jpg", "补充信息", on_progress)

    assert result == "处理成功"
    assert len(progress_messages) > 0
    assert progress_messages[0][1] == "📋 正在识别名片信息..."


def test_main_with_progress_no_image():
    result = main_with_progress("/tmp/nonexistent.jpg")
    assert "错误" in result


@patch("process_card.os.path.exists", return_value=True)
def test_main_with_progress_no_callback(mock_exists):
    with patch("process_card.ExhibitionAgent") as MockAgent:
        mock_instance = MagicMock()
        mock_instance.process_card.return_value = {"success": True}
        mock_instance.format_response.return_value = "OK"
        MockAgent.return_value = mock_instance
        result = main_with_progress("/tmp/test.jpg")
    assert result == "OK"
