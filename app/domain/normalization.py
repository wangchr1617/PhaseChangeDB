"""PhaseChangeDB 科学属性单位与归一化领域规则。"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.domain.exceptions import DomainValidationError


def resolve_and_validate_normalization(
    *,
    original_value_text: str,
    original_unit_text: str,
    value_numeric: Decimal | float | None,
    normalized_value: Decimal | float | None,
    normalized_unit_term_id: UUID | None,
    canonical_unit_term_id: UUID | None,
    canonical_unit_symbol: str | None = None,
) -> tuple[Decimal | None, UUID | None]:
    """严格校验并解析科学观测的归一化数值与单位。

    不变量规则：
    1. 原始值与原始单位（original_value_text, original_unit_text）是绝对权威事实，不可丢失。
    2. 如果没有执行明确的单位归一化，normalized_value 与 normalized_unit_term_id 必须同时保持 None。
    3. 如果提供了 normalized_value，必须同时提供 normalized_unit_term_id。
    4. 如果提供了 normalized_unit_term_id，必须同时提供 normalized_value。
    5. 归一化单位 normalized_unit_term_id 必须与属性定义中的 canonical_unit_term_id 完全一致。
    6. 暂时没有全局单位换算引擎时，同单位等值归一化必须经过明确的单位符号验证，数值必须与原始测量值保持一致。
    """
    # 规则 3 & 4：二者必须同时提供或同时为空
    if normalized_value is not None and normalized_unit_term_id is None:
        raise DomainValidationError("提供 normalized_value 时必须同时提供 normalized_unit_term_id")
    if normalized_unit_term_id is not None and normalized_value is None:
        raise DomainValidationError("提供 normalized_unit_term_id 时必须同时提供 normalized_value")

    # 规则 2：未提供明确归一化时，保持为空（严禁隐式伪造 fallback 到 value_numeric）
    if normalized_value is None and normalized_unit_term_id is None:
        return None, None

    # 规则 5：提供归一化值时，必须确保属性本身定义了规范单位且相互匹配
    if canonical_unit_term_id is None:
        raise DomainValidationError("该属性未定义 canonical_unit_term_id，无法接受归一化值")

    if normalized_unit_term_id != canonical_unit_term_id:
        raise DomainValidationError(
            f"归一化单位 '{normalized_unit_term_id}' 与属性规范单位 '{canonical_unit_term_id}' 不匹配"
        )

    norm_dec = Decimal(str(normalized_value))

    # 规则 6：同单位等值归一化检验
    if canonical_unit_symbol and original_unit_text.strip() == canonical_unit_symbol.strip():
        if value_numeric is not None:
            val_dec = Decimal(str(value_numeric))
            if norm_dec != val_dec:
                raise DomainValidationError(
                    f"原始单位与规范单位同为 '{canonical_unit_symbol}'，"
                    f"归一化值 ({norm_dec}) 必须与原始数值 ({val_dec}) 一致"
                )

    return norm_dec, canonical_unit_term_id


def try_same_unit_normalization(
    *,
    original_unit_text: str,
    value_numeric: Decimal | float | None,
    canonical_unit_term_id: UUID | None,
    canonical_unit_symbol: str | None,
) -> tuple[Decimal | None, UUID | None]:
    """当原始单位严格与属性规范单位一致时，显式执行同单位等值归一化。"""
    if value_numeric is None or not canonical_unit_term_id or not canonical_unit_symbol:
        return None, None
    if original_unit_text.strip() == canonical_unit_symbol.strip():
        return Decimal(str(value_numeric)), canonical_unit_term_id
    return None, None
