"""Build the explicit comparison setup for the Liberia regional pilot."""

import argparse
from datetime import date, timedelta
import json
from pathlib import Path

from backend.app.api.schemas.contracts import CropCycle, ModelAssumptions, RotationSchedule, SoilProfile
from backend.app.application.prepare_inputs import ComparisonSetup, same_zone_identity
from backend.app.infrastructure.cache import write_json

MAG_RICE = 'https://www.mag.go.cr/bibliotecavirtual/F01-8148.pdf'
MAG_MELON = 'https://www.mag.go.cr/bibliotecavirtual/A01-1277-p82.pdf'
MAG_SEASONS = 'https://www.mag.go.cr/bibliotecavirtual/P40-2728.pdf'
INTA_SORGHUM = 'https://revistas.ucr.ac.cr/index.php/ragromeso/article/download/1932/14544/52672?inline=1'
UCR_COVER = 'https://archivo.revistas.ucr.ac.cr/index.php/agromeso/article/download/31612/34044?inline=1'
UCR_SOIL = 'https://revistas.ucr.ac.cr/index.php/ragrocost/article/download/4598/6831/31237?inline=1'
SOILGRIDS = 'https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html'
FAO = 'https://www.fao.org/4/x0490e/x0490e0b.htm'
ROOT_DEPTH_CM = 100


def average_retention(properties, name):
    layers = sorted(
        (entry for entry in properties if entry['property'] == name),
        key=lambda entry: entry['depth_range']['top_depth'],
    )
    depth = total = 0
    for layer in layers:
        interval = layer['depth_range']
        if (interval['unit_depth'] != 'cm' or interval['top_depth'] != depth
                or layer['unit'] != 'm3/m3' or layer['statistic'] != 'mean'
                or layer['value'] is None):
            raise ValueError(f'{name}: expected contiguous volumetric retention in cm layers')
        bottom = min(ROOT_DEPTH_CM, interval['bottom_depth'])
        if bottom <= depth:
            raise ValueError(f'{name}: empty soil layer')
        total += (bottom - depth) * layer['value']
        depth = bottom
        if depth == ROOT_DEPTH_CM:
            return round(total / depth, 6)
    raise ValueError(f'{name}: incomplete coverage of the reference soil profile')


def cycle(crop_id, parameter_set, sowing, duration):
    return CropCycle(crop_id=crop_id, parameter_set_id=parameter_set, sowing_date=sowing,
                     harvest_date=sowing + timedelta(days=duration - 1))


def build_setup(analogs, soil_report):
    zone = analogs['zona']
    if (analogs['_mock'] or soil_report['_mock'] or zone['validated']
            or (zone['latitude'], zone['longitude']) != (10.55, -85.5)
            or not same_zone_identity(zone, soil_report['zona'])):
        raise ValueError('the Liberia pilot requires matching public climate and soil at 10.55, -85.50')
    years = sorted({neighbor['year'] for scenario in analogs['scenarios'].values()
                    if scenario['status'] == 'available' for neighbor in scenario['neighbors']})
    if not years or any(year >= 2026 for year in years):
        raise ValueError('the pilot requires historical analog years before 2026')

    soil_refs = [*soil_report['source_refs'], SOILGRIDS, UCR_SOIL]
    soil = SoilProfile(
        field_capacity_m3_m3=average_retention(soil_report['properties'], 'wv0033'),
        wilting_point_m3_m3=average_retention(soil_report['properties'], 'wv1500'),
        rooting_depth_m=ROOT_DEPTH_CM / 100, source_refs=soil_refs,
    )
    management = ModelAssumptions(
        irrigation_mode='rainfed', irrigation_mm_by_date={}, initial_soil_water_fraction=0.5,
        notes=['Todas las rotaciones se comparan en secano para estimar el déficit.',
               'El 1 de mayo se supone disponible la mitad del agua útil.'],
    )
    rotations = {}
    for year in years:
        rice = cycle('rice', 'rice', date(year, 7, 1), 120)
        alternatives = {
            'rice_melon': cycle('melon', 'melon', date(year, 12, 1), 60),
            'rice_legume': cycle('legume', 'cowpea', date(year, 11, 1), 100),
            'rice_sorghum': cycle('sorghum', 'sorghum_forage', date(year, 11, 1), 85),
        }
        rotations[year] = [RotationSchedule(rotation_id=key, calendar_status='provisional',
                                            cycles=[rice, alternative])
                           for key, alternative in alternatives.items()]
    return ComparisonSetup(
        mock=False, regional_pilot=True, generado=analogs['generado'], zona=zone,
        reviewed_by='Codex (revisión documental del piloto)',
        soil=soil, rotations_by_year=rotations, assumptions_by_year={year: management for year in years},
        source_refs=[*soil_refs, MAG_RICE, MAG_MELON, MAG_SEASONS, INTA_SORGHUM, UCR_COVER, FAO],
        warnings=[
            'Suelo estimado con SoilGrids: retención media ponderada de 0 a 100 cm a 33 y 1500 kPa.',
            'Calendario regional modelado a partir del MAG, INTA y FAO-56. Fechas y humedad inicial sin registros de finca.',
            'El déficit publicado se simula en secano para las tres rotaciones, incluido el melón.',
            'La lluvia de NASA POWER presenta un sesgo histórico frente a CHIRPS e IMN. Ver docs/rain_bias.md.',
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analogs', required=True, type=Path)
    parser.add_argument('--soil', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.resolve() in {args.analogs.resolve(), args.soil.resolve()}:
        parser.error('output must not overwrite a source artifact')
    setup = build_setup(json.loads(args.analogs.read_bytes()), json.loads(args.soil.read_bytes()))
    write_json(args.output, setup.model_dump(mode='json', by_alias=True))
    print(f'{args.output}: {len(setup.rotations_by_year)} years, three rotations per year')


if __name__ == '__main__':
    main()
