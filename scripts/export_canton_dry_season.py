"""Comprueba la demanda de enero–marzo en la estación del INTA en Cañas y, si pasa, exporta cada cantón.

La cifra de Rojas y Sánchez (UCR, 2014) es evapotranspiración menos lluvia: 427,58 − 11,15 = 416,53 mm,
con desviación 157,64 mm en el polígono de Cañas. El balde FAO-56 (ETc − ETa) no es esa cifra.
Las fechas de siembra no se marcan como observadas.
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import urllib.request

from backend.app.infrastructure.cache import RawCache, write_json
from backend.app.infrastructure.power import ingest_power
from backend.app.infrastructure.soil import DEPTHS, inspect_soil
from backend.app.simulation.et0 import et0_for_days
from scripts.build_regional_setup import average_retention

ROOT = Path(__file__).resolve().parents[1]
STATION = {
    "id": "inta-ejn-canas",
    "name": "INTA Estación Experimental Enrique Jiménez Núñez",
    "latitude": 10.3197162,
    "longitude": -85.1120922,
    "elevation_m": 45.0,
    "elevation_source": "INTA: 45 msnm en la ficha del centro",
    "coordinate_source": "OpenStreetMap way 1023338870, centro del polígono nombrado",
    "validated": False,
}
STUDY_DEMAND_MM = 416.53
STUDY_ET_MM = 427.58
STUDY_RAIN_MM = 11.15
STUDY_SD_MM = 157.64
SENARA_M3_S = {"january": 5.68, "february": 6.73, "march": 8.61, "mean": 7.0}
STUDY_FLOW_M3_S = 5.91
# Retención a capacidad de campo citada por Rojas y Sánchez desde Sandoval y Mata (2014).
# El artículo no publica el punto de marchitez.
PUBLISHED_FC = {"rest_of_district_mollisols": 0.4411, "north_vertisols": 0.6116}


def inside(lon: float, lat: float, rings: list) -> bool:
    ring = rings[0]
    hit = False
    j = len(ring) - 1
    for i, point in enumerate(ring):
        xi, yi = point
        xj, yj = ring[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            hit = not hit
        j = i
    return hit


def interior(polygons: list, center: list[float]) -> tuple[float, float]:
    """Un punto dentro del polígono. El centro del geojson a veces cae fuera."""
    lon, lat = center
    if any(inside(lon, lat, rings) for rings in polygons):
        return lon, lat
    xs = [point[0] for rings in polygons for point in rings[0]]
    ys = [point[1] for rings in polygons for point in rings[0]]
    step = 0.02
    x = min(xs)
    while x <= max(xs):
        y = min(ys)
        while y <= max(ys):
            if any(inside(x, y, rings) for rings in polygons):
                return x, y
            y += step
        x += step
    raise SystemExit("no hay un punto interior en el cantón")


def canton_points() -> list[dict]:
    collection = json.loads((ROOT / "frontend/public/geo/cantons.geojson").read_text(encoding="utf-8"))
    points = []
    for feature in collection["features"]:
        if not feature["properties"].get("guanacaste"):
            continue
        geometry = feature["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        lon, lat = interior(polygons, feature["properties"]["center"])
        points.append({
            "id": feature["id"],
            "name": feature["properties"]["name"],
            "latitude": lat,
            "longitude": lon,
        })
    if len(points) != 11:
        raise SystemExit(f"se esperaban 11 cantones, hay {len(points)}")
    return points


def elevation(latitude: float, longitude: float) -> float:
    url = f"https://api.open-meteo.com/v1/elevation?latitude={latitude}&longitude={longitude}"
    request = urllib.request.Request(url, headers={"User-Agent": "AlairaX-research/1.0"})
    payload = json.loads(urllib.request.urlopen(request, timeout=30).read().decode())
    value = float(payload["elevation"][0])
    if value != value:
        raise ValueError("elevación vacía")
    return value


def season(latitude: float, longitude: float, elevation_m: float) -> dict:
    cache = RawCache(ROOT / "datasets/raw/climate-cantons")
    document = ingest_power(cache, latitude, longitude, date(2014, 1, 1), date(2014, 3, 31))
    days = document["days"]
    et0 = et0_for_days(days, latitude, elevation_m)
    if any(value is None for value in et0):
        raise ValueError(f"ET0 incompleta en {latitude}, {longitude}")
    rain = sum(day["precipitation_mm"] for day in days)
    et0_sum = sum(et0)
    return {
        "rain_mm": round(rain, 2),
        "et0_mm": round(et0_sum, 2),
        "water_demand_mm": round(et0_sum - rain, 2),
        "days": len(days),
    }


def soil_at(latitude: float, longitude: float) -> dict:
    report = inspect_soil(
        RawCache(ROOT / "datasets/raw/soil-cantons"),
        latitude,
        longitude,
        DEPTHS,
    )
    try:
        fc = average_retention(report["properties"], "wv0033")
        wp = average_retention(report["properties"], "wv1500")
    except ValueError as error:
        return {"status": "unavailable", "error": str(error), "source": "SoilGrids 2.0"}
    return {
        "status": "map",
        "field_capacity_m3_m3": fc,
        "wilting_point_m3_m3": wp,
        "source": "SoilGrids 2.0, media de 0 a 100 cm a 33 y 1500 kPa. Predicción de mapa, no medición de finca.",
    }


def main() -> None:
    station_climate = season(STATION["latitude"], STATION["longitude"], STATION["elevation_m"])
    demand_delta = round(station_climate["water_demand_mm"] - STUDY_DEMAND_MM, 2)
    passed = abs(demand_delta) <= STUDY_SD_MM
    check = {
        "schema_version": "0.1.0",
        "_mock": False,
        "sowing_dates_observed": False,
        "station": STATION,
        "period": "2014-01-01/2014-03-31",
        "definition": "water_demand_mm = ET0 Penman-Monteith FAO-56 menos lluvia POWER. Esa resta es la cantidad comparable con los 416,53 mm (evapotranspiración del cultivo menos lluvia en el estudio). No es el déficit de balde Σ(ETc−ETa). La capacidad de campo publicada se registra como suelo de la estación y no entra en la resta.",
        "study": {
            "citation": "Rojas González y Sánchez Chinchilla, UCR, 2014. CIGR Proceedings.",
            "et_mm": STUDY_ET_MM,
            "rain_mm": STUDY_RAIN_MM,
            "water_demand_mm": STUDY_DEMAND_MM,
            "sd_mm": STUDY_SD_MM,
            "flow_m3_s": STUDY_FLOW_M3_S,
            "senara_m3_s": SENARA_M3_S,
            "published_field_capacity_m3_m3": PUBLISHED_FC,
            "wilting_point": "no publicado en el artículo",
        },
        "station_result": station_climate,
        "station_soil": {
            "source": "Sandoval y Mata 2014, citados por Rojas González y Sánchez Chinchilla. Capacidad de campo publicada para Cañas.",
            "field_capacity_m3_m3": PUBLISHED_FC,
            "recorded_for_station": True,
            "enters_water_demand": False,
            "reason_not_in_demand": "La demanda comparable es evapotranspiración menos lluvia. La capacidad de campo no entra en esa resta.",
            "wilting_point_m3_m3": None,
            "fao56_bucket_claimed": False,
            "bucket_note": "El punto de marchitez no está publicado, así que no se afirma un balde FAO-56 completo en la estación.",
            "soilgrids_used_for_station_demand": False,
            "liberia_soil_used_for_station_demand": False,
        },
        "difference_mm": demand_delta,
        "acceptable": passed,
        "acceptance_rule": "aceptable si la diferencia absoluta no supera la desviación publicada del polígono, 157,64 mm",
    }
    write_json(ROOT / "datasets/processed/validation/canas-ucr-2014.json", check)
    print(f"Cañas estación: demanda {station_climate['water_demand_mm']} mm, diferencia {demand_delta} mm, pasa={passed}")
    if not passed:
        print("El mapa no se amplía.")
        return

    cantons = {}
    for point in canton_points():
        height = elevation(point["latitude"], point["longitude"])
        climate = season(point["latitude"], point["longitude"], height)
        ground = soil_at(point["latitude"], point["longitude"])
        cantons[point["id"]] = {
            "_mock": False,
            "name": point["name"],
            "latitude": point["latitude"],
            "longitude": point["longitude"],
            "elevation_m": round(height, 1),
            "elevation_source": "Open-Meteo elevation",
            **climate,
            "soil": ground,
            "sowing_dates_observed": False,
        }
        if point["id"] == "canas":
            cantons[point["id"]]["station_check"] = {
                "water_demand_mm": station_climate["water_demand_mm"],
                "study_mm": STUDY_DEMAND_MM,
                "difference_mm": demand_delta,
                "senara_mean_m3_s": SENARA_M3_S["mean"],
                "published_field_capacity_m3_m3": PUBLISHED_FC["rest_of_district_mollisols"],
            }
        print(point["id"], climate["water_demand_mm"], ground.get("status"))

    demands = [row["water_demand_mm"] for row in cantons.values()]
    if len(set(demands)) < 2:
        raise SystemExit("los cantones repiten la misma demanda; no se publica el mapa")
    surface = {
        "_mock": False,
        "purpose": "Demanda de agua de enero a marzo de 2014 en el centro de cada cantón. ET0 FAO-56 y lluvia NASA POWER de ese punto. No es la comparación de rotaciones del piloto de Liberia.",
        "sowing_dates_observed": False,
        "reference_check": "datasets/processed/validation/canas-ucr-2014.json",
        "warnings": [
            "El suelo de los cantones es SoilGrids, una predicción de mapa, no una medición de finca.",
            "La estación del INTA no usa ese mapa: su suelo registrado es la retención publicada de Cañas, 0,4411 y 0,6116, y no entra en la resta de la demanda.",
            "Las fechas de siembra no están observadas.",
            "La demanda es ET0 menos lluvia del trimestre seco de 2014, la misma definición que los 416,53 mm de Cañas.",
        ],
        "cantons": cantons,
    }
    write_json(ROOT / "frontend/public/data/canton-surface.json", surface)


if __name__ == "__main__":
    main()
