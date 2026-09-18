"""PhaseChangeDB 科学属性单位与归一化领域规则。"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.domain.exceptions import DomainValidationError

# 能量单位换算基准（转为 eV）
ENERGY_CONVERSIONS_TO_EV: dict[str, Decimal] = {
    "ev": Decimal("1"),
    "mev": Decimal("0.001"),
    "j": Decimal("1") / Decimal("1.602176634e-19"),
    "hartree": Decimal("27.211386245988"),
    "ha": Decimal("27.211386245988"),
    "ry": Decimal("13.605693122994"),
    "rydberg": Decimal("13.605693122994"),
    "kj/mol": Decimal("0.01036427"),
    "kj_mol": Decimal("0.01036427"),
    "cm-1": Decimal("0.0001239841984332003"),
    "cm⁻¹": Decimal("0.0001239841984332003"),
}

# 长度单位换算基准（转为 nm）
LENGTH_CONVERSIONS_TO_NM: dict[str, Decimal] = {
    "nm": Decimal("1"),
    "å": Decimal("0.1"),
    "angstrom": Decimal("0.1"),
    "a": Decimal("0.1"),
    "um": Decimal("1000"),
    "µm": Decimal("1000"),
    "pm": Decimal("0.001"),
    "m": Decimal("1000000000"),
}

# 压力单位换算基准（转为 GPa）
PRESSURE_CONVERSIONS_TO_GPA: dict[str, Decimal] = {
    "gpa": Decimal("1"),
    "mpa": Decimal("0.001"),
    "kpa": Decimal("0.000001"),
    "pa": Decimal("0.000000001"),
    "bar": Decimal("0.0001"),
    "mbar": Decimal("0.0000001"),
}

# 时间单位换算基准（转为 s）
TIME_CONVERSIONS_TO_S: dict[str, Decimal] = {
    "s": Decimal("1"),
    "sec": Decimal("1"),
    "ms": Decimal("0.001"),
    "us": Decimal("0.000001"),
    "µs": Decimal("0.000001"),
    "ns": Decimal("0.000000001"),
    "ps": Decimal("0.000000000001"),
}

# 时间单位换算基准（转为 ps）
TIME_CONVERSIONS_TO_PS: dict[str, Decimal] = {
    "ps": Decimal("1"),
    "ns": Decimal("1000"),
    "us": Decimal("1000000"),
    "µs": Decimal("1000000"),
    "ms": Decimal("1000000000"),
    "s": Decimal("1000000000000"),
    "sec": Decimal("1000000000000"),
}


def convert_to_canonical_unit(
    value: Decimal | float | int,
    from_unit: str,
    to_canonical_unit: str,
) -> Decimal | None:
    """根据科学换算规则将输入数值换算为规范单位数值。
    若单位相同则直接返回原数值。若无法识别对应换算关系则返回 None。
    """
    if value is None:
        return None
    val_dec = Decimal(str(value))
    src = from_unit.strip().lower()
    tgt = to_canonical_unit.strip().lower()

    if src == tgt:
        return val_dec

    # 1. 温度换算：目标为 K
    if tgt == "k":
        if src in {"°c", "℃", "degc", "c", "ºc"}:
            return val_dec + Decimal("273.15")
        if src in {"°f", "℉", "f", "ºf"}:
            return ((val_dec - Decimal("32")) * Decimal("5") / Decimal("9")) + Decimal("273.15")

    # 2. 能量换算：目标为 eV
    if tgt == "ev":
        factor = ENERGY_CONVERSIONS_TO_EV.get(src)
        if factor is not None:
            return val_dec * factor

    # 3. 长度换算：目标为 nm
    if tgt == "nm":
        factor = LENGTH_CONVERSIONS_TO_NM.get(src)
        if factor is not None:
            return val_dec * factor

    # 4. 压力换算：目标为 GPa
    if tgt == "gpa":
        factor = PRESSURE_CONVERSIONS_TO_GPA.get(src)
        if factor is not None:
            return val_dec * factor

    # 5. 时间换算：目标为 s
    if tgt in {"s", "sec"}:
        factor = TIME_CONVERSIONS_TO_S.get(src)
        if factor is not None:
            return val_dec * factor

    # 6. 时间换算：目标为 ps
    if tgt == "ps":
        factor = TIME_CONVERSIONS_TO_PS.get(src)
        if factor is not None:
            return val_dec * factor

    # 7. 潜热换算：目标为 J/g
    if tgt in {"j/g", "j_g", "j g-1"}:
        if src in {"j/g", "j_g", "j g-1", "j/g-1"}:
            return val_dec
        if src in {"kj/kg", "kj_kg"}:
            return val_dec
        if src in {"cal/g", "cal_g"}:
            return val_dec * Decimal("4.184")
        if src in {"kcal/kg"}:
            return val_dec * Decimal("4.184")
        if src in {"j/kg"}:
            return val_dec * Decimal("0.001")

    return None


def _clean_decimal_str(d: Decimal) -> str:
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def format_display_value(
    value: Decimal | float | int | str | None,
    unit: str | None = None,
    canonical_unit: str | None = None,
    normalized_value: Decimal | float | int | None = None,
) -> str:
    """生成符合规范的全站展示文本。
    对于温度自动生成 '723 K（450 °C）' 的双单位显示形式。
    """
    if value is None:
        return "—"

    # 如果是非数值类型直接返回
    if isinstance(value, str):
        try:
            val_dec = Decimal(value)
        except Exception:
            return f"{value} {unit or ''}".strip() or "—"
    else:
        val_dec = Decimal(str(value))

    unit_clean = (unit or "").strip()
    canon_clean = (canonical_unit or "").strip()

    # 温度展示：统一规范使用 K，不显示任何摄氏度辅助
    temp_units = {"°c", "℃", "degc", "c", "ºc"}
    if canon_clean.upper() == "K" or unit_clean.upper() == "K" or unit_clean.lower() in temp_units:
        if unit_clean.lower() in temp_units:
            k_val = Decimal(str(normalized_value)) if normalized_value is not None else (val_dec + Decimal("273.15"))
        else:
            k_val = Decimal(str(normalized_value)) if normalized_value is not None else val_dec
        return f"{_clean_decimal_str(k_val)} K"

    # 普通单位展示
    display_unit = canon_clean or unit_clean
    val_str = _clean_decimal_str(val_dec)
    return f"{val_str} {display_unit}".strip() if display_unit else val_str


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
    """严格校验并解析科学观测的归一化数值与单位。"""
    # 规则 2 & 3：二者必须同时提供或同时为空
    if normalized_value is not None and normalized_unit_term_id is None:
        raise DomainValidationError("提供 normalized_value 时必须同时提供 normalized_unit_term_id")
    if normalized_unit_term_id is not None and normalized_value is None:
        raise DomainValidationError("提供 normalized_unit_term_id 时必须同时提供 normalized_value")

    # 未提供明确归一化时，保持为空（严禁隐式伪造 fallback 到 value_numeric）
    if normalized_value is None and normalized_unit_term_id is None:
        return None, None

    if canonical_unit_term_id is None or not canonical_unit_symbol or not canonical_unit_symbol.strip():
        raise DomainValidationError("该属性未定义规范单位（canonical_unit），无法接受归一化值")

    if normalized_unit_term_id != canonical_unit_term_id:
        raise DomainValidationError(
            f"归一化单位 '{normalized_unit_term_id}' 与属性规范单位 '{canonical_unit_term_id}' 不匹配"
        )

    canon_sym = canonical_unit_symbol.strip()
    orig_sym = original_unit_text.strip()
    norm_dec = Decimal(str(normalized_value))

    if value_numeric is None:
        raise DomainValidationError("提供归一化值时，原始数值 (value_numeric) 必须存在")

    val_dec = Decimal(str(value_numeric))

    # 同单位检验
    if orig_sym == canon_sym:
        if norm_dec != val_dec:
            raise DomainValidationError(
                f"原始单位与规范单位同为 '{canon_sym}'，"
                f"归一化值 ({norm_dec}) 必须与原始数值 ({val_dec}) 一致"
            )
        return norm_dec, canonical_unit_term_id

    # 跨单位科学换算检验
    expected = convert_to_canonical_unit(val_dec, orig_sym, canon_sym)
    if expected is None:
        raise DomainValidationError(
            f"不支持将单位 '{orig_sym}' 换算为规范单位 '{canon_sym}'"
        )
    if abs(expected - norm_dec) > Decimal("0.01"):
        raise DomainValidationError(
            f"提供的归一化值 ({norm_dec}) 与从原始单位 '{orig_sym}' 换算的值 ({expected}) 不一致"
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


def try_unit_conversion(
    *,
    original_unit_text: str,
    value_numeric: Decimal | float | None,
    canonical_unit_term_id: UUID | None,
    canonical_unit_symbol: str | None,
) -> tuple[Decimal | None, UUID | None]:
    """尝试将原始数值科学归一化为规范单位数值（支持跨单位）。"""
    if value_numeric is None or not canonical_unit_term_id or not canonical_unit_symbol:
        return None, None
    converted = convert_to_canonical_unit(value_numeric, original_unit_text, canonical_unit_symbol)
    if converted is not None:
        return converted, canonical_unit_term_id
    return None, None

