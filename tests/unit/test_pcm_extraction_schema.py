from uuid import UUID

import pytest

from app.domain.pcm_extraction_schema import (
    PhaseChangePropertyCandidate,
    normalize_activation_energy,
    normalize_temperature,
)


def test_temperature_normalization():
    # 200 °C -> 473.15 K
    val_k, term_id = normalize_temperature(200.0, "°C")
    assert float(val_k) == 473.15
    assert isinstance(term_id, UUID)

    # 450 K -> 450 K
    val_k2, term_id2 = normalize_temperature(450.0, "K")
    assert float(val_k2) == 450.0

def test_activation_energy_normalization():
    val_ev, term_id = normalize_activation_energy(2.35, "eV")
    assert float(val_ev) == 2.35
    assert isinstance(term_id, UUID)

    val_ev_kj, _ = normalize_activation_energy(250.0, "kJ/mol")
    assert round(float(val_ev_kj), 2) == 2.59

def test_phase_change_property_candidate_validation():
    candidate = PhaseChangePropertyCandidate(
        property_code="crystallization_temperature",
        nominal_material="GeTe",
        sample_formula="Ge45Bi5Te50",
        dopant_ratio_at_pct=5.0,
        original_value=210.0,
        original_unit="°C",
        heating_rate_k_per_min=20.0,
        measurement_method="DSC",
        film_thickness_nm=50.0,
        substrate="SiO2/Si",
        evidence_text="As shown in Fig. 2(a), the crystallization temperature Tx of Ge45Bi5Te50 is 210 °C at 20 K/min.",
        figure_or_table="Fig. 2(a)",
        page_number=3,
        confidence=0.95,
    )
    # 自动识别 dopant_element 为 Bi
    assert candidate.dopant_element == "Bi"
    # 自动归一化 210 °C -> 483.15 K
    assert candidate.normalized_value == 483.15
    assert candidate.normalized_unit_term_id is not None

def test_invalid_unit_rejection():
    with pytest.raises(ValueError, match="不支持单位"):
        PhaseChangePropertyCandidate(
            property_code="crystallization_temperature",
            nominal_material="GeTe",
            sample_formula="GeTe",
            original_value=210.0,
            original_unit="kg",  # 非法单位
            evidence_text="Invalid measurement text snippet",
        )
