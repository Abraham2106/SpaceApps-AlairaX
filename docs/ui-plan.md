# Plan de rediseño de la interfaz

Sale de la auditoría del 14 de noviembre de 2026 (ver `docs/ui-critique-log.md`). Las decisiones tomadas están en `docs/ui-decisions.md`. Cada fase espera el visto bueno antes de empezar.

Reglas que valen para todas las fases:

- Nunca se declara una rotación ganadora ni se da una recomendación de rendimiento o riego.
- Un `null` se escribe «sin dato».
- Toda vista que usa datos sintéticos identificados con `_mock` conserva el aviso «PRUEBA».
- No hay curvas inventadas cuando `daily_balance` viene vacío.
- Elegir un cantón no cambia las cifras.
- 2026 no se etiqueta como año análogo.

## Estado

| Fase | Tema | Estado |
|---|---|---|
| 1 | Accesibilidad | Hecha |
| 2 | Tokens y sistema visual | Hecha |
| 3 | Estructura y puntos de quiebre | Hecha |
| 4 | Pantalla del mapa | Hecha |
| 5 | Gráficos | Hecha |
| 6 | Temporada, Confianza y Cantones | Hecha |
| 7 | i18n, carga diferida y división de `MapScreen` | Hecha |
| 8 | Controles de calidad | Auditoría anterior registrada. QA del build integrado y umbral de crítica pendientes |

## Fase 1: accesibilidad (hecha)

Roles y teclado (`RadioGroup`, `Dialog`, lista de cantones), orden de encabezados, alertas de error, prueba e2e de teclado.

## Fase 2: tokens y sistema visual (hecha)

Estilos divididos en `styles/*.css`. Tokens de color, forma, texto y movimiento por tema. Panel opaco con borde de 1 px. Colores de rotación como `--rot-*`.

## Fase 3: estructura y puntos de quiebre (hecha)

CSS grid, cuatro anchos (≤767, 768–1099, ≥1100, ≥1440), barra superior sin desborde, barra lateral inferior en móvil, hoja del mapa con tres alturas.

## Fase 4: pantalla del mapa (hecha)

- Divulgación progresiva: primero la cifra y la frase; el detalle, los avisos y las limitaciones detrás de «Leer más».
- Lenguaje claro para el productor, con las reglas de `lib/plain.ts`.
- Pulir el reproductor a 768 px (control deslizante corto, «Comparar años» partido en dos líneas).
- Revisar la superposición de buscador, barra de capas y leyenda en tablet.

## Fase 5: gráficos (hecha)

- Gráficos responsivos.
- Tooltips y lectura por teclado.
- Alternar entre gráfico y tabla.
- Esqueletos de carga.

## Fase 6: Temporada, Confianza y Cantones (hecha)

Rediseño de las tres páginas con el sistema de las fases 2 y 3. El calendario de la temporada sigue con `verified: false`.

## Fase 7: i18n y rendimiento (hecha)

- Diccionario de textos único para español e inglés.
- MapLibre y su CSS se descargan al abrir Mapa. El JavaScript de entrada pasó de 1.511 kB a 456 kB minificados.
- `MapScreen` compone el buscador, la ficha de lectura, las capas, la leyenda y el reproductor.

## Fase 8: controles de calidad

### Auditoría de referencia · 14 de noviembre de 2026

- Lighthouse de accesibilidad obtuvo 100/100 en las cinco rutas, en Noche y Sol. La meta era ≥ 95.
- axe detectó cero violaciones en 46 vistas y estados.
- Se regeneraron las 31 imágenes de `docs/screenshots` con Playwright, incluida la del error en Rotaciones. La matriz principal cubre 360, 768 y 1440 px en Noche y Sol.
- Se completaron tres rondas independientes. El registro detalla los ajustes y los hallazgos visuales pendientes. La última ronda dio entre 7 y 8 de 10 en los ejes observados.

### Estado del build integrado · 15 de noviembre de 2026

- El build de `main` en `d5eb13a` incluye la portada de reproducciones 2022–2026 y las capas Sentinel‑2 y OpenAerialMap cuando hay una API conectada. [PR #9](https://github.com/Abraham2106/SpaceApps-AlairaX/pull/9)
- Pasaron las 44 pruebas unitarias del frontend y las dos pruebas dirigidas de Playwright sobre navegación por teclado y procedencia y fecha de la imagen. El build del frontend en GitHub Actions también pasó.
- El despliegue de GitHub Pages se detuvo en `actions/configure-pages` con un HTTP 404. Para publicar este build, un administrador debe configurar **Settings → Pages → Source → GitHub Actions** y volver a ejecutar el flujo. [Ejecución de Pages](https://github.com/Abraham2106/SpaceApps-AlairaX/actions/runs/43718616010)

### Pendientes para cerrar la fase

- [ ] Ejecutar la suite completa de Playwright sobre el build de producción e incluir la portada de reproducciones en la revisión de capturas.
- [ ] Repetir axe en las seis rutas, en Noche y Sol, a 360, 768 y 1440 px. Incluir estados interactivos y registrar cualquier violación. La meta es cero violaciones.
- [ ] Repetir Lighthouse de accesibilidad en las seis rutas, en Noche y Sol. Registrar los resultados por ruta y tema con la meta de ≥ 95/100.
- [ ] Verificar el sitio publicado y actualizar el registro de críticas tras las rondas de revisión visual.

Las seis rutas de la auditoría son Reproducciones (`/#/`), Mapa (`/#/mapa`), Cantones (`/#/cantones`), Rotaciones (`/#/rotaciones`), Temporada (`/#/temporada`) y Confianza (`/#/confianza`).

## Propuestas abiertas del registro de críticas

- 3: acento.
- 4: fondo del tema Sol.
- 5: alcanzar el umbral de tres rondas consecutivas con 9/10 o más.
