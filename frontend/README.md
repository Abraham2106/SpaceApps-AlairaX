# NandaView

Interfaz para comparar tres rotaciones de Guanacaste bajo el mismo clima histórico. El mapa es la pantalla. Las cifras salen del contrato; la interfaz no las recalcula.

## Correr

Node 22, desde `frontend/`:

```bash
npm ci
npm run dev
```

Abre `http://127.0.0.1:5173/SpaceApps-AlairaX/#/`.

Sin `VITE_API_URL` lee los fixtures de `public/data/` y muestra el aviso de datos sintéticos. Con una URL, por ejemplo `http://127.0.0.1:8000`, prueba `GET /health` y usa `GET /scenarios`, `GET /rotations`, `GET /sources` y `POST /compare`. Un 409 o un 503 se muestran con el motivo. La misma dirección se puede escribir en Confianza.

```bash
npm test
npm run build
npm run preview
npx playwright test
```

El build usa `base: /SpaceApps-AlairaX/` y `HashRouter`, que es lo que publica GitHub Pages.

## Estructura

- `src/lib/` tipos, validación zod, prosa determinista, geometría y malla.
- `src/map/NandaMap.tsx` MapLibre: fotografía, NASA GIBS, relieve, cantones, malla, OSM.
- `src/screens/` Mapa, Cantones, Rotaciones, Temporada, Confianza.
- `public/geo/cantons.geojson` límites simplificados.
- `public/data/` fixtures del contrato. No se modifican.

## Decisiones

Están en `docs/ui-research.md` y `docs/ui-decisions.md`. Resumen: instrumento de campo, no un tablero. Tema Noche y tema Sol. Tres colores de rotación que también se separan en grises. La malla tiene un solo tono porque el modelo es un punto. Elegir un cantón no cambia las cifras.

## Fuentes y licencias geográficas

| Capa | Fuente | Licencia / uso |
|---|---|---|
| Cantones | geoBoundaries CRI ADM2 gbOpen, año representado 2020, geometría simplificada en este repo | CC0. Nombres con tilde de presentación; `sourceName` guarda el original. `Palmeras` se muestra como Palmares. |
| Fotografía nítida | Esri World Imagery (Maxar, Earthstar Geographics) | Atribución visible. No es un producto NASA y no entra al modelo. |
| Color real y mármol | NASA GIBS: MODIS Terra Corrected Reflectance True Color, 12 de marzo de 2024, y Blue Marble Next Generation | Imagen de contexto. Reconocimiento a NASA ESDIS. No entra al balance. |
| Imagen de la portada | NASA GIBS WMS, Terra MODIS del 12 de marzo de 2024. Recorte EPSG:4326 entre −86.42°, 9.53° y −84.65°, 11.31° | Fotografía contextual. Los límites usan geoBoundaries y el marcador usa las coordenadas del catálogo. |
| Relieve | Teselas terrarium de AWS. La tesela regional cita GMTED2010 y ETOPO1 | Solo iluminación. |
| Calles y nombres | OpenFreeMap, dato OpenStreetMap | ODbL. No se usa el servidor oficial `tile.openstreetmap.org`. La atribución aparece con la capa. |

El clima del pipeline real, cuando hay corrida, es NASA POWER (comunidad AG). Los fixtures no lo son: su `source_refs` dice `synthetic-fixture-v1`.

## Librerías

React, TypeScript, Vite, MapLibre GL JS, Zustand, TanStack Query, Zod, Vitest, Testing Library, Playwright, Lucide. Tipografías OFL: IBM Plex Sans e IBM Plex Mono. El repositorio es MIT. Esas licencias son compatibles.
