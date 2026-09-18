from decimal import Decimal
from uuid import uuid4

from app.domain.normalization import (
    convert_to_canonical_unit,
    format_display_value,
    try_unit_conversion,
)


def test_temperature_conversion():
    # 摄氏度转开尔文: 130 °C -> 403.15 K
    k_val = convert_to_canonical_unit(130, "°C", "K")
    assert k_val == Decimal("403.15")

    # 450 °C -> 723.15 K
    k_val2 = convert_to_canonical_unit(450, "℃", "K")
    assert k_val2 == Decimal("723.15")


def test_energy_conversion():
    # meV -> eV
    ev = convert_to_canonical_unit(500, "meV", "eV")
    assert ev == Decimal("0.5")

    # Hartree -> eV
    ev_ha = convert_to_canonical_unit(1, "Hartree", "eV")
    assert ev_ha == Decimal("27.211386245988")

    # kJ/mol -> eV
    ev_kj = convert_to_canonical_unit(100, "kJ/mol", "eV")
    assert ev_kj == Decimal("1.036427")


def test_length_and_pressure_conversion():
    # Å -> nm
    nm = convert_to_canonical_unit(5, "Å", "nm")
    assert nm == Decimal("0.5")

    # MPa -> GPa
    gpa = convert_to_canonical_unit(2500, "MPa", "GPa")
    assert gpa == Decimal("2.5")


def test_display_value_formatting():
    # 温度统一显示为 K，不显示任何摄氏度辅助
    disp = format_display_value(130, "°C", "K", Decimal("403.15"))
    assert disp == "403.15 K"
    assert "°C" not in disp

    # 开尔文直接显示
    disp_k = format_display_value(453, "K", "K")
    assert disp_k == "453 K"
    assert "°C" not in disp_k

    # 能量显示
    disp_e = format_display_value(2.35, "eV", "eV")
    assert disp_e == "2.35 eV"

    # 空值处理
    assert format_display_value(None) == "—"


def test_auto_normalization():
    canon_id = uuid4()
    norm_val, norm_id = try_unit_conversion(
        original_unit_text="°C",
        value_numeric=130,
        canonical_unit_term_id=canon_id,
        canonical_unit_symbol="K",
    )
    assert norm_val == Decimal("403.15")
    assert norm_id == canon_id
