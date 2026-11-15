# Piloto regional de Liberia

El punto de referencia es 10.55° N, 85.50° O. El clima diario procede de NASA POWER y el índice ENOS del snapshot NOAA ONI del 14 de noviembre de 2026. FAO‑56 calcula demanda, déficit hídrico y días de estrés para las tres rotaciones. La interfaz identifica el alcance regional y la validación de finca pendiente. Los resultados llevan `_mock: false`, el punto conserva `validated: false` y los calendarios siguen como `provisional`.

| Insumo | Valor usado y fundamento |
| --- | --- |
| Arroz de secano | Siembra el 1 de julio, ciclo de 120 días. El [estudio regional alojado por el MAG](https://www.mag.go.cr/bibliotecavirtual/F01-8148.pdf) describe un ciclo de unos 120 días y siembra en julio–agosto para la Chorotega de secano, incluida Liberia. El estudio del [IMN sobre Liberia](https://www.imn.ac.cr/documents/10179/602859/Art-5-2015-2-Quesada%26Waylen/1b4ae7d6-ce1e-40dc-bc2d-d70401e0a92b) documenta la estacionalidad de la lluvia. El kernel escala las etapas FAO‑56 a 120 días y conserva la advertencia por usar Kc y agotamiento de arroz inundado como aproximación para secano. |
| Melón | Siembra el 1 de diciembre, ciclo de 60 días hasta la primera cosecha. El [almanaque del MAG](https://www.mag.go.cr/bibliotecavirtual/P40-2728.pdf) incluye diciembre y la [ficha de diversificación en Guanacaste](https://www.mag.go.cr/bibliotecavirtual/A01-1277-p82.pdf) sitúa la primera cosecha alrededor del día 60. Las métricas de esta comparación usan secano en las tres alternativas. |
| Caupí | Siembra de referencia el 1 de noviembre después del arroz. Ciclo de 100 días según la suma de etapas de [FAO‑56](https://www.fao.org/4/x0490e/x0490e0b.htm). La [literatura de cobertura publicada por la UCR](https://archivo.revistas.ucr.ac.cr/index.php/agromeso/article/download/31612/34044?inline=1) documenta el uso de *Vigna unguiculata* como abono verde en Latinoamérica. La fecha, variedad y terminación siguen siendo supuestos del piloto. |
| Sorgo forrajero | Siembra de referencia el 1 de noviembre y primer corte a los 85 días. El [ensayo de materiales BMR del INTA en Cañas](https://revistas.ucr.ac.cr/index.php/ragromeso/article/download/1932/14544/52672?inline=1) registró esa duración en época seca con riego y siembra en enero. La duración se traslada como supuesto al piloto de secano en Liberia. Se usa el Kc de sorgo dulce de FAO‑56 como aproximación para BMR. |
| Suelo | Capacidad de campo de 0,33205 m³/m³ y punto de marchitez de 0,20040 m³/m³, medias ponderadas por espesor de las capas de 0 a 100 cm de [SoilGrids](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html) a 33 y 1500 kPa. El [estudio de la UCR sobre retención en suelos costarricenses](https://revistas.ucr.ac.cr/index.php/ragrocost/article/download/4598/6831/31237?inline=1) documenta esas tensiones. Se supone un metro de profundidad efectiva y 50 % del agua útil al inicio del 1 de mayo. Las capas son predicciones espaciales. |

Niño fuerte, Neutro y Niña usan abril–octubre y ONI de agosto a octubre para elegir 3, 5 y 5 análogos. «Como 2026» usa **abril–agosto y ONI de junio a agosto** para elegir 5 análogos. Así se usa únicamente clima completo antes del faltante de radiación del 7 de septiembre. Las 54 corridas del balance hídrico usan temporadas históricas completas de mayo a abril. Los cuantiles describen la muestra de años análogos. El [sesgo histórico de lluvia POWER](rain_bias.md) y el [backtest preliminar](kernel_validation.md) limitan la interpretación de los rangos. El mapa sintético por cantón conserva su propia etiqueta. Para validación en finca hacen falta coordenadas, perfil de suelo medido, registros de siembra y de manejo, y observaciones para cotejar el balance.

## Reproducción

Desde la raíz, con los insumos del repo y las dependencias de Python y frontend instaladas:

```powershell
$climateFiles = (Get-ChildItem datasets/processed/climate/power_*.json).FullName
$et0 = 'datasets/processed/et0/et0_10.55_-85.5.json'
$analogs = 'datasets/processed/analogs/analogos.json'
$setup = 'configs/regions/guanacaste-pilot.setup.json'
foreach ($scenarioId in @('neutral', 'strong_el_nino', 'la_nina', 'like_2026')) {
    python -m scripts.prepare_comparison --analogs $analogs --scenario $scenarioId --climate $climateFiles --et0 $et0 --setup $setup --start-mmdd 05-01 --end-mmdd 04-30 --end-year-offset 1 --output "outputs/inputs/$scenarioId.json"
    if ($LASTEXITCODE) { throw "Falló la preparación de $scenarioId" }
    python -m scripts.run_comparison --analogs $analogs --scenario $scenarioId --inputs "outputs/inputs/$scenarioId.json" --kernel backend.app.simulation.kernel:simulate_rotation --output "outputs/regional-pilot/public/compare-$scenarioId.json"
    if ($LASTEXITCODE) { throw "Falló la comparación de $scenarioId" }
}
python -m scripts.export_pilot_site_data --analogs $analogs --comparisons-dir outputs/regional-pilot/public --output-dir frontend/public/data
npm.cmd --prefix frontend run build
python -m scripts.qa_scientific_release --regional-pilot
```

Para regenerar los análogos con ese corte, ejecutar `python -m scripts.build_analogs --climate $climateFiles --oni datasets/processed/climate/oni.json --et0 $et0 --start-mmdd 04-01 --end-mmdd 10-31 --oni-season ASO --tracking-end-mmdd 08-31 --tracking-oni-season JJA --as-of 2026-11-14`. Para reconstruir el setup, ejecutar `python -m scripts.build_regional_setup --analogs $analogs --soil datasets/processed/soil/soil_readiness_10.55_-85.5.json --output $setup`.
