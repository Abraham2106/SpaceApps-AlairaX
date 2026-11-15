"""Tests de los YAML de parámetros y del contrato de rotaciones."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.simulation.contract import CropSegment, KernelAssumptions, RotationTemplate
from backend.app.simulation.parameters import load_crops, load_rotations

PARAMS = Path(__file__).resolve().parents[2] / "research" / "parameters"


@pytest.fixture(scope="module")
def crops():
    return load_crops(PARAMS / "crops.yaml")


@pytest.fixture(scope="module")
def rotations():
    return load_rotations(PARAMS / "rotations.yaml")


def test_crops_yaml_loads_expected_ids(crops) -> None:
    assert set(crops.crops) == {"rice", "melon", "cowpea", "sorghum", "sorghum_forage", "mucuna", "canavalia"}
    assert crops.version == "0.1.0"
    assert all(not crop.verified for crop in crops.crops.values())


def test_fao_values_are_cited(crops) -> None:
    rice = crops.crops["rice"]
    assert rice.kc_mid == pytest.approx(1.20)
    assert rice.stage_days == [30, 30, 60, 30]
    assert rice.root_depth_max_m == pytest.approx(1.0)
    assert rice.p_depletion == pytest.approx(0.20)
    assert rice.source is not None and "Tabla 12" in rice.source

    sorghum = crops.crops["sorghum"]
    assert sorghum.kc_end == pytest.approx(0.55)
    assert sorghum.p_depletion == pytest.approx(0.55)


def test_crops_without_fao_data_are_null_and_warned(crops) -> None:
    for crop_id in ("mucuna", "canavalia"):
        crop = crops.crops[crop_id]
        assert crop.kc_ini is None and crop.kc_mid is None and crop.kc_end is None
        assert crop.stage_days is None
        assert crop.root_depth_max_m is None
        assert crop.p_depletion is None
        assert crop.source is None
        assert crop.warnings, f"{crop_id} debe explicar por qué faltan datos"


def test_rotations_yaml_has_three_rotations(rotations) -> None:
    ids = {rotation.rotation_id for rotation in rotations.rotations}
    assert ids == {"rice_melon", "rice_legume", "rice_sorghum"}


def test_exactly_one_current_rotation(rotations) -> None:
    current = [r for r in rotations.rotations if r.is_current]
    assert len(current) == 1
    assert current[0].rotation_id == "rice_melon"


def test_rotations_reference_existing_crops(rotations, crops) -> None:
    for rotation in rotations.rotations:
        for segment in rotation.segments:
            assert segment.crop_id in crops.crops


def test_rice_is_rainfed_and_melon_irrigated(rotations) -> None:
    rice_melon = next(r for r in rotations.rotations if r.rotation_id == "rice_melon")
    rice_segment, melon_segment = rice_melon.segments

    assert rice_segment.crop_id == "rice"
    assert rice_segment.sowing_mmdd == "05-15"
    assert rice_segment.irrigated is False
    assert rice_segment.regime == "upland"
    assert melon_segment.crop_id == "melon"
    assert melon_segment.sowing_mmdd == "12-01"
    assert melon_segment.irrigated is True


def test_legume_and_sorghum_rotations_are_rainfed(rotations) -> None:
    for rotation_id in ("rice_legume", "rice_sorghum"):
        rotation = next(r for r in rotations.rotations if r.rotation_id == rotation_id)
        assert all(not segment.irrigated for segment in rotation.segments)
        assert all(segment.regime == "upland" for segment in rotation.segments)


def test_invalid_sowing_date_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CropSegment(crop_id="rice", sowing_mmdd="13-45")


def test_repeated_crop_in_rotation_is_rejected() -> None:
    with pytest.raises(ValidationError, match="repite cultivos"):
        RotationTemplate(
            rotation_id="bad",
            name="Repite arroz",
            segments=[
                CropSegment(crop_id="rice", sowing_mmdd="06-01"),
                CropSegment(crop_id="rice", sowing_mmdd="12-01"),
            ],
        )


def test_model_assumptions_defaults_match_decisions() -> None:
    assumptions = KernelAssumptions()

    assert assumptions.initial_depletion_fraction == pytest.approx(0.5)
    assert assumptions.runoff_threshold_mm == pytest.approx(60.0)
    assert assumptions.runoff_fraction == pytest.approx(0.3)
    assert assumptions.kc_fallow == pytest.approx(0.15)
    assert assumptions.flooded_percolation_mm_day == pytest.approx(4.0)
    assert assumptions.irrigation_rule == "refill_at_raw"
    assert assumptions.season_start_mmdd == "05-01"
