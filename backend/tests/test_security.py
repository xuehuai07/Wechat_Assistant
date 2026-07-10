from app.security import SessionStore, redact


def test_redact_masks_nested_sensitive_values():
    value = {"deepseek_api_key": "abcdef123456", "nested": {"context_token": "tok123456789"}}
    assert redact(value) == {"deepseek_api_key": "abc***456", "nested": {"context_token": "tok***789"}}


def test_session_store_requires_exact_password():
    store = SessionStore()
    assert store.create("secret", "wrong") is None
    token = store.create("secret", "secret")
    assert token
    assert store.valid(token)
    store.revoke(token)
    assert not store.valid(token)
