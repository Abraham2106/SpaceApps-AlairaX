# Decisiones de interfaz

Cada decisión sale de `docs/ui-research.md` o del contrato. Si una crítica obliga a cambiarla, se anota aquí y en el registro de críticas.

## Identidad

Instrumento de campo sobre una fotografía del territorio, no un tablero. Esquinas rectas, borde de 1 px, sin sombra blanda, sin gradiente morado, sin emoji. Tipografía: Source Serif 4 para el nombre y los cantones, IBM Plex Sans para la interfaz, IBM Plex Mono para las cifras. Las tres son OFL y se sirven desde el paquete, no desde una CDN en tiempo de ejecución.

Tema Noche: la identidad del instrumento, texto claro sobre tinta verde muy oscura, paneles casi opacos para que el satélite no compita con la lectura. Tema Sol: el modo de alto contraste para el celular al sol; paneles crema opacos, sin desenfoque, texto más grande. `prefers-contrast: more` abre en Sol. `prefers-reduced-motion: reduce` corta transiciones y pone el vuelo de cámara en duración cero.

Rotaciones, fijas en todos los gráficos:

- Arroz → melón, `#143d66`, trazo continuo (la referencia).
- Arroz → leguminosa, `#1f7a6b`, trazo discontinuo.
- Arroz → sorgo, `#c9842a`, trazo punteado.

La luminancia baja, media y alta los separa en grises. La métrica activa usa una escala cividis de un solo valor en toda la malla.

## Mapa

MapLibre GL JS. No Leaflet (no tiene terreno ni extrusión decente) y no deck.gl (otro contexto WebGL para una malla que MapLibre dibuja).

Capas, de abajo hacia arriba:

1. Fotografía Esri World Imagery, por defecto. Es la única base nítida a escala de cantón sin clave. La atribución dice Esri, Maxar y Earthstar Geographics. No se llama “capa NASA”.
2. Alternativas, excluyentes: color real NASA MODIS Terra del 12 de marzo de 2024 (GIBS, zoom máximo 9) y NASA Blue Marble.
3. Relieve terrarium (AWS), con luz cálida desde el noroeste y horizonte de estación seca. Solo iluminación. La tesela regional cita GMTED2010 y ETOPO1; no se afirma que todo el relieve sea SRTM.
4. Cantones. Relleno bajo para que se vea el suelo. Filete oscuro grueso y filete claro fino para que los vecinos no se peguen. Los 11 de Guanacaste llevan nombre. El resto queda atenuado.
5. Malla hexagonal regular en grados, tres tamaños según el zoom, solo sobre Guanacaste, un solo color. La extrusión, si se enciende, tiene altura constante: una meseta, no un campo inventado.
6. Placas 3D de cantón, optativas, misma idea: altura constante, color de identidad.
7. Calles y poblados de OpenFreeMap (dato OSM, esquema OpenMapTiles), desde un zoom cercano. No se usa `tile.openstreetmap.org`. La atribución de OSM aparece cuando la capa está encendida, y el crédito de límites y de imagen está siempre.

La cámara se queda en planta. El borde de los cantones es una línea fina, sin relleno de territorio ni filete negro: el contorno grueso se leía como un mapa de estrategia, no como un instrumento. El acento es un cian de lectura, no un dorado. El punto del modelo se marca con la coordenada, no con una ficha. El punto del modelo es el `zona` de la respuesta, no un marcador fijo en el código.

## Datos

Sin `VITE_API_URL` y sin una URL escrita en Confianza, se leen los fixtures con `import.meta.env.BASE_URL`. Si hay URL, se prueba `GET /health`. Si responde, `GET /scenarios`, `GET /rotations`, `GET /sources` y `POST /compare` con la zona y el `k` del catálogo. Un 409 o un 503 se muestran con el `detail`, y no se rellenan con el fixture. El modo queda escrito en la barra.

Los tipos de `src/lib/types.ts` siguen los JSON Schema de `docs/contracts/`. Zod valida lo que el navegador recibe, incluidos los cuatro fixtures. La interfaz no recalcula p10/p50/p90 ni el delta. La prosa sale de reglas en `src/lib/plain.ts`.

## Honestidad que se ve

- `_mock: true` deja un aviso fijo. No se puede cerrar.
- Un `null` se escribe «sin dato» y no se dibuja en el cero.
- El tamaño de muestra, los avisos, las limitaciones y la `model_version` de las corridas están en el registro.
- 2026 no se etiqueta como análogo. El escenario «Como 2026» lo explica.
- Elegir un cantón no cambia las cifras. La frase lo dice. Fuera de Guanacaste, tampoco.
- El calendario de la temporada usa las fechas de `research/parameters/rotations.yaml` y las etapas de `crops.yaml`, con `verified: false`. No hay curva diaria si `daily_balance` viene vacío.

## Rutas

HashRouter, base `/SpaceApps-AlairaX/`. Secciones: Mapa, Cantones, Rotaciones, Temporada, Confianza. El estado compartible (escenario, métrica, tema, idioma, cantones, años) va en la consulta del hash.

## Qué se dejó fuera a propósito

- OpenWeather y cualquier clima en vivo que no sea el contrato.
- Choropleth de cantones por métrica.
- H3 como si hubiera un índice espacial.
- Una escala Low–Extreme.
- Traducir en silencio los avisos del archivo: se muestran y, además, se explican en español.
