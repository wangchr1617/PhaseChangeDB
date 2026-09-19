"""PhaseChangeDB MySQL 仓储通用基础类与数据转换辅助函数。"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def to_uuid(value: bytes | bytearray | memoryview | None) -> UUID | None:
    """将 MySQL BINARY(16) 转换为 Python UUID。"""
    return UUID(bytes=bytes(value)) if value is not None else None


def to_json(value: Any) -> dict | None:
    """将 JSON 字符串或字典解析为标准 Python 字典。"""
    if value is None or isinstance(value, dict):
        return value
    return json.loads(value)


def to_number(value: Decimal | int | float | None) -> float | None:
    """将数值类型安全转换为 float。"""
    return float(value) if value is not None else None


class BaseMySQLRepository:
    """所有 MySQL 细分子仓储的公共基类。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def outbox(
        self,
        event_id: UUID,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict,
    ) -> None:
        """在当前事务中持久化 Outbox 事件。"""
        await self.session.execute(
            text(
                """
                INSERT INTO sys_outbox_event (id, aggregate_type, aggregate_id, event_type, payload_json)
                VALUES (:id, :aggregate_type, :aggregate_id, :event_type, :payload)
                """
            ),
            {
                "id": event_id.bytes,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id.bytes,
                "event_type": event_type,
                "payload": json.dumps(payload, ensure_ascii=False),
            },
        )
