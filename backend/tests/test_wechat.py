from types import SimpleNamespace

from app.wechat.ilink_client import extract_text_messages
from app.wechat.service import WechatService


def test_extract_text_messages_from_ilink_payload():
    payload = {
        "msgs": [
            {
                "msg": {
                    "msg_id": "m1",
                    "from_user_id": "u1",
                    "context_token": "ctx",
                    "item_list": [{"type": 1, "text_item": {"text": "你好"}}],
                }
            }
        ]
    }
    messages = extract_text_messages(payload)
    assert len(messages) == 1
    assert messages[0].message_id == "m1"
    assert messages[0].user_id == "u1"
    assert messages[0].text == "你好"
    assert messages[0].context_token == "ctx"


async def test_qr_login_uses_image_content_and_keeps_token_private(monkeypatch, tmp_path):
    class FakeILinkClient:
        def __init__(self, base_url, token="", timeout=35):
            self.base_url = base_url
            self.token = token
            self.timeout = timeout

        async def fetch_qr_code(self):
            return {
                "qrcode": "opaque-polling-id",
                "qrcode_img_content": "https://example.test/wechat-login",
            }

        async def poll_qr_status(self, qrcode):
            assert qrcode == "opaque-polling-id"
            return {
                "status": "confirmed",
                "bot_token": "secret-bot-token",
                "baseurl": "https://confirmed.example.test",
            }

    monkeypatch.setattr("app.wechat.service.ILinkClient", FakeILinkClient)
    settings = SimpleNamespace(
        wechat=SimpleNamespace(
            base_url="https://initial.example.test",
            credentials_path=tmp_path / "wechat_credentials.json",
            long_poll_timeout_seconds=35,
        )
    )
    service = WechatService(settings, agent=object())

    qr_result = await service.request_qr()
    assert qr_result == {
        "status": "waiting_scan",
        "qr_url": "https://example.test/wechat-login",
    }
    assert service.state.qr_code == "opaque-polling-id"

    poll_result = await service.poll_qr_once()
    assert poll_result == {"status": "logged_in", "has_token": True}
    assert "secret-bot-token" not in str(poll_result)
    assert service._client.base_url == "https://confirmed.example.test"
