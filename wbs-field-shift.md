# WBS con horario · Finca Resiliente (AlairaX) · Field Shift · NASA Space Apps 2026 CR

Versión 2, sáb 14 nov 2026, ~13:00 (hora CR). **Cierre oficial: dom 15 nov, 11:59 p. m.** · **Meta interna de envío: dom 20:00** (4 h de colchón).

Esta versión reemplaza a la primera. Se alinea con tus dos documentos del repo: `fieldshift-contexto.md` y `Finca_Resiliente_AlairaX_Contexto_Completo_WBS.md`. **Conserva su numeración 1.0–7.0** (para que los issues 001–012 de su sección 13.5 sigan valiendo) y les añade lo que a ellos les falta: responsable por nombre, horas, hora límite y orden de recortes. Fuentes de apoyo: `recopilacion-field-shift.md`, `propuesta-skeleton-web.md`, `outputs/informe_apis.md`, `fieldshift-pitch-borrador.pdf`.

## 0. Qué cambió frente a mi primera versión

| Tema | Antes (mi versión 1) | Ahora (según tus documentos) | Por qué |
|---|---|---|---|
| Roles | Abe = datos y modelo, Justin = integración y entrega | **Abe = I1** (todo el AI/ML, API, integración). **Justin = I2** (kernel FAO-56). **Ant = I3** (parámetros, fuentes, QA). **Angelina = I4** (UX/UI, frontend, pitch) | Decisión explícita tuya: nadie duplica el ML y el kernel es de Justin |
| Rotaciones | 4 (A–D, con silvopastoril) | **3**: `rice_melon`, `rice_legume`, `rice_sorghum` | Las tres comparten el arroz como base, así que son comparables. El silvopastoril pasa a P2 |
| IMERG y SMAP | En la ruta crítica (bloqueados por el EULA) | **P2**. El MVP usa POWER + ONI/RONI + SoilGrids | Tu doc los marca como "para después". El demo no puede depender de un EULA |
| Histórico | POWER 2001–2025 (por IMERG) | **POWER 1981–2025** (~45 temporadas) | Sin IMERG no hay razón para recortar a 2001, y el KNN gana análogos |
| Punto de la finca | Casco urbano de Liberia (10.6346, −85.4407) | **Punto agrícola fuera del casco** (prueba: 10.55, −85.50) | Tu doc encontró que en el casco urbano HLS da rojo negativo y SoilGrids devuelve `null` |
| Despliegue | Solo JSON estático | **Contrato FastAPI + demo público estático con JSON precalculado** (FastAPI queda P1) | GitHub Pages no corre FastAPI. Ver D2 |
| Métricas P0 | Incluía días de suelo desnudo y meses sin forraje | **Demanda hídrica, déficit modelado, días de estrés** | Tu doc: la cobertura solo se muestra si hay método verificable |
| Nombre | Por decidir | **Finca Resiliente (AlairaX)**; el reto es *Field Shift* | Tu doc ya lo usa. Falta confirmarlo (D3) |
| Prioridades | P1/P2/P3 | **P0 / P1 / P2** | Mismo vocabulario que tu doc |

## 1. Alcance congelado

**Entregable final:** un simulador web público, sin login, que compara **3 rotaciones** en Guanacaste bajo el **mismo clima histórico**. Busca años análogos con KNN (ENOS), corre un balance hídrico FAO-56 y muestra demanda hídrica, déficit modelado y días de estrés, con incertidumbre p10–p90, fuentes y límites visibles. Más un deck de **≤ 7 diapositivas en inglés, portada incluida**, la página del proyecto en inglés y el clic en **"Submit for Judging"**.

**Mensaje honesto del producto** (de tu doc, sección 15.3): es una *comparación modelada y explicable*. No predice cosechas, no demuestra ahorro de agua y no reemplaza al agrónomo.

**Fuera de alcance (P2):** LLM explicativo, XGBoost, chatbot, WhatsApp, precios y rentabilidad, GIS avanzado, SMAP/IMERG/ECOSTRESS en vivo, microservicios.

## 2. Equipo y roles

| Rol | Persona | Perfil | Dueño de | Carpeta |
|---|---|---|---|---|
| **I1** AI/ML, API e integración | **Abe** | CS + IA/ML, desarrolla con Codex/Cursor | Dataset climático, features, KNN, comparador, robustez, contrato, export de JSON, integración | `backend/app/intelligence/`, `api/` |
| **I2** Kernel científico | **Justin** | Electrónica + software con Claude | ET0, balance hídrico, simulación de rotaciones, tests numéricos, despliegue | `backend/app/simulation/` |
| **I3** Investigación y QA | **Ant** | Electrónica, investigación amplia | Parámetros Kc, fuentes, supuestos, fichas de evidencia, QA, texto del formulario | `research/` |
| **I4** Producto y pitch | **Angelina** | Ing. industrial: UX/UI, marketing, frontend | Flujos, interfaz, gráficos, deck, storytelling | `frontend/` |

Reglas de convivencia (de tu doc): Justin **no** hace otro KNN ni ranking; Abe **no** toca ecuaciones del kernel; Ant **no** es cuello de botella de backend; Justin audita ecuaciones y unidades aunque Claude escriba el código.

## 3. Árbol del WBS

```
Finca Resiliente · Space Apps 2026
├─ 1.0 Planificación y arquitectura   [Abe + todos]
├─ 2.0 Investigación y evidencia      [Ant]
├─ 3.0 Kernel de simulación           [Justin]
├─ 4.0 Motor AI/ML                    [Abe]
├─ 5.0 Producto y experiencia         [Angelina]
├─ 6.0 Integración y despliegue       [Abe + Justin]
└─ 7.0 Validación y entrega           [todos]
```

## 4. Paquetes de trabajo

**P0** = obligatorio para la demo. **P1** = solo si P0 va al día. **P2** = no se compromete. Las horas son esfuerzo efectivo contando con asistencia de IA. Todas las horas son de Costa Rica. Una "Dep." con ID es una dependencia dura.

### 1.0 · Planificación y arquitectura

| ID | Tarea | Resp. | Apoyo | h | Límite | Dep. | Salida | P |
|---|---|---|---|---|---|---|---|---|
| 1.1 | Idea final confirmada con el Team Owner (Abraham); mapear nombres ↔ I1–I4; elegir un punto agrícola válido fuera del casco urbano (probar que SoilGrids no devuelve `null`) y fijar el usuario: técnico de cooperativa | Ant | Abe | 1 | Sáb 13:00 | | Decisión escrita | P0 |
| 1.2 | Cerrar las 3 rotaciones con calendario, objetivo y qué se compara; alinear demo, deck e investigación (ver D1) | Ant | Justin, Abe | 1 | Sáb 13:00 | | `rotaciones` v0 | P0 |
| 1.3 | **Contrato congelado (M1):** modelos Pydantic y JSON de `simulate_rotation()` y de `/compare`; fixture de una temporada; JSON mock con `_mock`, `generado`, `zona` (Issue 001) | Abe | Justin, Angelina | 2 | Sáb 14:30 | 1.2 | Schemas + mocks | P0 |
| 1.4 | Repo público con la estructura de la sección 11.4 de tu doc, `.gitignore` (`.env`, `outputs/raw/`), README esqueleto, tablero con los issues 001–012 | Justin | Abe | 1.5 | Sáb 14:00 | | Repo + tablero | P0 |
| 1.5 | Elegibilidad y reglas: los 4 en el mismo evento y en Members (lo hace el Team Owner); confirmar con el canal del evento el tema de IA para idear, trabajo previo y formato | Ant | Abe | 1.5 | Sáb 14:00 | | Nota + captura de Members | P0 |

### 2.0 · Investigación y evidencia científica (Ant)

| ID | Tarea | Resp. | Apoyo | h | Límite | Dep. | Salida | P |
|---|---|---|---|---|---|---|---|---|
| 2.1 | Matriz de fuentes (fuente → dato → fecha → unidad → fiabilidad → URL) y `procedencia.json` | Ant | | 1 | Dom 11:00 | 4.1 | `source_matrix.md`, `procedencia.json` | P0 |
| 2.2 | Parámetros por cultivo: Kc por fase, duración, siembra/cosecha, raíz, agotamiento; arroz inundado (lámina y percolación) aparte; `null` si falta, nunca inventar. **v1 arroz + melón a las 15:30** (Issue 002) | Ant | Justin | 3.5 | Sáb 18:00 | 1.2 | `crop_parameters` | P0 |
| 2.3 | Matriz de supuestos e incertidumbre: POWER 0,5° vs HLS 30 m vs SoilGrids 250 m, vacíos y avisos | Ant | | 1 | Dom 11:00 | 2.1 | `provenance.md` | P0 |
| 2.4 | Revisión de coherencia: unidades, rangos FAO por ciclo (arroz 450–700 mm, melón 400–600, sorgo 450–650), 3 casos hechos a mano | Ant | Justin | 2 | Dom 12:30 | 3.5 | `qa_cases.md` | P0 |
| 2.5 | Fichas de evidencia por rotación: por qué, evidencia, beneficios, vacíos, riesgos; incluir la lluvia media IMN de Liberia (1.652,7 mm/año) | Ant | | 2 | Sáb 22:00 | 1.2 | Texto de `rotaciones.json` | P0 |
| 2.6 | Verificar en la fuente original las cifras del gancho: −43 % de lluvia, +3,5 °C de Niño 3, 10 cantones en alerta roja, ONI 2026 | Justin | Ant | 1.5 | Dom 11:00 | | Tabla cifra → fuente → verificada | P0 |

### 3.0 · Kernel de simulación (Justin)

| ID | Tarea | Resp. | Apoyo | h | Límite | Dep. | Salida | P |
|---|---|---|---|---|---|---|---|---|
| 3.1 | Entradas del kernel: validar clima diario, perfil de suelo (agua útil con capacidad de campo y marchitez de SoilGrids), cultivos y calendarios; esqueleto `simulation/` | Justin | | 2 | Sáb 17:00 | 1.3, 2.2 (v1) | Esqueleto + tests | P0 |
| 3.2 | ET0 FAO-56 Penman-Monteith diaria desde T2M_MAX/MIN, RH2M, WS2M y ALLSKY_SFC_SW_DWN; contrastar con el rango IMN (EVPTRNS **no** es ET0) | Justin | Abe | 2 | Sáb 18:30 | 4.1 | `et0_diaria` | P0 |
| 3.3 | Balance hídrico diario FAO-56: ETc = Kc·ET0, lluvia efectiva, almacenamiento acotado, estrés, arroz inundado con lámina y percolación. **Primera rotación a las 22:00** (Issue 003) | Justin | Ant | 4 | Sáb 22:00 | 3.1, 3.2, 2.2 | `water_balance.py` | P0 |
| 3.4 | Las 3 rotaciones con la misma llamada; salidas: demanda hídrica, déficit modelado, días de estrés, avisos y supuestos (Issue 007) | Justin | | 3 | Dom 09:00 | 3.3 | Resultados comparables | P0 |
| 3.5 | Pruebas unitarias: balance de masa, rangos, días faltantes, etapas | Justin | | 2 | Dom 11:00 | 3.4 | `pytest` en verde | P0 |
| 3.6 | Estrés térmico y fenología por etapa, con umbrales que tengan fuente | Justin | Ant | 2 | Dom 13:00 | 3.4 | Indicador de calor | P1 |
| 3.7 | Comparar el kernel con la tabla FAO/CROPWAT y probar sensibilidad a Kc, humedad inicial y suelo | Justin | Abe | 1.5 | Dom 13:00 | 3.5 | Nota de validación | P1 |

### 4.0 · Motor AI/ML (Abe)

| ID | Tarea | Resp. | Apoyo | h | Límite | Dep. | Salida | P |
|---|---|---|---|---|---|---|---|---|
| 4.1 | Dataset climático: POWER diario **1981–2025 + 2026 a la fecha** en el punto de la finca; control de calidad (tope de lluvia diaria, p. ej. p99,9, huecos, unidades); ONI/RONI y `fase_temporada` (AMJ-OND); caché y metadatos. Calibrar la lluvia contra el valor IMN (POWER sobreestima +28 %) (Issue 004) | Abe | | 3.5 | Sáb 16:30 | 1.1 | `datasets/processed/` | P0 |
| 4.2 | Features por temporada con escalado sin fuga temporal: lluvia estacional, ET0 acumulada, Tmax, días de calor, ONI | Abe | | 2 | Sáb 20:00 | 4.1, 3.2 | `features.py` | P0 |
| 4.3 | KNN de años análogos (k = 5) para 4 escenarios: Niño fuerte, Neutro, Niña y "Como 2026". 2026 es año de seguimiento, **no análogo**. Distancias y sensibilidad a k (Issue 005) | Abe | | 2.5 | Sáb 22:00 | 4.2 | `analogos.json` | P0 |
| 4.4 | Comparador contrafactual: deltas entre la rotación actual y las alternativas, año por año. Arranca con un **kernel mock** y cambia al real al terminar 3.4 (Issue 008) | Abe | Justin | 2 | Sáb 23:30 (mock), Dom 09:00 (real) | 4.3, 1.3 | `counterfactual.py` | P0 |
| 4.5 | Robustez e incertidumbre: p10/p50/p90 entre análogos, comparación pareada por año, lista de "lo que no se puede concluir" | Abe | | 2 | Dom 11:00 | 4.4, 3.4 | `robustness.py`, `resultados.json` | P0 |
| 4.6 | Backtest dejando un año fuera (El Niño 2015 y 2023): déficit simulado vs lluvia observada | Justin | Abe | 2 | Dom 12:30 | 4.5 | Figura + tabla de error | P1 |
| 4.7 | Reglas de ranking con pesos visibles y caso "no se puede recomendar" (decisión D5) | Abe | Angelina | 1 | Dom 10:00 | 4.5 | Regla de ranking | P1 |
| 4.8 | Lluvia de contraste con CHIRPS v3 (sin login) para documentar el sesgo de POWER | Justin | | 1.5 | Dom 10:00 | 4.1 | Nota + gráfica | P1 |
| 4.9 | IMERG y SMAP solo para validación (exige aceptar el EULA de GES DISC con la cuenta del token) | Justin | | 3 | Solo si sobra tiempo | | Series de validación | P2 |
| 4.10 | HLS NDVI y suelo desnudo (escenas de ~200 MB; Fmask; fuera del casco) | Abe | | 3 | No se compromete | | Capa NDVI | P2 |
| 4.11 | LLM explicativo | — | | — | Fuera del MVP | | Texto por plantilla | P2 |

### 5.0 · Producto y experiencia (Angelina)

Stack propuesto: Vite + React, HashRouter, Recharts, Leaflet + OSM (ver `propuesta-skeleton-web.md`). Angelina decide si usa JavaScript o TypeScript (D8).

| ID | Tarea | Resp. | Apoyo | h | Límite | Dep. | Salida | P |
|---|---|---|---|---|---|---|---|---|
| 5.1 | Flujos, wireframes y sistema visual a partir del boceto de la pizarra | Angelina | | 2 | Sáb 15:00 | | Kit de UI | P0 |
| 5.2 | Frontend mock-first: scaffold, lectura de los JSON mock, Layout, MockBanner, ScenarioSelector, AnalogYearsTable (Issue 006) | Angelina | Abe | 4 | Sáb 21:00 | 1.3, 1.4, 5.1 | UI navegable con mocks | P0 |
| 5.3 | Resultados: 3 tarjetas por rotación (indicadores, fuente, avisos, vacíos, riesgos), gráfica de déficit con banda p10–p90, aviso fijo "Estimaciones de modelo. Requieren validación local.", panel "¿Por qué confiar?" | Angelina | | 4 | Dom 10:00 | 5.2 | UI de resultados | P0 |
| 5.4 | Conectar a los JSON reales y quitar el MockBanner | Angelina | Abe | 1 | Dom 12:00 | 6.1 | Web con datos reales | P0 |
| 5.5 | Páginas Inicio, Método, Procedencia y Equipo (con la declaración de IA) | Angelina | Ant | 3 | Dom 12:00 | 5.2, 2.1 | Páginas | P0 |
| 5.6 | Sliders de prioridades que reordenan las tarjetas | Angelina | Abe | 1.5 | Dom 12:30 | 4.7 | Sliders | P1 |
| 5.7 | Español/inglés (lo esencial debe existir en inglés para los jueces) | Angelina | Ant | 1.5 | Dom 13:00 | 5.5 | `es`, `en` | P1 |
| 5.8 | Responsive móvil y accesibilidad básica | Angelina | | 1.5 | Dom 13:30 | 5.3 | Usable en celular | P1 |
| 5.9 | Mapa Leaflet con la zona marcada (un píxel de POWER cubre toda la zona; solo sirve para ubicar) | Angelina | | 0.75 | Dom 13:30 | 5.2 | Mapa | P1 |

### 6.0 · Integración y despliegue

| ID | Tarea | Resp. | Apoyo | h | Límite | Dep. | Salida | P |
|---|---|---|---|---|---|---|---|---|
| 6.1 | Pipeline de export: genera `public/data/*.json` (escenario × rotación) desde dataset + KNN + kernel + comparador. Primer export parcial Sáb 23:30 | Abe | Justin | 2 | Dom 09:00 | 4.4, 3.4 | JSON reales | P0 |
| 6.2 | **Vertical slice (M3):** una rotación de punta a punta (datos → KNN → kernel → comparador → UI); después las 3 (Issue 009) | Abe | Justin, Angelina | 2 | Sáb 23:30 (1 rotación), Dom 10:00 (3) | 6.1, 5.2 | Slice funcionando | P0 |
| 6.3 | Despliegue en GitHub Pages sin login, con datasets precargados y prueba en ventana privada. Primer deploy Sáb 22:00 (Issue 011) | Justin | Abe | 1 | Dom 14:00 | 1.4, 5.2 | URL pública | P0 |
| 6.4 | FastAPI: `/health`, `/rotations`, `/scenarios`, `/sources`, `POST /compare` sobre los mismos casos de uso. Corre en local; el demo público no lo necesita | Justin | Abe | 2 | Dom 14:00 | 6.1 | `backend/app/api` | P1 |

### 7.0 · Validación y entrega

| ID | Tarea | Resp. | Apoyo | h | Límite | Dep. | Salida | P |
|---|---|---|---|---|---|---|---|---|
| 7.1 | QA de punta a punta: 3 rotaciones × 4 escenarios, errores y datos faltantes, sin datos ficticios ocultos (Issue 010) | Justin | Ant | 2 | Dom 13:30 | 6.2 | Informe QA | P0 |
| 7.2 | README y método científico: cómo correr, fuentes, límites, IA declarada | Ant | Abe | 1.5 | Dom 14:00 | 6.1 | `README`, `scientific_method.md` | P0 |
| 7.3 | Deck de 7 diapositivas en inglés (estructura de tu doc 15.2): diseño, capturas con datos reales, sin logos NASA, imágenes generadas con marca de agua. v1 con mocks a las 14:00, final a las 17:00 (Issue 012) | Angelina | Ant | 5 | Dom 17:00 | 5.4 | Deck EN | P0 |
| 7.4 | Guion del deck en inglés | Ant | Angelina | 1.5 | Sáb 22:00 | 2.6 | Guion | P0 |
| 7.5 | Página del proyecto en inglés: nombre, resumen, descripción, datos NASA usados y cómo, referencias y **declaración de IA** por persona (Claude, Codex/Cursor, etc.) | Ant | Abe, Justin | 3 | Dom 14:30 | 7.2 | Texto final | P0 |
| 7.6 | Alojar el deck en un enlace público sin login; subir imágenes ≤ 10 MB | Angelina | | 0.5 | Dom 17:30 | 7.3 | Links | P0 |
| 7.7 | Probar **todos los links en ventana privada** y en celular; checklist de cumplimiento (sin logos NASA, ≤ 7 diapositivas, inglés, aviso de validación visible) | Ant | Angelina | 1.5 | Dom 18:30 | 7.6 | Checklist firmado | P0 |
| 7.8 | **Feature freeze** y smoke test del build de producción | Justin | | 0.5 | Dom 14:00 | 5.4 | Build congelado | P0 |
| 7.9 | **Clic en "Submit for Judging"** por el Team Owner; confirmar estado "Submitted" con los 4 miembros; captura | Abe | Justin | 0.5 | **Dom 20:00** | 7.7, 7.8 | Envío confirmado | P0 |

### Ceremonias (todos, 2 h cada uno)

Kickoff Sáb 12:30 (0,5 h) · cuatro checkpoints de 15 min (1 h) · ensayo del pitch Dom 18:00 (0,5 h).

## 5. Carga por persona

Sumado con script sobre las 50 tareas de la sección 4 (solo cuenta las horas del **responsable**; el apoyo no suma). Cada persona incluye 2 h de ceremonias.

| Persona | Rol | P0 | + ceremonias | P1 | Total P0+P1 | Tareas donde apoya |
|---|---|---|---|---|---|---|
| Abe | I1 | 18,5 h | **20,5 h** | 1,0 h | 21,5 h | 14 |
| Justin | I2 | 19,5 h | **21,5 h** | 9,0 h | 30,5 h | 9 |
| Ant | I3 | 20,5 h | **22,5 h** | 0 h | 22,5 h | 7 |
| Angelina | I4 | 19,5 h | **21,5 h** | 5,25 h | 26,75 h | 5 |
| **Equipo** | | 78,0 h | 86,0 h | 15,25 h | 101,25 h | |

(P2 aparte: Abe 3 h y Justin 3 h, no comprometidas.)

Lectura honesta de la carga:

- **El P0 está parejo** (20,5–22,5 h por persona). Entre el sábado 13:00 y el domingo 20:00 hay 31 h de reloj; quitando sueño y comidas quedan unas 20–22 h útiles por persona. **El P0 cabe, pero casi sin holgura**, y el tiempo de apoyo (Abe apoya en 14 tareas) no está contado. Por eso el orden de recortes de la sección 8 importa.
- **Justin tiene el P1 más cargado** (9 h: FastAPI, backtest, CHIRPS, estrés térmico, comparación FAO). Si el kernel se atrasa, el P1 de Justin se cae completo y no se reasigna.
- **Abe queda bajo en horas pero alto en dependencias**: casi todo pasa por él (contrato, dataset, KNN, export, envío). Su riesgo es de **bloqueo de otros**, no de horas. Por eso 4.1 y 1.3 son lo primero del sábado.
- **Ant concentra el P0 sin P1**: es la que ya tiene más horas en P0, así que no hay margen para pasarle tareas de Justin salvo 2.6 y 7.1 (verificación y QA, que encajan con su perfil). Es también la que no puede fallar en 2.2 (parámetros), que bloquea el balance.

## 6. Hitos y ruta crítica

Usa los hitos M1–M5 de tu doc, con hora.

| Hito | Cuándo | Criterio de salida |
|---|---|---|
| M0 Kickoff | Sáb 12:30 | Decisiones D1–D8 tomadas; roles confirmados |
| **M1 Contrato cerrado** | Sáb 14:30 | Schemas, fixtures, 3 rotaciones, repo y mocks (1.2, 1.3, 1.4) |
| **M2 Componentes aislados** | Sáb 21:00 | KNN ejecutable con kernel mock, kernel con la primera rotación, UI navegable con mocks, parámetros v1 |
| **M3 Vertical slice** | Sáb 23:30 | Una rotación recorre todo el camino y vuelve a la UI; primer deploy público |
| **M4 MVP integrado** | Dom 12:00 | 3 rotaciones, análogos, indicadores, avisos y datos reales; sin MockBanner |
| Feature freeze | Dom 14:00 | Nada nuevo; solo correcciones |
| M5a Todo escrito | Dom 17:30 | Deck final EN, página del proyecto, links públicos |
| **M5 Release** | **Dom 20:00** | "Submitted" confirmado. Hasta 23:59 solo contingencia |

**Ruta crítica:** 1.3 contrato → 4.1 dataset → 3.2 ET0 → 4.2 features → 4.3 KNN → 4.4 comparador → 3.3/3.4 kernel → 6.1 export → 6.2 slice → 5.4 datos reales → 7.3 deck → 7.7 pruebas → 7.9 envío.
**En paralelo, también crítica:** 2.2 parámetros → 3.1/3.3 balance (sin Kc no hay déficit).
**M3 es el hito que más importa:** evita descubrir tarde que los módulos no encajan.

## 7. Decisiones para el kickoff

| # | Decisión | Propuesta |
|---|---|---|
| D1 | Qué 3 rotaciones | `rice_melon` (actual), `rice_legume`, `rice_sorghum`. El demo viejo usa maíz + mucuna → frijol y el pitch usa otras letras: hay que alinear demo, deck y página (Ant) |
| D2 | Cómo se publica el modelo | El **contrato** es el de FastAPI (Pydantic). El demo público lee **JSON precalculado** por escenario × rotación. FastAPI queda P1 como envoltura de los mismos casos de uso. Razón: GitHub Pages no corre Python, y tu propio doc pide no depender de APIs en el demo |
| D3 | Nombre | **Finca Resiliente (AlairaX)**, con *Field Shift* como nombre del reto. Tagline candidato: *"We can't predict the next drought. But we can replay past ones, and test every crop rotation against them."* |
| D4 | Formato del demo | Deck ≤ 7 diapositivas en inglés. El video de 30 s no se hace |
| D5 | Ranking | En P0 solo se **compara**, sin "ganadora". El ranking con pesos visibles es P1 y debe incluir el caso "no se puede recomendar" |
| D6 | IMERG, SMAP y HLS | P2. Sin ellos se declara la resolución de POWER y su sesgo, y se contrasta con CHIRPS y el valor IMN. No se muestra "suelo desnudo" sin método verificable |
| D7 | Año de seguimiento 2026 | Solo como escenario "Como 2026", nunca como análogo |
| D8 | Lenguaje del frontend | Angelina decide JavaScript o TypeScript; el contrato de datos no cambia |

## 8. Riesgos y plan B

| Riesgo | Prob. | Impacto | Mitigación / plan B |
|---|---|---|---|
| Carga de Abe: ML + API + integración (lo advierte tu doc) | Alta | Alto | FastAPI pasa a Justin y a P1; el export de JSON reemplaza a la API en el demo; Angelina conecta los datos reales (5.4) |
| Kernel científicamente incorrecto | Media | Muy alto | Pruebas de balance de masa (3.5), comparación con la tabla FAO (3.7) y revisión de Ant (2.4) |
| Tabla de parámetros tarde o con huecos | Media | Alto | Arroz y melón primero (v1 a las 15:30). Si falta un cultivo, `null` y aviso; nunca inventar |
| Tres rotaciones no comparables | Media | Alto | Calendarios, riego y uso del segundo ciclo documentados por Ant; el arroz inundado se trata aparte |
| POWER sobreestima la lluvia (+28 %) y trae picos (523 mm/día) | Alta | Medio | Control de calidad y calibración con IMN en 4.1; contraste con CHIRPS (4.8) |
| Píxel urbano da datos inválidos | Alta | Medio | Punto agrícola fuera del casco (1.1) |
| KNN con pocas temporadas | Media | Medio | POWER desde 1981 da ~45 años; se declara como limitación y no se usa ML más pesado |
| Frontend más lento de lo previsto | Media | Alto | Mock-first con JSON fiel al schema; los P1 de la UI son lo primero que se corta |
| Cifras del gancho sin verificar | Media | Alto | 2.6; si no se confirman, se usan solo las que aparezcan en IMN, CNE o NOAA |
| Reglas de IA ("no usar IA para idear") y trabajo previo | Baja | Muy alto | 1.5 confirma con el canal del evento; 7.5 declara todo el uso de IA con honestidad |
| Deck con más de 7 diapositivas | Media | Muy alto | El borrador tiene 8; 7.4 parte de 7 y 7.7 lo revisa |
| Enrutado roto en GitHub Pages | Baja | Alto | HashRouter y primer deploy el sábado a las 22:00 |
| Envío a último minuto | Media | Muy alto | Meta interna Dom 20:00; guardar no es enviar; lo envía el Team Owner |
| Equipo registrado como 3 y ahora son 4 | Media | Alto | 1.5: el Team Owner agrega a los 4 en Members cuanto antes |

**Orden de recortes si el tiempo aprieta** (primero se cae lo de arriba): 5.9 mapa → 5.8 móvil → 5.7 inglés/español completo (queda el inglés esencial) → 6.4 FastAPI → 4.8 CHIRPS → 3.7 comparación FAO → 5.6 sliders → 4.7 ranking → 4.6 backtest → 3.6 estrés térmico. Todo P2 queda fuera de plano. **Lo que nunca se recorta:** las 3 rotaciones, el KNN, el balance FAO-56, los avisos de límites y el envío.

## 9. Checklist de cumplimiento antes de enviar

- [ ] Los 4 inscritos en el mismo evento local y en la pestaña Members
- [ ] Demo en inglés: deck ≤ 7 diapositivas contando la portada
- [ ] Nombre del equipo, de todos los miembros y el reto elegido en el deck
- [ ] Links al demo y al proyecto (sitio y repo) públicos, probados en ventana privada y sin login
- [ ] Datos NASA usados y cómo; agencias socias y referencias
- [ ] Uso de IA declarado por persona; imágenes generadas con marca de agua visible
- [ ] Sin logos NASA ni insignias de misión; sin datos personales ni fotos de menores
- [ ] "Estimaciones de modelo. Requieren validación local." visible en la web
- [ ] ≥ 3 rotaciones, incluida la actual, con por qué, evidencia, beneficios, vacíos y riesgos
- [ ] Ninguna cifra "estimada" presentada como observada; no se promete ahorro de agua ni toneladas por hectárea
- [ ] Trabajo empezado este fin de semana
- [ ] **"Submit for Judging"** pulsado y estado "Submitted" confirmado
