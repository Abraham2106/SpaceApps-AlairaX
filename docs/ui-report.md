# Reporte de la interfaz · 14 de noviembre de 2026

El umbral no está cerrado. No hay tres rondas consecutivas de críticos con ojos frescos en 9/10 o más. Lo que sigue es el estado real.

## Qué está corriendo

NandaView reemplaza el visor de OpenWeather. El mapa es la pantalla: fotografía de alta resolución, relieve iluminado, los 11 cantones de Guanacaste con borde y nombre, y el punto provisional marcado dentro de Liberia. Las secciones son Mapa, Cantones, Rotaciones, Temporada y Confianza.

Los números salen de los fixtures (`_mock: true`) con un aviso que no se cierra. p10/p50/p90 se explican como variación entre años análogos. No hay rendimiento, ahorro ni rotación ganadora. Un valor ausente se escribe «sin dato». 2026 no entra como análogo. Elegir un cantón, o un punto fuera de Guanacaste, no cambia las cifras.

## Verificación hecha

- `npm test`: 10 pruebas de Vitest en verde (fixtures, punto en Liberia, San José fuera, prosa).
- `npx tsc --noEmit` y `npx vite build` en verde con Node 22. El build avisa que el paquete de MapLibre supera 500 KB.
- Playwright: el flujo del productor (punto del modelo, Niño fuerte, frase de incertidumbre, confianza, compartir) pasa y no deja errores de consola.
- Capturas en `docs/screenshots/` para 360, 768 y escritorio, Noche y Sol. Las de mapa y cantones en escritorio, ya asentadas, muestran los once cantones separados.

## No verificado o por debajo del umbral

- No hay tres rondas de crítica externa. El registro está en `docs/ui-critique-log.md`.
- Lighthouse móvil, después de corregir el listado de cantones: accesibilidad 100, rendimiento 70. El rendimiento lo baja el peso de MapLibre.
- La API en vivo se probó en el cliente (409 y 503 se muestran y no se rellenan con el fixture). No se dejó un uvicorn levantado con el catálogo real, que hoy responde `unavailable` porque la ET0 no está revisada.
- La fluidez en un teléfono físico no se midió. El vuelo de cámara y el relieve se vieron en Chromium de escritorio y en un viewport de 360 px.

## Inconsistencias que no se tocaron

- Los fixtures son sintéticos. El catálogo real está `unavailable` por ET0 `reviewed: false`.
- `model_version` está en cada corrida, no en el sobre.
- geoBoundaries trae 83 unidades de 2020, sin tildes, y dice `Palmeras` donde el cantón es Palmares. La pantalla muestra el nombre con tilde y guarda el original.
- El WBS cita un sesgo de lluvia de +28 %. `research/provenance.md` dice que esa cifra del pitch no está verificada. La interfaz no la repite.

## Riesgos

- La fotografía nítida es Esri/Maxar, no NASA. GIBS MODIS y Blue Marble están como capas aparte y se ven más gruesas.
- El paquete es pesado por MapLibre. En un teléfono medio el primer dibujo tarda.
- La malla y la extrusión empiezan apagadas. Hay que encenderlas en el riel.
- Nandayure queda cerca del borde inferior cuando la línea de tiempo está abierta.
