# Registro de críticas de la interfaz

Ejes, cada uno de 0 a 10: claridad para un productor no técnico, jerarquía visual, identidad propia, fluidez del mapa, belleza de las gráficas, accesibilidad, rendimiento percibido, estados vacío/error/carga, honestidad científica, calidad móvil.

Un defecto real de un crítico con ojos frescos pone la cuenta de rondas consecutivas en cero. No hay todavía tres rondas seguidas en 9 o más. El umbral del encargo no está cerrado.

## Ronda 0 · mirada propia sobre capturas renderizadas

Capturas en `docs/screenshots/`, tomadas con Playwright el 14 de noviembre de 2026 (hora de Costa Rica) en 360, 768 y escritorio, tema Noche y tema Sol.

Defectos que ya se corrigieron en el mismo ciclo, antes de darlas por vistas:

- El panel inferior tapaba el satélite y, en el celular, el mapa quedaba en una franja.
- La atribución flotaba encima del texto de los cantones.
- La página de rotaciones se fotografió en «Cargando…» porque la espera era corta. La espera ahora es el contenido.
- Tres párrafos repetían el mismo descargo. Quedó una sola frase y una línea por rotación.

Lo que sigue débil, a ojo, y por eso no se declara un 9:

- En la vista oblicua los límites blancos compiten con el relieve y con el golfo. Hace falta confirmar en la próxima ronda de ojos frescos que los once cantones se leen sin explicación.
- La malla y la extrusión 3D existen como capas, pero no son el estado inicial. Un crítico puede no encontrarlas.
- El gráfico cabe, y todavía no tiene la calma editorial de una pieza de Our World in Data.
- No hay ronda de cinco críticos externos sobre estas capturas.

## Ronda 1 · ojos frescos, 14 de noviembre de 2026

Cinco críticos vieron una captura de la vista principal, sin el código. Todos encontraron defectos reales. La cuenta de rondas consecutivas en 9 o más vuelve a cero.

| Crítico | Claridad | Jerarquía | Identidad | Mapa | Gráficas | Accesibilidad | Rendimiento | Estados | Honestidad | Móvil |
|---|---|---|---|---|---|---|---|---|---|---|
| [Diseño de producto](bc-b98758ac-c49e-5c48-8047-f322a9e6d286) | 2 | 2 | 2 | 3 | no visto | 2 | 4 | no visto | 4 | no visto |
| [Visualización](bc-ae1c4683-5c99-5c57-be78-925129d1d11e) | 2 | 2 | 2 | no visto | no visto | 3 | no visto | 3 | 3 | no visto |
| [Accesibilidad](bc-d815477b-d6b2-5975-96b6-00264cd23578) | 2 | 2 | 2 | 3 | no visto | 2 | no visto | 2 | 4 | no visto |
| [Productor agrícola](bc-33b07f73-3ee3-582e-9c31-0ebadb5c6edf) | 2 | 3 | 2 | no visto | no visto | 2 | no visto | 2 | 3 | no visto |
| [Cartografía](bc-6efae56c-edf4-5724-a32a-ccb9fcc44513) | 2 | 3 | 2 | no visto | 2 | 3 | no visto | 3 | 4 | no visto |

Defectos que se corrigen ahora, porque son reales y no piden inventar una rotación ganadora:

- La ficha decía «delta» y «n = 3». Pasa a «menos que arroz → melón» y «años parecidos».
- El aviso decía FIXTURE y `_mock`. Pasa a «PRUEBA» y «cifras de prueba».
- El punto del mapa mostraba una coordenada ilegible. Muestra el valor y el cantón.
- Las capas se llamaban Nítida, MODIS, 3D y OSM. Pasan a Foto, Color NASA, Altura y Calles.
- Cada cantón repetía «Guanacaste». El buscador parecía un lugar ya elegido.

No se corrige el pedido de declarar una rotación ganadora, un rendimiento o una recomendación de riego. El contrato no lo permite.

## Medición del 14 de noviembre de 2026, noche

No es una ronda de cinco críticos ni cierra el umbral de 9/10. Lighthouse móvil, solo accesibilidad, sobre el preview de esta rama: primero 97, con un fallo de contraste en el enlace activo del menú. El fondo activo pasó a `#0c5a30` con texto blanco y la segunda medición dio 100. Vitest: 11/11. El guion del productor recorrió mapa, Liberia, «Leer más», Confianza y compartir sin errores de consola. Faltan las capturas de 360/768/escritorio en Sol y tres rondas de ojos frescos sin un defecto real.

## Auditoría de sistema · 14 de noviembre de 2026, rama `justin/ui-mejoras`

Mirada propia sobre el código y las capturas. No es una ronda de cinco críticos ni cierra el umbral de 9/10. Se mejora dentro de `ui-decisions.md` sin reemplazarlo.

### Hallazgos

- **El tema Sol estaba roto.** Barra superior, menú, paneles de vidrio, buscador, leyenda, botones de capa, reproductor y diálogo de año tenían colores de Noche escritos a mano. Con Sol encendido, el texto oscuro caía sobre el vidrio oscuro (1,0:1) y `--danger` de Sol sobre ese vidrio daba 2,1:1. «FIXTURE» y «ESCENARIO» no se veían. Se nota en `map-sun-360.png` de la ronda anterior.
- **Botón activo del selector de escenario:** blanco sobre `#1f8a4c` daba 4,27:1, por debajo de AA.
- **Blancos táctiles:** el resumen de atribución medía 22 px de alto y «Ver la gráfica» no tenía alto mínimo.
- **Menú móvil a 360 px:** «Rotaciones» y «Temporada» se cortaban («Rotacion», «Temporac») a 0,62 rem.
- **Estados:** Temporada y Confianza no mostraban carga ni error. El error del mapa no ofrecía reintentar. La carga no se anunciaba a lectores de pantalla.
- **Letra de 0,62 rem** en el subtítulo de la marca, la leyenda, los botones de capa y los meses del reproductor.
- **Temporada:** las marcas del eje usaban hex sueltos y no coincidían con la lista. La marca de mayo (arroz) tenía el color de melón y la de diciembre (melón) el de sorgo.
- **El guion e2e** escribía en `/agent/...` y `/opt/cursor/...`, rutas de otra máquina. En Windows creaba carpetas en la raíz del disco.
- Movimiento reducido ya se respetaba en el mapa (`reducedMotion()` pone duración 0). El foco visible ya existía.

### Cambios

- `frontend/src/index.css`:
  - Tokens consolidados para cromo, controles, selección, paneles, pista, asa, velo, escalas de letra, radios y espaciado, con valores para Noche y Sol.
  - En Noche los valores reproducen los que estaban a mano. Lo visible cambia en tres sitios: el verde activo pasa a `#1c7f46`, la letra mínima a 0,68 rem y el menú móvil.
  - Sol hace lo que dice la decisión: paneles opacos, sin desenfoque ni sombra, letra mayor y blancos de 48 px.
  - `.glass`, `.player` y `.year-pop` redefinen `--ink`, `--muted` y `--line`, así que lo que va dentro hereda el contraste del panel.
- **Contraste del botón activo:** el selector de escenario y el menú comparten `--selected-bg` `#1c7f46`. Blanco encima da 5,0:1, y el botón contra su fondo da 3,3:1 (control) y 3,6:1 (menú). La medición anterior usaba `#0c5a30` para el menú: tenía más contraste de texto, pero el botón apenas se distinguía del fondo (menos de 3:1).
- **Capa encendida:** borde doble, fondo y peso. No depende solo del color.
- **Blancos táctiles:**
  - Atribución: 24 px (WCAG 2.2, 2.5.8).
  - Enlaces sueltos en `.row`: 44 px.
  - Buscador del mapa, botones de la barra y «Leer más»: 44 px.
  - El buscador muestra el anillo de foco en el contenedor.
- **Menú móvil:** ícono arriba y nombre abajo, sin cortes a 360 px.
- `frontend/src/components/QueryState.tsx` (nuevo): carga con `role="status"` y error con `role="alert"` más «Reintentar». Lo usan Mapa, Rotaciones, Temporada y Confianza.
- `frontend/src/screens/SeasonScreen.tsx`:
  - Marcas con `ROTATION_STYLE` y `--mark-window`, ocultas a lectores porque la lista dice lo mismo.
  - Colores corregidos: mayo neutro (el arroz es común a las tres rotaciones), octubre leguminosa más sorgo, diciembre melón.
  - El aviso «sin balance diario» espera a que haya datos.
- `frontend/e2e/productor.spec.ts`:
  - Las capturas van a `docs/screenshots` relativo al repo, o a `SCREENSHOT_DIR`.
  - La copia extra solo se hace si existe `ARTIFACTS_DIR`.
  - Las carpetas se crean al capturar.
- **Capturas:** se regeneraron las 30 de `docs/screenshots`, porque Sol cambia por completo y Noche cambia en el menú móvil.

No cambia ningún texto público sobre el modelo. Siguen sin aparecer ahorro, rendimiento ni rotación ganadora.

### Propuestas que piden una decisión humana

1. ~~**Colores de rotación en las gráficas.**~~ Resuelta en la Fase 2: un tono por tema (`--rot-*`), ver abajo.
2. ~~**Esquinas y sombra.**~~ Resuelta en la Fase 2: manda `ui-decisions.md` (radios de 2 a 6 px, borde de 1 px, sin sombra).
3. **Acento.** La decisión dice cian de lectura; la implementación usa verde `#3dcc7a` en Noche y azul petróleo `#0b4f6c` en Sol. Hay que decidir si se actualiza la decisión o el token `--accent`.
4. **Fondo de Sol.** La decisión habla de crema; el token es gris frío `#f3f6f8`. Hay que decidir uno de los dos.
5. **Rondas.** Hacen falta tres rondas de ojos frescos sobre las capturas nuevas de Sol antes de dar el tema por cerrado.

## Fase 2: tokens y sistema visual

### Cambios

- `frontend/src/index.css` pasa a ser solo una lista de imports. La hoja se partió en `frontend/src/styles/` en este orden de cascada: `tokens.css`, `base.css`, `shell.css`, `map.css`, `content.css`, `responsive.css`.
- **Colores de rotación por tema** (`--rot-melon`, `--rot-legume`, `--rot-sorghum`):
  - Noche: `#6cb4ff`, `#3fd0b8`, `#e8a33d`.
  - Sol: `#0b4f8a`, `#0f766e`, `#9a5806`.
  - Cierra el pendiente de la Fase 1: el `#143d66` no leía sobre Noche. El trazo (continuo, `7 4`, `1.5 4`) se mantiene como segunda señal.
  - Mecanismo: `data-rot="rice_*"` fija `--rot`; `.rot-bg` y `.rot-dot` lo consumen. `ROTATION_STYLE` devuelve `var(--rot-*)`, así que los gráficos cambian con el tema.
- **Identidad rectangular:** radios de 2, 4 y 6 px (`--r-1/2/3`). Paneles opacos con borde de 1 px, sin sombra ni desenfoque (se quitaron `--panel-blur` y `--panel-shadow`).
- **Escala de letra** `--fs-*` con mínimo de 12 px, y tokens de movimiento `--dur-fast`, `--dur-base`, `--ease`. Los botones tienen transición y estado `:active`; `prefers-reduced-motion` los corta.
- `--outline` por tema para el borde de marcas y puntos, de modo que se vean sobre cualquier fondo.
- Los estilos en línea con `color-mix` y hex sueltos de `MapScreen`, `SeasonScreen`, `CantonsScreen` y `Charts` pasaron a clases (`rot-bg`, `rot-dot`, `plate-alt`, `plate-outline`, `mark-window`, `mark-ink`).

### Verificación

- `tsc` y `vite build`: sin errores. `vitest`: 11/11. Playwright: 32/32.
- `oxlint`: 3 avisos que ya existían (`themeName` sin usar en el e2e y dos lecturas de ref durante el render en `NandaMap.tsx`).
- Las capturas de esta fase fueron a una carpeta temporal; `docs/screenshots` no se regeneró.

### Lo que no se tocó a propósito

- Los literales de MapLibre, `color.ts`, `surface.ts` y el `circle-stroke-color` de `NandaMap.tsx` siguen en hex: el mapa es oscuro en los dos temas y MapLibre no lee variables CSS.
- Quedan estilos en línea dinámicos (anchos, posiciones en porcentaje, muestras de `surfaceColor`), porque dependen de los datos.
- No cambia ningún texto público sobre el modelo.

## Fase 3: estructura y puntos de quiebre

### Problema que se midió
- La barra superior de escritorio necesitaba 1431 px. Entre 801 y 1439 px el aviso PRUEBA y los botones de tema e idioma se salían de la pantalla y el documento tenía scroll horizontal. En móvil la barra medía 175–227 px.

### Cambios
- `.app` y `.workspace` pasan a CSS grid. La barra lateral ya no se superpone al mapa: en móvil es una fila propia abajo y el escenario ocupa el resto.
- Cuatro anchos, definidos en `styles/responsive.css` y `lib/viewport.ts`: ≤767 móvil, 768–1099 tablet, ≥1100 ancho, ≥1440 amplio. `NandaMap.tsx` y `MapScreen.tsx` usan `isMobile()` en vez de `innerWidth < 800`.
- Debajo de 1440 el aviso de modo se oculta y los botones de tema e idioma quedan solo con ícono (la etiqueta sigue en el nombre accesible). En tablet los controles pasan a una segunda fila; en móvil la barra baja a unos 123 px.
- Barra lateral: 208 px con nombres, 92 px con el nombre bajo el ícono en tablet, barra inferior de 64 px en móvil.
- La hoja inferior del mapa tiene tres alturas (corta, media, alta). El asa es un `slider` con `aria-valuetext`; un toque, Enter o Espacio pasan a la siguiente, las flechas suben y bajan, y arrastrar ajusta a la más cercana al soltar. Hay alternativa al arrastre (WCAG 2.5.7).
- El buscador de cantón salió del flujo de la barra y vive dentro del escenario.

### Verificación
- `tsc`, `vite build`, `vitest` (11/11) y Playwright (32/32) sin errores. `oxlint`: los mismos 3 avisos de antes.
- Medido con Playwright a 360, 480, 768, 801, 900, 1024, 1100, 1280 y 1440 px: sin scroll horizontal ni elementos de la barra fuera de pantalla.
- Hoja a 360 px: 168 → 299 → 429 px por toque; End lleva a la alta.

### Pendiente
- A 768 px el reproductor de la parte baja queda apretado (el control deslizante es corto y «Comparar años» se parte en dos líneas). Se resuelve con el rediseño del mapa de la Fase 4.
- Sin revisar con lector de pantalla real ni con pantallas táctiles físicas; los gestos se probaron con toques de Playwright.
- `docs/screenshots` no se regeneró.

## Fase 8 · verificación del 14 de noviembre de 2026

- Lighthouse 13.6.0 dio 100/100 en accesibilidad móvil para Mapa, Cantones, Rotaciones, Temporada y Confianza, en los dos temas y con datos de prueba.
- axe 4.14.0 terminó con cero violaciones en 46 ejecuciones. Se revisaron las 30 combinaciones de ruta, ancho y tema, más 16 estados interactivos. Se corrigieron los nombres accesibles del selector de idioma y de las filas de los gráficos, que ahora incluyen el texto visible.
- «Saltar al contenido» lleva el foco al área principal y conserva la ruta del hash. La comprobación funcionó mediante teclado en Noche y Sol.
- Playwright pasó 38/38. Se renovaron las 30 capturas de la matriz y la captura de recuperación por error en Rotaciones. Vitest pasó 11/11 y oxlint terminó limpio.
- Antes de las rondas independientes, la captura de 360 px mostraba un deslizador estrecho para elegir un día.

### Tres rondas de revisión independiente

Cada ronda recibió una lectura de diseño y una comprobación técnica de revisores distintos. En la segunda ronda se reemplazó al primer revisor técnico tras un límite de uso. El detector de Impeccable no pudo cargar su motor local. Los revisores usaron capturas, inspección de fuente y, donde fue posible, reproducción en Chromium o los resultados de axe.

1. **Primera ronda.** La rampa sobre cantones sugería un resultado del modelo por área. El calendario podía confundirse con balance diario, la búsqueda quedaba oculta en la ficha y el comparador móvil podía subir detrás de la cabecera. Se usaron límites neutros por defecto; la malla y su leyenda se activan juntas como prueba. El calendario provisional muestra la fecha exacta, el deslizador usa el ancho disponible en móvil, el comparador abre en diálogo y enlaza a Temporada, y la búsqueda responde junto al campo. Los estados observados quedaron entre 6 y 8 de 10.
2. **Segunda ronda.** A 768 px la columna fija de capas reducía el espacio cartográfico. Se sustituyó por un botón y se ajustó el encuadre. A 360 px la cifra muestra su origen sintético. Rotaciones indica cuándo coinciden los extremos del rango y Confianza explica en palabras el estado de revisión. También se corrigieron el destino al punto exacto del modelo, la selección con Altura activa, la espera de límites para interpretar el GPS y el estado cuando la API devuelve una comparación ausente. Los ejes visuales observados quedaron entre 7 y 8 de 10.
3. **Tercera ronda.** Se trasladó el aviso de cantón fuera de Guanacaste al buscador para que se mantenga visible con la ficha cerrada. Quedaron como hallazgos visuales la falta de contexto de muestra junto al título de Rotaciones, las marcas del calendario sin rótulos de meses a 360 px y la presencia de códigos técnicos en el recorrido general. Los ejes visuales observados quedaron entre 7 y 8 de 10. El umbral de tres rondas consecutivas con 9/10 o más sigue pendiente.

Tras los ajustes visuales se regeneraron las 31 capturas, Playwright pasó 39/39, Lighthouse volvió a dar 100/100 en las diez combinaciones de ruta y tema y axe volvió a marcar cero violaciones en 46 ejecuciones. Las correcciones de interacción posteriores se comprobaron con los casos de Mapa en Playwright.
