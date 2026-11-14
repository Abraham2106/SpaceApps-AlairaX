# Investigación de interfaz · NandaView

Fecha: 14 de noviembre de 2026 (hora de Costa Rica). Se consultó antes de fijar la interfaz. No se copió código, texto ni estilo de ningún producto.

## Qué es el producto, leído en el repo

NandaView compara tres rotaciones de Guanacaste (`rice_melon`, `rice_legume`, `rice_sorghum`) bajo el mismo clima histórico. La línea base es arroz → melón. Las métricas del contrato son demanda hídrica, déficit hídrico modelado y días de estrés, con p10/p50/p90 entre años análogos. Fuentes del pipeline real: NASA POWER, NOAA ONI/RONI, SoilGrids, CHIRPS y el balance FAO-56. El punto `10.55, -85.50` es provisional y cae dentro del polígono de Liberia en geoBoundaries (comprobado sobre la geometría original y la simplificada).

Los JSON de `frontend/public/data/` son fixtures sintéticos (`_mock: true`, `source_refs: ["synthetic-fixture-v1"]`). El catálogo real `datasets/processed/analogs/analogos.json` tiene los cuatro escenarios en `unavailable` porque la ET0 externa no está revisada. 2026 no es análogo. No hay rendimiento, rentabilidad ni rotación ganadora.

La pantalla anterior en `frontend/src` era un visor de OpenWeather (Leaflet, emojis, clave `VITE_OPENWEATHER_KEY`). No consumía el contrato. Se reemplaza.

## Mapas de clima de primer nivel

Se miraron las capturas de Xweather Live adjuntas al encargo (Cartago, selector de foco, riel de capas con miniatura, línea de tiempo, impactos de Low a Extreme) y la propia estructura de [live.xweather.com](https://live.xweather.com/).

Qué hacen bien: el mapa es la interfaz, no un adorno; el foco cambia qué capas importan; el riel muestra la capa antes de activarla; el tiempo es un control, no un menú escondido; el panel flota y se puede cerrar.

Dónde fallan para un productor de Guanacaste: el idioma y la densidad son de meteorólogo; la escala Low–Extreme se lee como alarma aunque el texto pida cautela; no comparan una decisión de rotación; no separan “imagen” de “cifra del modelo”.

Windy y earth.nullschool enseñan partículas y atmósfera con belleza, y se vuelven ilegibles al sol y con una sola mano. Apple Weather es claro a costa de esconder la procedencia. Google Earth Engine es poderoso y opaco para quien no es analista.

Decisión que cambió: NandaView no lleva una escala de impacto de bajo a extremo. Esa escala invita a leer un fixture como una alerta. En su lugar, el foco agrícola elige la métrica del contrato (agua, demanda, estrés) y la cifra abre su procedencia.

## Producto de hackathon que convence a un jurado

Se leyó el README de [Epiq](https://github.com/vvdotcom/Epiq) (respuesta HTTP 200 el 14 de noviembre de 2026). Epiq muestra un mapa vivo, un terminal de actividad con las consultas reales del agente, un resumen de situación, patrones similares y una tendencia. Convence porque cada número parece salir de un sistema que se puede mirar trabajar, no de una tarjeta genérica.

Qué no se trae: el terminal teatral, Leaflet, MongoDB, ni un modelo SEIR. Si no hay backend, un log animado sería mentira. Decisión: el registro de NandaView enumera campos reales del contrato (años, distancias, zona, `model_version`, avisos, supuestos). Si la fuente es un fixture, la primera línea lo dice.

## Agricultura de precisión

farmOS y LiteFarm llevan registros de la finca (lotes, labores), no un ensamble climático. Climate FieldView y Farmers Edge dibujan rendimiento por lote con una densidad que aquí sería falsa: no hay mapa de cosecha. Cropwise y Ekylibre mezclan operación y normativa. FIWARE Smart Agrifood es un marco, no una pantalla.

Decisión: nada de mapas de rendimiento, ni “salud del cultivo”, ni semáforo de rentabilidad. Los cantones se separan para que se puedan nombrar y encuadrar. El color de placa distingue el límite. No pinta una variable que el modelo no calculó por cantón.

## Diseño de datos

Linear, Stripe, Observable, Datawrapper, Flourish, The Pudding y Our World in Data coinciden en pocas cosas útiles aquí: una afirmación por vista, la fuente junto a la cifra, cifras tabulares, y una tabla además del gráfico. Datawrapper insiste en no truncar una escala si eso agranda una diferencia chica.

Decisión: dos gráficos, no un dashboard de tarjetas. Uno muestra el nivel con escala desde cero (la diferencia de 20 mm no se ve enorme junto a 780 mm). Otro muestra solo el delta contra arroz → melón, que es el número que el contrato ya calculó. Debajo, la tabla.

## Incertidumbre y color

- p10/p50/p90 del contrato son cuantiles empíricos entre años análogos (`uncertainty_method: empirical_linear_quantiles_across_analog_years`). No son un intervalo de confianza ni una probabilidad de éxito. La banda sola se malinterpreta; por eso cada año análogo es un punto visible (la idea del quantile dotplot de Kay, Kola, Hullman y Munson, CHI 2016, “When (ish) is My Bus?”; el DOI respondió 403 desde este entorno, se cita el trabajo por título y autores).
- Barras de error sin decir qué resumen se evitan. Cleveland y McGill: la posición sobre una escala común se lee mejor que el área. Tufte: no dibujar lo que el dato no trae. El fixture no trae `daily_balance`; no se inventa una curva diaria.
- Escala secuencial para la métrica: anclas de cividis, perceptualmente uniforme y usable en daltonismo (Nuñez, Anderton y Renslow, PLOS ONE 2018, [10.1371/journal.pone.0199239](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0199239), HTTP 200). La malla entera usa un solo tono porque el modelo es un punto. La leyenda lo dice.
- Tres rotaciones con luminancia distinta para que se separen en grises: melón oscuro, leguminosa media, sorgo claro, más trazo continuo, discontinuo y punteado.

## Uso en el campo

Pantalla al sol, una mano, red mala, pulgares grandes, lenguaje llano. Los estudios de adopción en pequeños productores (conectividad, confianza, relevancia local; el propio WBS del repo marca el móvil y el idioma como entregables) dicen que una función de más no compensa un número que no se entiende.

Decisión: tema Sol con paneles opacos, texto grande y blancos de 44 px. Los fixtures cargan sin red. El permiso de ubicación se explica antes de pedirlo y no se guarda en un servidor. Si el punto cae fuera de Guanacaste, la cámara puede ir, pero las cifras no se trasladan.

## Cartografía

Se probó, el 14 de noviembre de 2026:

| Fuente | Resultado | Uso |
|---|---|---|
| geoBoundaries CRI ADM2 gbOpen, geometría simplificada (commit `9469f09`) | HTTP 200, 83 unidades, licencia declarada CC0, año representado 2020 | Límites. Se simplificó en el repo (108 KB) |
| NASA GIBS MODIS Terra Corrected Reflectance True Color, 2024-03-12, `GoogleMapsCompatible_Level9` | HTTP 200, CORS `*` | Capa científica de color real. Zoom máximo 9 |
| NASA GIBS Blue Marble Next Generation | HTTP 200, CORS `*` | Contexto global |
| NASA GIBS VIIRS true color y un identificador NDVI de prueba | 400 y 404 | No se muestran: no responden con el URL probado |
| Esri World Imagery | HTTP 200, CORS `*` con `Origin` | Fotografía de alta resolución. No es NASA |
| Teselas terrarium de AWS | HTTP 200, CORS `*`. La tesela z6 de la región cita GMTED2010 y ETOPO1 | Relieve e iluminación. No es una métrica |
| OpenFreeMap `styles/liberty` y `planet` | HTTP 200, CORS `*` | Calles y nombres OSM |
| `tile.openstreetmap.org` | HTTP 200 | No se usa como mapa base |

[Política de teselas de OSMF](https://operations.osmfoundation.org/policies/tiles/): el servidor oficial no es un CDN de una aplicación. [Atribución OSM](https://wiki.openstreetmap.org/wiki/Attribution): hay que nombrar a los colaboradores cuando se usa el dato. OpenFreeMap publica teselas vectoriales de OSM para este uso, sin clave. MapLibre GL JS es el render recomendado para ese estilo de tesela, con terreno, luz y extrusión. Leaflet no tiene terreno nativo. deck.gl sumaría otro contexto WebGL para una malla regular que MapLibre ya dibuja; en un teléfono medio no se justifica.

IGN/SNIT sería el catastro oficial, con condiciones de redistribución distintas. No se redistribuye. Los nombres de geoBoundaries vienen sin tildes (`Canas`, `Tilaran`) y uno sale como `Palmeras` donde el cantón se llama Palmares. La interfaz muestra el nombre con tilde y guarda `sourceName`.

Los 11 de Guanacaste están en la capa: La Cruz, Liberia, Bagaces, Carrillo, Cañas, Tilarán, Abangares, Nicoya, Santa Cruz, Hojancha, Nandayure. El resto del país se dibuja y, al tocarlo, dice que no hay simulación.

## NASA: qué entra hoy y qué no

En el pipeline, cuando hay datos reales, el clima diario es NASA POWER, comunidad `AG`, unidades métricas, hora solar local (documentado en `docs/scientific_method.md` y en [la API diaria de POWER](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)). Variables: `PRECTOTCORR`, `T2M_MIN`, `T2M_MAX`, `RH2M`, `WS2M`, `ALLSKY_SFC_SW_DWN`. El catálogo real lista esas URL. El balance es FAO-56 ([Allen et al., 1998](https://www.fao.org/4/x0490e/x0490e00.htm)), no un producto NASA. ONI/RONI son NOAA. El suelo es SoilGrids. CHIRPS no es NASA.

En el mapa, y solo como imagen: GIBS MODIS y Blue Marble, con el reconocimiento a NASA ESDIS. La fotografía nítida es Esri/Maxar y se etiqueta como tal para no hacerla pasar por NASA. El relieve ilumina; no se agrega al balance.

No entran en las cifras, y la pantalla de confianza lo dice: GPM IMERG (lluvia más fina; el WBS lo dejó en P2 por el EULA), SMAP (humedad de suelo, no un perfil hidráulico medido) y HLS (30 m de contexto; `research/provenance.md` dice que no entra al balance). Usarlos “de más” sería pintar un campo espacial que el contrato no entrega. El plan está en la vista Confianza, separado de los números.

## Accesibilidad

WCAG 2.2 AA: contraste en los dos temas, foco visible, nombres en los controles, tabla además del SVG, el mapa con alternativa en lista, `prefers-reduced-motion` con vuelo de cámara en duración cero. El lienzo del mapa no es el único camino al cantón.

## Inconsistencias que la UI no “arregla”

- El fixture parece una comparación completa. El catálogo real está `unavailable` por ET0. Son cosas distintas y la interfaz no las mezcla.
- `model_version` vive en cada corrida, no en el sobre de `CompareResponse`.
- El aviso de muestra del fixture está en inglés. Se muestra el original y una frase en español hecha con reglas, sin borrar el original.
- El WBS menciona un sesgo de lluvia de POWER de +28 %. `research/provenance.md` dice que el origen de esa cifra del pitch no está verificado. La interfaz no la repite.
- `rotations.json` dice «Arroz → melón». `rotations.yaml` dice «Arroz secano → Melón regado» y marca el calendario como no verificado. Se usa el nombre de la fuente que está cargada.
- La ventana de análogos documentada es 1 de abril–31 de octubre. El YAML agrícola corre de mayo a abril. El encargo pide una temporada de abril a diciembre. La línea de tiempo muestra esos meses y marca las siembras como referencia no validada, no como fenología observada.
