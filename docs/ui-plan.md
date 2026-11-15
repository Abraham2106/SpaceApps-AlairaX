# Plan de rediseño de la interfaz

Sale de la auditoría del 14 de noviembre de 2026 (ver `docs/ui-critique-log.md`). Las decisiones tomadas están en `docs/ui-decisions.md`. Cada fase espera el visto bueno antes de empezar.

Reglas que valen para todas las fases:

- Nunca se declara una rotación ganadora ni se da una recomendación de rendimiento o riego.
- Un `null` se escribe «sin dato».
- El aviso `_mock` / «PRUEBA» es permanente.
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
| 8 | Controles de calidad | Mediciones, capturas y tres rondas hechas. Umbral de crítica pendiente |

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

- Lighthouse de accesibilidad obtuvo 100/100 en las cinco rutas, en Noche y Sol. La meta era ≥ 95.
- axe detectó cero violaciones en 46 vistas y estados.
- Se regeneraron las 31 imágenes de `docs/screenshots` con Playwright, incluida la del error en Rotaciones. La matriz principal cubre 360, 768 y 1440 px en Noche y Sol.
- Se completaron tres rondas independientes. El registro detalla los ajustes y los hallazgos visuales pendientes. La última ronda dio entre 7 y 8 de 10 en los ejes observados.

## Propuestas abiertas del registro de críticas

- 3: acento.
- 4: fondo del tema Sol.
- 5: alcanzar el umbral de tres rondas consecutivas con 9/10 o más.
