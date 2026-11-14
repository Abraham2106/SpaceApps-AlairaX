# Disponibilidad de suelo en el punto provisional

El punto `10.55, -85.50` sigue sin validación agronómica. El adaptador consulta
textura y retención en dos peticiones separadas, para que un error de las capas
hidráulicas no oculte la disponibilidad de textura.

```powershell
python scripts/inspect_soil.py
```

Por defecto consulta solamente `0-5cm`, estadístico `mean`, con timeout de
15 segundos y una tentativa por petición. Esto respeta el límite de cinco
consultas por minuto de la [entrada oficial REST](https://rest.isric.org/).
No se debe ejecutar repetidamente en un bucle. `--offline` usa solamente
respuestas exitosas ya guardadas; `--refresh` solicita un snapshot nuevo.

Se pueden seleccionar otras profundidades con `--depth 5-15cm`, repetido para
múltiples capas, y otro punto con `--latitude`/`--longitude`.

## Salida y evidencia

`datasets/processed/soil/soil_readiness_10.55_-85.5.json` contiene los intentos,
URL exacta, fecha UTC, errores reales, datos si existen y motivos que impiden
usar el perfil. Un fallo remoto produce `status=blocked`, `_mock=false` y campos
hidráulicos `null`: es un reporte real de indisponibilidad, sin valores ficticios.

Las respuestas exitosas se guardan con `RawCache`; los intentos, incluidos
fallos, quedan en `datasets/raw/soil/*.attempt.json`. Un cuerpo HTTP de error
se conserva como `.error.body` con hash en el reporte, sin tratarlo como dato.
Un timeout no tiene cuerpo de respuesta ni código HTTP confirmado.

Prueba real del 14 de noviembre de 2026: ambas peticiones (`texture` y
`water_retention`) terminaron con `TimeoutError: The read operation timed out`
al usar timeout de 15 segundos. Una prueba previa de textura con 25 segundos
también expiró. La documentación OpenAPI REST no cargó desde la herramienta web,
mientras la documentación y el catálogo ISRIC sí estuvieron accesibles.
Esto verifica un bloqueo de acceso en estos intentos; no demuestra que el punto
carezca de suelo ni que todos los servicios globales estén caídos.

## Propiedades y unidades

La [documentación de capas de ISRIC](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html)
describe textura mapeada en g/kg y contenido volumétrico a tensiones de 10,
33 y 1500 kPa. El catálogo oficial de servicios expone las capas
[`wv0033`](https://maps.isric.org/soilgrids.html) y
[`wv1500`](https://maps.isric.org/generated/soilgrids/wv1500.html).

El adaptador conserva la unidad del proveedor y normaliza únicamente unidades
reconocidas: g/kg → porcentaje de masa (`raw/10`); contenido volumétrico en
milésimas → m³/m³ (`raw/1000`). Una unidad no reconocida deja el valor normalizado
en `null` y solicita revisión. La tabla de documentación usa `wv003` en una fila,
mientras el catálogo y los servicios identifican `wv0033`; la consulta usa este
último código sin asumir que el REST beta soporte todas las capas.

## Decisiones pendientes de Justin y Ant

La textura no determina por sí sola capacidad de campo ni punto de marchitez.
Aunque exista retención a 33/1500 kPa, se conserva como evidencia por capa:
elegir esos valores como FC/WP requiere revisar el suelo, la convención de
tensión, incertidumbre y método de agregación. No se elige automáticamente.

La profundidad radicular es un parámetro del cultivo y la etapa. La consulta
superficial de 0–5 cm no representa toda la zona de raíces. El perfil que acepta
el kernel permanece con `field_capacity_m3_m3`, `wilting_point_m3_m3` y
`rooting_depth_m` en `null`, y `ready_for_simulation=false`.

Si REST sigue indisponible, ISRIC publica [WMS/WCS](https://maps.isric.org/soilgrids.html)
y [otras vías oficiales de acceso](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_02.html).
La existencia del catálogo no demuestra que un píxel concreto tenga datos
válidos. Hace falta consultar esa ubicación y revisar su procedencia.

## Consulta posterior satisfactoria · 14 noviembre 2026

La consulta configurada en el navegador integrado respondió HTTP 200 para `10.55, -85.50`: `clay`, `sand`, `silt`, `wv0033` y `wv1500`, estadístico `mean`, profundidades `0-5cm`, `5-15cm`, `15-30cm`, `30-60cm`, `60-100cm` y `100-200cm`. La CLI confirmó después ambas consultas y guardó los datos con procedencia en el reporte procesado, ahora `status=partial`.

En esta respuesta, la retención informa `mapped_units="(10-2 cm³/cm³)*10"` y `d_factor=10`: el valor crudo se divide por 1000 para obtener fracción volumétrica. Por ejemplo, en 0–5 cm, `wv0033=333` equivale a 0,333 m³/m³ y `wv1500=200` a 0,200 m³/m³. Se agregó una regresión para esta unidad observada. Son predicciones de SoilGrids; su asignación como FC/WP y la agregación al perfil radicular siguen pendientes de Justin y Ant.

## Pruebas

```powershell
python -m unittest backend.tests.test_soil -v
```

Cubren unidades, campos ausentes, separación textura/FC-WP y reporte de errores
sin sustituirlos por datos mock.
