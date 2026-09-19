"""PhaseChangeDB 凭据安全加解密与脱敏工具模块。

使用 AES-256-GCM 算法对大模型 API Key 及敏感凭据进行加密存储与安全会话中继，
杜绝数据库、日志与前端明文泄露。
"""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


def derive_key(key_material: str | None = None) -> bytes:
    """基于配置的 secret_key 或默认物料派生 32 字节 (256-bit) 密钥。"""
    settings = get_settings()
    material = key_material or getattr(settings, "secret_key", "phasechange-dev-secret-key-change-in-production-32b")
    return hashlib.sha256(material.encode("utf-8")).digest()


def encrypt_secret(plaintext: str, key_material: str | None = None) -> str:
    """使用 AES-256-GCM 加密明文凭据，返回 Base64 编码的密文包 (nonce + ciphertext + tag)。"""
    if not plaintext:
        return ""
    key = derive_key(key_material)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    payload = nonce + ciphertext
    return base64.urlsafe_b64encode(payload).decode("utf-8")


def decrypt_secret(ciphertext_b64: str, key_material: str | None = None) -> str:
    """解密 Base64 编码的密文包，恢复原始明文凭据。"""
    if not ciphertext_b64:
        return ""
    key = derive_key(key_material)
    aesgcm = AESGCM(key)
    payload = base64.urlsafe_b64decode(ciphertext_b64.encode("utf-8"))
    if len(payload) < 12:
        raise ValueError("无效的密文载荷：长度不足")
    nonce = payload[:12]
    ct = payload[12:]
    decrypted_bytes = aesgcm.decrypt(nonce, ct, None)
    return decrypted_bytes.decode("utf-8")


def mask_secret(secret: str | None, prefix_len: int = 4, suffix_len: int = 3) -> str:
    """对敏感凭据（API Key、Token、密码）进行安全掩码展示。

    例如：sk-1234567890abcdef -> sk-1••••••cdef
    """
    if not secret or not secret.strip():
        return "未配置凭据"
    s = secret.strip()
    if len(s) <= prefix_len + suffix_len:
        return "••••••"
    return f"{s[:prefix_len]}••••••{s[-suffix_len:]}"


def sanitize_sensitive_dict(data: dict[str, Any]) -> dict[str, Any]:
    """递归对字典中的敏感字段（如 api_key, password, token, authorization 等）进行掩码脱敏。"""
    sensitive_keys = {
        "api_key",
        "apikey",
        "secret",
        "password",
        "token",
        "authorization",
        "pcm_reviewer_token",
        "secret_key",
    }
    sanitized: dict[str, Any] = {}
    for k, v in data.items():
        lower_k = k.lower()
        if any(sk in lower_k for sk in sensitive_keys) and isinstance(v, str):
            sanitized[k] = mask_secret(v)
        elif isinstance(v, dict):
            sanitized[k] = sanitize_sensitive_dict(v)
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_sensitive_dict(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized
