"""PhaseChangeDB 安全加密与大模型代理中继单元测试。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret, sanitize_sensitive_dict
from app.main import app


def test_crypto_roundtrip():
    """测试 AES-256-GCM 加密与解密的正确性与可逆性。"""
    secret = "sk-proj-super-secret-key-1234567890abcdef"
    encrypted = encrypt_secret(secret)
    assert encrypted != secret
    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret


def test_crypto_different_nonces():
    """测试相同明文加密生成不同密文（防重放与统计分析）。"""
    secret = "same-secret-token"
    enc1 = encrypt_secret(secret)
    enc2 = encrypt_secret(secret)
    assert enc1 != enc2
    assert decrypt_secret(enc1) == secret
    assert decrypt_secret(enc2) == secret


def test_mask_secret():
    """测试敏感凭据掩码脱敏。"""
    assert mask_secret("sk-1234567890abcdef") == "sk-1••••••def"
    assert mask_secret("") == "未配置凭据"
    assert mask_secret(None) == "未配置凭据"
    assert mask_secret("short") == "••••••"


def test_sanitize_sensitive_dict():
    """测试嵌套字典全链路敏感字段自动脱敏。"""
    raw = {
        "user": "alice",
        "api_key": "sk-1234567890abcdef",
        "nested": {
            "password": "mypassword123",
            "token": "token-xyz-789",
            "status": "active",
        },
        "list_items": [
            {"name": "item1", "secret": "very-secret-token"},
            {"name": "item2", "count": 10},
        ],
    }
    sanitized = sanitize_sensitive_dict(raw)
    assert sanitized["user"] == "alice"
    assert sanitized["api_key"] == "sk-1••••••def"
    assert sanitized["nested"]["password"] == "mypa••••••123"
    assert sanitized["nested"]["token"] == "toke••••••789"
    assert sanitized["nested"]["status"] == "active"
    assert sanitized["list_items"][0]["secret"] == "very••••••ken"
    assert sanitized["list_items"][1]["count"] == 10


@pytest.mark.asyncio
async def test_agent_diagnostic_custom_key():
    """测试通过接口传入自定义 Key 时的混合双模解析与掩码保护。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/v1/agents/literature-parser/diagnostic",
            json={
                "provider": "gemini",
                "model_name": "gemini-2.5-pro",
                "api_key": "AIzaSyD-dummy-custom-key-12345678",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["key_mode"] == "custom_user_key"
        assert "AIza••••••678" in data["masked_key"]
        # 绝不能在响应体或日志中泄露完整原始 key
        assert "AIzaSyD-dummy-custom-key-12345678" not in str(data)


@pytest.mark.asyncio
async def test_agent_diagnostic_demo_key():
    """测试未传 Key 时自动回退至演示模式或服务端托管 Key。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/v1/agents/literature-parser/diagnostic",
            json={
                "provider": "gemini",
                "model_name": "gemini-2.5-pro",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["key_mode"] in ("server_hosted_key", "demo_simulation")
