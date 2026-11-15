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
