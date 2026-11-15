---
name: NandaView
description: Instrumento agroclimático para decidir qué sembrar después del arroz en Guanacaste.
colors:
  field-gray: "#e9eae6"
  instrument-white: "#ffffff"
  well: "#f4f4f1"
  ink: "#151714"
  muted: "#62665f"
  line: "#e6e7e2"
  line-strong: "#d6d8d2"
  field-green: "#1f7a4d"
  field-green-soft: "#e5f2ea"
  tooltip-ink: "#1d201c"
  cond-1: "#2f9e5b"
  cond-2: "#8fc04f"
  cond-3: "#e5c03c"
  cond-4: "#ec8a35"
  cond-5: "#d4472f"
  rot-melon: "#1f7a4d"
  rot-legume: "#3f6fb0"
  rot-sorghum: "#b07a2a"
typography:
  display:
    fontFamily: "Instrument Sans Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "2.75rem"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Instrument Sans Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 600
    lineHeight: 1.2
  title:
    fontFamily: "Instrument Sans Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Instrument Sans Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Instrument Sans Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.3
rounded:
  r-1: "6px"
  r-2: "10px"
  r-3: "16px"
  r-4: "22px"
  pill: "999px"
spacing:
  s-1: "4px"
  s-2: "8px"
  s-3: "12px"
  s-4: "16px"
  s-5: "24px"
  s-6: "32px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.instrument-white}"
    rounded: "{rounded.pill}"
    height: "40px"
  button-quiet:
    backgroundColor: "{colors.instrument-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    height: "40px"
  card:
    backgroundColor: "{colors.instrument-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.r-4}"
    padding: "18px"
  stat-tile:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
    rounded: "{rounded.r-3}"
  tooltip:
    backgroundColor: "{colors.tooltip-ink}"
    textColor: "{colors.instrument-white}"
    rounded: "{rounded.r-2}"
---

# Design System: NandaView

## Overview

**Creative North Star: "El instrumento de campo"**

NandaView se lee como un instrumento de medición, no como una landing ni como un chat. El mapa satelital es el protagonista; encima flotan paneles blancos con cifras grandes, unidades pequeñas y escalas de ticks. La densidad es media: cada panel responde una pregunta concreta (cuánta agua faltó, qué rotación queda primero, cómo se movió el suelo).

La honestidad es parte del diseño: el estado "Piloto regional / validación en finca pendiente" está siempre visible, y los datos sintéticos nunca se pintan como si fueran medidos.

**Key Characteristics:**
- Lienzo gris de campo con instrumentos blancos flotantes.
- Cifras protagonistas con la unidad en tamaño menor.
- Escalas de ticks verde→rojo y un único marcador oscuro.
- Tooltips oscuros, controles en forma de píldora.

## Colors

Neutros cálidos con un solo verde de campo como acento y dos escalas semánticas separadas.

### Primary
- **Verde de campo** (field-green): estado activo, puntos de "Menor" y la identidad de melón. Nunca decora.

### Neutral
- **Gris de campo** (field-gray): fondo de la app detrás de los paneles.
- **Blanco instrumento** (instrument-white): paneles, rail y controles.
- **Pozo** (well): mosaicos de cifras dentro de un panel.
- **Tinta** (ink): texto, botón primario y el elemento seleccionado.

### Named Rules
**The Two Scales Rule.** La escala de condición (cond-1…cond-5) significa "mejor/peor" y siempre va de verde (menos) a rojo (más). Los colores de rotación (rot-*) solo identifican cultivos. Nunca se mezclan en una misma marca.

**The Honest Data Rule.** Los datos sintéticos (`_mock`) no se usan como coropleta por defecto ni se colorean con la escala de condición.

## Typography

**Body Font:** Instrument Sans Variable (con Segoe UI, system-ui)
**Label/Mono Font:** IBM Plex Mono, solo para coordenadas e identificadores.

**Character:** Una sola sans geométrica y sobria, con cifras tabulares; el peso y el tamaño crean la jerarquía.

### Hierarchy
- **Display** (600, 2.75rem): título de página, uno por pantalla.
- **Headline** (600, 1.375rem): títulos de pantallas interiores.
- **Title** (600, 0.9375rem): título de panel.
- **Body** (400, 0.9375rem, 1.5): texto de lectura, máximo ~70ch.
- **Label** (500, 0.75rem): etiquetas de cifras, ejes y leyendas.

### Named Rules
**The Number First Rule.** La cifra va grande y la unidad va en `<small>` a ~45% del tamaño. No hay kicker sobre los títulos.

## Layout

La app es una grilla de dos columnas: un rail flotante de 60px y el escenario. En el mapa, el panel de lectura flota a la izquierda con `clamp(340px, 26vw, 392px)`, y el encuadre del mapa compensa su ancho. El inicio usa una grilla de 12 columnas (resumen 7 + lateral 5; suelo 7 + mapa de calor 5). El contenido se alinea a la izquierda con la barra superior. Por debajo de 1180px las columnas se apilan; por debajo de 768px el rail pasa a barra inferior y el panel del mapa se vuelve una hoja que sube sobre el mapa.

## Elevation & Depth

La profundidad es física: los paneles se separan del fondo con sombras suaves, y los controles que van sobre el mapa usan vidrio (blanco 86% + desenfoque).

### Shadow Vocabulary
- **Reposo** (`--shadow-1`): rail y paneles sobre el fondo gris.
- **Elevado** (`--shadow-2`): menús y el control seleccionado de un segmento.
- **Sobre el mapa** (`--shadow-3`): panel de lectura, rail y controles flotantes sobre la imagen satelital.

### Named Rules
**The No Nested Cards Rule.** Dentro de un panel, las secciones se separan con espacio o con un pozo tonal, nunca con otra tarjeta con sombra.

## Shapes

Esquinas generosas en contenedores (22px), medianas en mosaicos (16px) y píldoras en todos los controles. Los ticks son líneas de 3px con extremos redondeados.

## Components

### Buttons
- **Shape:** píldora (999px), 40px de alto.
- **Primary:** fondo tinta, texto blanco, con una flecha cuando lleva a otra pantalla.
- **Quiet:** fondo blanco, borde de línea; en hover se oscurece el borde.
- **Focus:** anillo de 2px en el color de acento con un margen de 2px.

### Chips
- **Style:** píldora blanca con un punto de color a la izquierda (estado del piloto, de la muestra y del modo en vivo).

### Cards / Containers
- **Corner Style:** 22px.
- **Background:** blanco instrumento sobre gris de campo.
- **Internal Padding:** 18px.

### Inputs / Fields
- **Style:** selects en píldora con chevron SVG; en el inicio llevan la etiqueta dentro de la propia píldora.

### Navigation
- **Rail:** íconos de 20px con etiqueta corta; el activo es un cuadrado tinta con el ícono en blanco. En móvil, barra inferior con etiquetas.

### Signature: Tick Scale
Entre 32 y 56 ticks colorean la escala de condición desde el mínimo hasta el máximo observado; los que pasan el valor se atenúan y un marcador tinta con halo indica la posición.

### Signature: Soil Chart
Línea escalonada de agua en el suelo, coloreada por tramos (verde sin estrés, rojo con estrés, punteada fuera de temporada), con tooltip oscuro y navegación por teclado.

## Do's and Don'ts

### Do:
- **Do** mostrar siempre el estado del piloto ("Sin validar en finca") junto a la lectura principal.
- **Do** usar la escala de condición solo para métricas donde menos es mejor.
- **Do** respetar `prefers-reduced-motion`: el vuelo del mapa y la entrada de los paneles bajan a 0 ms.

### Don't:
- **Don't** inventar paneles tipo "AI Insights" ni cifras sin fuente en el archivo de simulación.
- **Don't** usar los colores de rotación para decir bueno o malo.
- **Don't** anidar tarjetas ni poner kickers sobre los títulos.
