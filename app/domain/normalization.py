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
    2. 如果未提供 normalized_value 与 normalized_unit_term_id，两者都返回 None，允许仅保存原始值和原始单位。
    3. 如果只提供其中一个，抛出 DomainValidationError（状态码 400），不写入数据库。
    4. 如果两者均提供：
       a. 属性必须存在规范单位（canonical_unit_term_id 与 canonical_unit_symbol 均非空）；
       b. normalized_unit_term_id 必须严格等于 canonical_unit_term_id；
       c. original_unit_text.strip() 必须严格等于 canonical_unit_symbol.strip()；
          若不相等，直接拒绝并提示“当前 MVP 尚不支持跨单位自动换算，请省略 normalized_* 或先在可信换算流程中处理”；
       d. value_numeric 必须存在；
       e. normalized_value 必须在 Decimal 语义下严格等于 value_numeric；
       f. 禁止大小写折叠、单位别名猜测或自动换算。
    5. 保持 Decimal 精度，不要在持久化前转成 float。
    """
    # 规则 2 & 3：二者必须同时提供或同时为空
    if normalized_value is not None and normalized_unit_term_id is None:
        raise DomainValidationError("提供 normalized_value 时必须同时提供 normalized_unit_term_id")
    if normalized_unit_term_id is not None and normalized_value is None:
        raise DomainValidationError("提供 normalized_unit_term_id 时必须同时提供 normalized_value")

    # 规则 1 & 2：未提供明确归一化时，保持为空（严禁隐式伪造 fallback 到 value_numeric）
    if normalized_value is None and normalized_unit_term_id is None:
        return None, None

    # 规则 4.a：属性必须存在规范单位
    if canonical_unit_term_id is None or not canonical_unit_symbol or not canonical_unit_symbol.strip():
        raise DomainValidationError("该属性未定义规范单位（canonical_unit），无法接受归一化值")

    # 规则 4.b：normalized_unit_term_id 必须严格等于 canonical_unit_term_id
    if normalized_unit_term_id != canonical_unit_term_id:
        raise DomainValidationError(
            f"归一化单位 '{normalized_unit_term_id}' 与属性规范单位 '{canonical_unit_term_id}' 不匹配"
        )

    # 规则 4.c：原始单位与规范单位必须严格相等（禁止跨单位自动猜测）
    orig_sym = original_unit_text.strip()
    canon_sym = canonical_unit_symbol.strip()
    if orig_sym != canon_sym:
        raise DomainValidationError(
            "当前 MVP 尚不支持跨单位自动换算，请省略 normalized_* 或先在可信换算流程中处理"
        )

    # 规则 4.d：value_numeric 必须存在
    if value_numeric is None:
        raise DomainValidationError("提供归一化值时，原始数值 (value_numeric) 必须存在")

    # 规则 4.e：normalized_value 必须在 Decimal 语义下严格等于 value_numeric
    norm_dec = Decimal(str(normalized_value))
    val_dec = Decimal(str(value_numeric))
    if norm_dec != val_dec:
        raise DomainValidationError(
            f"原始单位与规范单位同为 '{canon_sym}'，"
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
