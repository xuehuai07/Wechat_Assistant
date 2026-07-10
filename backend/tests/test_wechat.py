from app.wechat.ilink_client import extract_text_messages


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
