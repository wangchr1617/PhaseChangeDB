"""材料名称归一化、别名映射、掺杂/后缀剥离及科学判定单元测试。"""

from decimal import Decimal
import pytest

from app.domain.material_normalizer import (
    extract_elements,
    is_cost_effective,
    is_low_toxicity,
    normalize_formula,
)
from app.domain.normalization import convert_to_canonical_unit


def test_standard_material_normalization():
    # 标准化学式归一化
    res = normalize_formula("Sb2Te3")
    assert res.canonical_formula == "Sb2Te3"
    assert res.chemical_system == "Sb-Te"
    assert res.is_low_toxicity is True
    assert res.is_cost_effective is True
    assert "sb2te3" in res.aliases

    res_gete = normalize_formula("GeTe")
    assert res_gete.canonical_formula == "GeTe"
    assert res_gete.chemical_system == "Ge-Te"

    res_gst = normalize_formula("Ge2Sb2Te5")
    assert res_gst.canonical_formula == "Ge2Sb2Te5"
    assert res_gst.chemical_system == "Ge-Sb-Te"


def test_case_and_subscript_insensitivity():
    # 全小写修复
    res_low = normalize_formula("sb2te3")
    assert res_low.canonical_formula == "Sb2Te3"

    res_gete_low = normalize_formula("gete")
    assert res_gete_low.canonical_formula == "GeTe"

    # Unicode 下标修复
    res_sub = normalize_formula("Sb₂Te₃")
    assert res_sub.canonical_formula == "Sb2Te3"

    res_sub2 = normalize_formula("Ge₂Sb₂Te₅")
    assert res_sub2.canonical_formula == "Ge2Sb2Te5"


def test_synonym_and_alias_mapping():
    # 英文通用全名别名
    res_en = normalize_formula("antimony telluride")
    assert res_en.canonical_formula == "Sb2Te3"

    # 中文别名
    res_zh = normalize_formula("碲化锑")
    assert res_zh.canonical_formula == "Sb2Te3"

    # 碲化锗
    res_zh_gete = normalize_formula("碲化锗")
    assert res_zh_gete.canonical_formula == "GeTe"

    # GST-225 常用缩写
    res_gst = normalize_formula("gst-225")
    assert res_gst.canonical_formula == "Ge2Sb2Te5"


def test_suffix_stripping_and_sample_preservation():
    # 测试后缀分离（如 Sb2Te3_d70d0962, Sb2Te3-film, GeTeReqId1 等）
    res_hash = normalize_formula("Sb2Te3_d70d0962")
    assert res_hash.canonical_formula == "Sb2Te3"
    assert res_hash.sample_suffix == "d70d0962"

    res_persist = normalize_formula("Sb2Te3_PErSiST")
    assert res_persist.canonical_formula == "Sb2Te3"

    res_reqid = normalize_formula("GeTeReqId1")
    assert res_reqid.canonical_formula == "GeTe"

    res_film = normalize_formula("Sb2Te3-film")
    assert res_film.canonical_formula == "Sb2Te3"


def test_dopant_prefix_separation():
    # 掺杂前缀结构化分离 (Sc0.2Sb2Te3 -> 主材料 Sb2Te3, 掺杂 Sc 0.2)
    res_dop = normalize_formula("Sc0.2Sb2Te3")
    assert res_dop.canonical_formula == "Sb2Te3"
    assert res_dop.doping_element == "Sc"
    assert res_dop.doping_concentration == 0.2
    # Sc 属于昂贵稀贵元素，因此掺杂后 cost_effective 判定为 False
    assert res_dop.is_cost_effective is False


def test_toxicity_and_cost_evaluations():
    # 纯态低毒与成本可控
    assert is_low_toxicity(["Ge", "Sb", "Te"]) is True
    assert is_cost_effective(["Ge", "Sb", "Te"]) is True

    # 包含重金属黑名单 (Pb, Cd, Hg, As, Tl, Be)
    assert is_low_toxicity(["Pb", "Te"]) is False
    assert is_low_toxicity(["Cd", "Te"]) is False
    assert is_low_toxicity(["As", "Se"]) is False

    # 包含高价贵金属黑名单 (Au, Pt, Pd, Ru, Rh, Ir, Sc)
    assert is_cost_effective(["Au", "Ge", "Te"]) is False
    assert is_cost_effective(["Pt", "Sb", "Te"]) is False
    assert is_cost_effective(["Sc", "Sb", "Te"]) is False


def test_latent_heat_unit_conversions():
    # 相变潜热统一换算到 J/g
    # 120 kJ/kg -> 120 J/g
    val1 = convert_to_canonical_unit(120, "kJ/kg", "J/g")
    assert val1 == Decimal("120")

    # 150000 J/kg -> 150 J/g
    val2 = convert_to_canonical_unit(150000, "J/kg", "J/g")
    assert val2 == Decimal("150")

    # 10 cal/g -> 41.84 J/g
    val3 = convert_to_canonical_unit(10, "cal/g", "J/g")
    assert val3 == Decimal("41.84")
