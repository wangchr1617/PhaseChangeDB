"""PhaseChangeDB 相变材料核心物性提取标准领域 Schema 与校验规范。

面向相变存储材料（PCM）领域设计：
1. 核心物性规范：结晶温度 (Tc/Tx)、熔点 (Tm)、激活能 (Ea)、翻转时间 (t_cryst/t_SET)、高低阻态电阻率等；
2. 实验条件约束：升温速率 (heating rate，如 10, 20, 40 K/min)、测试方法 (DSC, XRD, R-T)、薄膜厚度与衬底；
3. 样品成分解耦：标称材料、掺杂元素 (Dopant)、掺杂原子百分比 (at.%) 及完整配比式；
4. 证据链回溯：原文片段、图表定位 (如 Fig. 3a)、页码与置信度。
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 数据库已知规范属性 Code 与其物理维度及单位映射
CANONICAL_PROPERTY_CONFIG: dict[str, dict[str, Any]] = {
    "crystallization_temperature": {
        "name": "Crystallization Temperature",
        "symbol": "Tx",
        "canonical_unit": "K",
        "canonical_unit_term_id": UUID("01a06666-3c71-7c33-ab52-f93946c91c5b"),
        "property_definition_id": UUID("01a06666-90fe-7a0f-88d7-afad67e17652"),
        "allowed_input_units": ["K", "°C", "C", "degC"],
    },
    "activation_energy": {
        "name": "Activation Energy",
        "symbol": "Ea",
        "canonical_unit": "eV",
        "canonical_unit_term_id": UUID("01a06666-3c71-7266-a1ba-eb5a84b5e2a0"),
        "property_definition_id": UUID("01a06666-90fe-7157-8efe-0faf744b5ded"),
        "allowed_input_units": ["eV", "kJ/mol", "J/mol"],
    },
    "melting_temperature": {
        "name": "Melting Temperature",
        "symbol": "Tm",
        "canonical_unit": "K",
        "canonical_unit_term_id": UUID("01a06666-3c71-7c33-ab52-f93946c91c5b"),
        "property_definition_id": UUID("01a06666-90fe-7636-9fd8-dbff5e37fe3e"),
        "allowed_input_units": ["K", "°C", "C", "degC"],
    },
    "glass_transition_temperature": {
        "name": "Glass Transition Temperature",
        "symbol": "Tg",
        "canonical_unit": "K",
        "canonical_unit_term_id": UUID("01a06666-3c71-7c33-ab52-f93946c91c5b"),
        "property_definition_id": UUID("01a06666-90fe-7be7-b976-143309756899"),
        "allowed_input_units": ["K", "°C", "C", "degC"],
    },
    "crystallization_time": {
        "name": "Crystallization Time",
        "symbol": "t_cryst",
        "canonical_unit": "s",
        "canonical_unit_term_id": UUID("01a06666-3c71-72fa-a679-300c36fa1f6b"),
        "property_definition_id": UUID("01a06666-90fe-7d76-914d-74ab13f3e938"),
        "allowed_input_units": ["s", "ns", "us", "ms"],
    },
    "SET_time": {
        "name": "SET Time",
        "symbol": "t_SET",
        "canonical_unit": "s",
        "canonical_unit_term_id": UUID("01a06666-3c71-72fa-a679-300c36fa1f6b"),
        "property_definition_id": UUID("01a06666-90fe-7264-b944-6fa29aa955cd"),
        "allowed_input_units": ["s", "ns", "us", "ms"],
    },
    "electrical_resistivity": {
        "name": "Electrical Resistivity",
        "symbol": "ρ",
        "canonical_unit": "ohm_m",
        "canonical_unit_term_id": UUID("01a06666-3c71-79b4-b050-2bd4bc30ac1a"),
        "property_definition_id": UUID("01a06666-90fe-728e-94dc-e81b18cbeb38"),
        "allowed_input_units": ["ohm_m", "Ω·m", "ohm·m", "ohm_cm", "Ω·cm", "ohm·cm"],
    },
}

# 默认样品类型薄膜与测量方法 Term ID
THIN_FILM_SAMPLE_TYPE_TERM_ID = UUID("01a06666-3c71-7d4e-9cb8-edf582d577fd")
THERMAL_CATEGORY_TERM_ID = UUID("01a06666-3c71-7f0a-92e1-679ac97ef680")


def normalize_temperature(value: float | Decimal, unit: str) -> tuple[Decimal, UUID]:
    """统一温度归一化到开尔文 (K) 并返回其 canonical term id。"""
    u = unit.strip().lower()
    val_dec = Decimal(str(value))
    term_id = CANONICAL_PROPERTY_CONFIG["crystallization_temperature"]["canonical_unit_term_id"]
    if u in ("k", "kelvin"):
        return val_dec, term_id
    if u in ("°c", "c", "degc", "celsius"):
        # T(K) = T(°C) + 273.15
        return val_dec + Decimal("273.15"), term_id
    raise ValueError(f"不支持的温度输入单位: {unit}")


def normalize_activation_energy(value: float | Decimal, unit: str) -> tuple[Decimal, UUID]:
    """统一活化能归一化到 eV。"""
    u = unit.strip().lower()
    val_dec = Decimal(str(value))
    term_id = CANONICAL_PROPERTY_CONFIG["activation_energy"]["canonical_unit_term_id"]
    if u in ("ev", "electronvolt"):
        return val_dec, term_id
    if u in ("kj/mol", "kj mol-1", "kj*mol-1"):
        # 1 eV = 96.4853 kJ/mol => 1 kJ/mol = 0.010364 eV
        ev_val = val_dec / Decimal("96.4853")
        return ev_val.quantize(Decimal("0.0001")), term_id
    raise ValueError(f"不支持的活化能单位: {unit}")


def normalize_time(value: float | Decimal, unit: str) -> tuple[Decimal, UUID]:
    """统一时间归一化到秒 (s)。"""
    u = unit.strip().lower()
    val_dec = Decimal(str(value))
    term_id = CANONICAL_PROPERTY_CONFIG["crystallization_time"]["canonical_unit_term_id"]
    if u in ("s", "second"):
        return val_dec, term_id
    if u in ("ns", "nanosecond"):
        return val_dec * Decimal("1e-9"), term_id
    if u in ("us", "μs", "microsecond"):
        return val_dec * Decimal("1e-6"), term_id
    if u in ("ms", "millisecond"):
        return val_dec * Decimal("1e-3"), term_id
    raise ValueError(f"不支持的时间单位: {unit}")


def normalize_property_value(property_code: str, value: float | Decimal, unit: str) -> tuple[Decimal, UUID]:
    """根据物性 code 统一调用专用换算函数。"""
    if property_code in ("crystallization_temperature", "melting_temperature", "glass_transition_temperature"):
        return normalize_temperature(value, unit)
    if property_code == "activation_energy":
        return normalize_activation_energy(value, unit)
    if property_code in ("crystallization_time", "SET_time"):
        return normalize_time(value, unit)
    if property_code == "electrical_resistivity":
        u = unit.strip().lower()
        val_dec = Decimal(str(value))
        term_id = CANONICAL_PROPERTY_CONFIG["electrical_resistivity"]["canonical_unit_term_id"]
        if u in ("ohm_m", "ω·m", "ohm·m"):
            return val_dec, term_id
        if u in ("ohm_cm", "ω·cm", "ohm·cm"):
            return val_dec * Decimal("0.01"), term_id
        raise ValueError(f"不支持的电阻率单位: {unit}")
    raise ValueError(f"未实现物性换算规则: {property_code}")


class PhaseChangePropertyCandidate(BaseModel):
    """相变材料结构化提取单项物性候选 Schema。"""

    model_config = ConfigDict(extra="forbid")

    property_code: Literal[
        "crystallization_temperature",
        "activation_energy",
        "melting_temperature",
        "glass_transition_temperature",
        "crystallization_time",
        "SET_time",
        "electrical_resistivity",
    ] = Field(description="物性代码，必须严格对应系统 obs_property_definition.code")

    nominal_material: str = Field(
        min_length=1, max_length=64, description="宿主材料标识，如 GeTe, Sb2Te3, Ge2Sb2Te5"
    )
    sample_formula: str = Field(
        min_length=1, max_length=128, description="实际样品化学式，如 Ge45Bi5Te50, GeTe, (GeTe)0.9(Bi2Te3)0.1"
    )
    dopant_element: str | None = Field(default=None, max_length=8, description="掺杂元素符号，如 Bi, In, Sb, N, C, Ag")
    dopant_ratio_at_pct: float | None = Field(default=None, ge=0.0, le=100.0, description="掺杂原子百分比 (at.%)")

    # 实验与测试条件
    sample_type: str = Field(default="thin_film", description="样品形貌类型 (thin_film, bulk, nanowire)")
    film_thickness_nm: float | None = Field(default=None, ge=0.0, description="薄膜厚度，单位 nm")
    substrate: str | None = Field(default=None, max_length=128, description="衬底材料，如 SiO2/Si, Glass, Quartz")
    heating_rate_k_per_min: float | None = Field(
        default=None, ge=0.0, description="升温速率 (K/min 或 °C/min)，热学测量 (如 DSC, R-T) 的核心不变量"
    )
    measurement_method: str | None = Field(
        default=None, max_length=64, description="测试方法，如 DSC, R-T, in-situ XRD"
    )

    # 测量值与单位
    original_value: float = Field(description="文献中原始报告的数值")
    original_unit: str = Field(min_length=1, max_length=32, description="文献中原始报告的单位，如 °C, K, eV, ns")
    normalized_value: float | None = Field(default=None, description="自动计算的规范单位数值 (如 K, eV, s)")
    normalized_unit_term_id: UUID | None = Field(default=None, description="对应规范单位 ont_term.id")

    # 原文证据支撑
    evidence_text: str = Field(min_length=5, description="直接摘录包含该结论的文献原文句子或表格摘要")
    figure_or_table: str | None = Field(default=None, max_length=64, description="出处图表号，如 Fig. 2(a), Table 1")
    page_number: int = Field(default=1, ge=1, description="文献所在页码")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="抽取置信度")

    @model_validator(mode="after")
    def compute_normalization(self) -> PhaseChangePropertyCandidate:
        """自动执行规范化换算并填补规范单位 ID。"""
        cfg = CANONICAL_PROPERTY_CONFIG.get(self.property_code)
        if not cfg:
            raise ValueError(f"未知物性代码: {self.property_code}")

        # 检查输入单位是否被允许
        cleaned_unit = self.original_unit.strip()
        allowed = [u.lower() for u in cfg["allowed_input_units"]]
        if cleaned_unit.lower() not in allowed:
            err_msg = (
                f"物性 {self.property_code} 不支持单位 '{self.original_unit}'，"
                f"允许值: {cfg['allowed_input_units']}"
            )
            raise ValueError(err_msg)

        # 自动换算并赋值
        norm_val, norm_term_id = normalize_property_value(
            self.property_code, self.original_value, self.original_unit
        )
        self.normalized_value = float(norm_val)
        self.normalized_unit_term_id = norm_term_id

        # 启发式识别掺杂元素 (若未显式指定但化学式存在明显非宿主元素)
        if not self.dopant_element and self.nominal_material in ("GeTe", "Sb2Te3"):
            formula = self.sample_formula
            for possible_dopant in ("Bi", "In", "Sb", "Ag", "N", "C", "Ti", "Sc", "Cr", "Cu", "Al", "Si", "Ga"):
                if self.nominal_material == "GeTe" and possible_dopant in ("Ge", "Te"):
                    continue
                if self.nominal_material == "Sb2Te3" and possible_dopant in ("Sb", "Te"):
                    continue
                if re.search(rf"\b{possible_dopant}\b|{possible_dopant}\d+", formula):
                    self.dopant_element = possible_dopant
                    break

        return self
