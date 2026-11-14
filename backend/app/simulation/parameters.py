"""Carga de parámetros agronómicos desde YAML (research/parameters/).

Los YAML son la única fuente de parámetros del kernel: nada se hardcodea en las
ecuaciones. Cada entrada lleva ``source`` y ``verified: false`` hasta que I3 la
revise; ``null`` significa "sin fuente citada", nunca "valor cero".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backend.app.simulation.contract import CropLibrary, RotationLibrary


def _read_yaml(path: str | Path) -> dict[str, Any]:
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(f"No existe el archivo de parámetros: {file}")
    with file.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{file} debe contener un mapeo YAML en la raíz.")
    return data


def load_crops(path: str | Path) -> CropLibrary:
    """Carga ``crops.yaml`` y valida contra :class:`CropLibrary`."""
    return CropLibrary.model_validate(_read_yaml(path))


def load_rotations(path: str | Path) -> RotationLibrary:
    """Carga ``rotations.yaml`` y valida contra :class:`RotationLibrary`."""
    return RotationLibrary.model_validate(_read_yaml(path))
