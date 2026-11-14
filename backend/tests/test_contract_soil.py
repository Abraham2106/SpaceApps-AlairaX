"""Tests del perfil de suelo (SoilGrids → FAO-56 Tabla 19)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.simulation.contract import SoilWaterProfile


def test_from_soilgrids_converts_milli_units() -> None:
    soil = SoilWaterProfile.from_soilgrids(280.0, 140.0)

    assert soil.theta_fc == pytest.approx(0.28)
    assert soil.theta_wp == pytest.approx(0.14)
    assert soil.warnings == []
    assert "SoilGrids" in soil.source


def test_from_soilgrids_null_falls_back_to_texture() -> None:
    soil = SoilWaterProfile.from_soilgrids(None, None)

    # Loam: FAO-56 Tabla 19, punto medio (0.20-0.30) y (0.07-0.17)
    assert soil.theta_fc == pytest.approx(0.25)
    assert soil.theta_wp == pytest.approx(0.12)
    assert any("suelo estimado por textura" in w for w in soil.warnings)
    assert "Tabla 19" in soil.source


def test_partial_null_also_falls_back() -> None:
    soil = SoilWaterProfile.from_soilgrids(300.0, None)

    assert soil.theta_fc == pytest.approx(0.25)
    assert any("suelo estimado por textura" in w for w in soil.warnings)


def test_sandy_loam_fallback() -> None:
    soil = SoilWaterProfile.from_soilgrids(None, None, texture="sandy loam")

    assert soil.theta_fc == pytest.approx(0.23)
    assert soil.theta_wp == pytest.approx(0.11)


def test_unknown_texture_raises() -> None:
    with pytest.raises(ValueError, match="Textura desconocida"):
        SoilWaterProfile.from_soilgrids(None, None, texture="moon dust")


def test_wilting_point_must_be_below_field_capacity() -> None:
    with pytest.raises(ValidationError, match="theta_wp debe ser menor"):
        SoilWaterProfile.from_soilgrids(100.0, 200.0)
