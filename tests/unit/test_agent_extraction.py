"""PhaseChangeDB 文献物性抽取 Agent 与暂存闭环单元测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.application.literature_agent import extract_properties_heuristic
from app.main import app


def test_extract_properties_heuristic_crystallization_temp() -> None:
    sample_text = (
        "In this work, the crystallization temperature Tc of 5 at.% Bi-doped GeTe "
        "thin film (50 nm thick) was measured to be 215 °C at a constant heating rate of 20 K/min using DSC."
    )
    candidates = extract_properties_heuristic(sample_text)
    assert len(candidates) >= 1

    tc_cand = next((c for c in candidates if c.property_code == "crystallization_temperature"), None)
    assert tc_cand is not None
    assert tc_cand.nominal_material == "GeTe"
    assert tc_cand.dopant_element == "Bi"
    assert tc_cand.dopant_ratio_at_pct == 5.0
    assert tc_cand.original_value == 215.0
    assert tc_cand.original_unit == "°C"
    # 归一化温度：215 + 273.15 = 488.15 K
    assert tc_cand.normalized_value == 488.15
    assert tc_cand.heating_rate_k_per_min == 20.0
    assert tc_cand.film_thickness_nm == 50.0
    assert tc_cand.measurement_method == "DSC"
    assert "crystallization temperature" in tc_cand.evidence_text.lower()


def test_extract_properties_heuristic_multiple_properties() -> None:
    sample_text = (
        "For the Sb2Te3 phase change material, the melting point Tm is 618 °C. "
        "The crystallization activation energy Ea was fitted to be 2.45 eV by Kissinger plots. "
        "Moreover, the ultra-fast switching time t_cryst reaches 12 ns."
    )
    candidates = extract_properties_heuristic(sample_text)
    assert len(candidates) >= 3

    tm_cand = next((c for c in candidates if c.property_code == "melting_temperature"), None)
    assert tm_cand is not None
    assert tm_cand.original_value == 618.0
    assert tm_cand.normalized_value == 618.0 + 273.15

    ea_cand = next((c for c in candidates if c.property_code == "activation_energy"), None)
    assert ea_cand is not None
    assert ea_cand.original_value == 2.45
    assert ea_cand.original_unit == "eV"
    assert ea_cand.normalized_value == 2.45

    time_cand = next((c for c in candidates if c.property_code == "crystallization_time"), None)
    assert time_cand is not None
    assert time_cand.original_value == 12.0
    assert time_cand.original_unit == "ns"
    # 12 ns = 1.2e-8 s
    assert abs(float(time_cand.normalized_value) - 1.2e-8) < 1e-12


def test_agent_extract_api_endpoint_custom_key() -> None:
    client = TestClient(app)
    payload = {
        "text": (
            "We systematically investigated Ti-doped Sb2Te3 thin films. "
            "The crystallization temperature was found to be 230 °C at 10 K/min."
        ),
        "provider": "gemini",
        "model_name": "gemini-2.5-pro",
        "api_key": "AIzaSyTestCustomKey1234567890",
        "auto_stage": True,
    }

    resp = client.post("/v1/agents/literature-parser/extract", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert data["key_mode"] == "custom_user_key"
    assert data["candidates_extracted"] >= 1
    assert len(data["staged_candidate_ids"]) >= 1

    # 验证提取出的物性候选
    first_cand = data["candidates"][0]
    assert first_cand["property_code"] == "crystallization_temperature"
    assert first_cand["original_value"] == 230.0
    assert first_cand["normalized_value"] == 503.15  # 230 + 273.15
    assert any("ext_candidate" in log for log in data["logs"])


def test_agent_extract_api_endpoint_demo_mode() -> None:
    client = TestClient(app)
    payload = {
        "text": "The melting temperature of GeTe alloy is 725 °C.",
        "provider": "openai_compatible",
        "model_name": "deepseek-chat",
        "api_key": None,
        "auto_stage": False,
    }

    resp = client.post("/v1/agents/literature-parser/extract", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["key_mode"] == "demo_simulation"
    assert data["candidates_extracted"] >= 1
    assert len(data["staged_candidate_ids"]) == 0  # auto_stage is False
