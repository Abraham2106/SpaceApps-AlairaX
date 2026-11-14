# Revisión científica pendiente · 14 de noviembre de 2026

Este registro separa la implementación comprobada de la aprobación científica que todavía necesita el equipo. Las casillas abiertas no se consideran cumplidas por la existencia de schemas, mocks o tests de integración. El [método actual](scientific_method.md) describe lo que realmente hace el código.

## Evidencia disponible

| Evidencia | Estado comprobado | Alcance |
|---|---|---|
| POWER y NOAA reales con caché y procedencia | Descargados en el punto provisional | Recuperación y normalización; no validación de parcela |
| Cobertura POWER 1984–2025 | 42 años con las seis variables completas | Entradas meteorológicas; ET0 sigue pendiente |
| Pipeline de features real abril–octubre, ONI ASO | 0 años elegibles, 46 exclusiones | Falta ET0 revisada; cuatro escenarios `unavailable` |
| Contratos y comparación pareada | Ejecutables y probados con fixtures | Guardas de integración; no kernel científico |
| JSON de frontend | Cuatro ejemplos `_mock=true` | Interfaz y contrato; ninguna cifra agronómica real |

## Ant: fuentes, parámetros y decisiones

- [ ] Confirmar y registrar la ubicación agrícola; demostrar que el perfil de suelo es utilizable y documentar resolución, profundidad y fuente.
- [ ] Revisar la interpretación de SoilGrids como predicción espacial. Entregar capacidad de campo, punto de marchitez y profundidad efectiva, o el método referenciado con que se obtienen.
- [ ] Cerrar los calendarios y la identidad del cultivo de la alternativa `rice_legume`. Mantener los IDs de rotación comunes y fechas compatibles con el clima de cada año.
- [ ] Entregar parámetros por cultivo con referencia, unidad, etapa, duración y rango de incertidumbre. Registrar explícitamente vacíos y supuestos, incluidos los del arroz inundado.
- [ ] Verificar cualquier referencia IMN usada para contrastar lluvia: estación, período, cobertura y comparabilidad con el píxel. Revisar el evento extremo preservado de `2020-11-03`; no eliminarlo solo por superar 500 mm/día.
- [ ] Revisar la decisión de usar ONI como feature exploratoria mientras NOAA usa RONI para monitoreo/pronóstico oficial. Conservar cada índice y snapshot separados y registrar la versión publicada de la serie cuando se identifique.
- [ ] Verificar en fuentes originales las cifras del pitch y distinguir datos observados, derivados del proveedor, estimados y modelados.
- [ ] Completar fichas de evidencia, beneficios, riesgos, vacíos y viabilidad de las tres rotaciones. Aprobar el lenguaje público sin promesas de ahorro o rendimiento.

## Justin: ET0 y kernel FAO-56

- [ ] Implementar y revisar ET0 diaria, unidades, radiación, humedad, viento a 2 m y datos auxiliares requeridos por las ecuaciones. No sustituir ET0 con un campo de evaporación sin justificación.
- [ ] Entregar un artefacto ET0 con fechas, `mm/day`, zona idéntica, versión, fuentes y revisión identificada. Documentar si algún año requiere otra fuente o método por radiación faltante; 1981–1983 no tienen esa variable en el snapshot POWER.
- [ ] Revisar el tratamiento de 2026 y sus huecos antes de elegir una ventana de seguimiento. Una ventana completa histórica debe usar los mismos meses y días.
- [ ] Implementar balance hídrico y días de estrés con umbral documentado. Registrar cómo se tratan lluvia efectiva, inicialización de agua, raíces, riego, escorrentía/percolación y arroz inundado.
- [ ] Verificar balance de masa, almacenamiento acotado, etapas y comportamiento ante parámetros o clima faltantes mediante pruebas físicas y casos manuales independientes.
- [ ] Contrastar resultados con un procedimiento FAO/CROPWAT o referencia equivalente bajo insumos y supuestos explícitos; registrar discrepancias antes de aceptar el kernel.
- [ ] Publicar una sola versión revisada para toda la comparación y salidas diarias que cubran exactamente el período solicitado.

## Abe: regeneración e integración después de la revisión

- [ ] Regenerar features con ET0 revisada. Registrar cuántos años quedan elegibles y todas las exclusiones; no equiparar los 42 años de entradas meteorológicas con el conjunto efectivo de KNN.
- [ ] Revisar la cantidad de años de cada grupo ONI con el k configurado por escenario (Niño fuerte: 3; restantes: 5); dejar `unavailable` donde no haya suficientes, sin cambiar de fase ni reducir k silenciosamente.
- [ ] Revisar pesos, umbral de calor y contribuciones a la distancia con el equipo. El umbral climático no se presenta como daño agronómico validado.
- [ ] Examinar sensibilidad a k y luego propagar los vecinos al mismo kernel para evaluar sensibilidad de las métricas, además de estabilidad de la selección.
- [ ] Generar resultados de las tres rotaciones con iguales insumos ambientales y manejo por año; revisar hashes, versión, advertencias y procedencia.
- [ ] Probar sensibilidad agronómica a parámetros, suelo, inicialización y lluvia cuando exista un kernel revisado. No presentar la banda entre análogos como toda la incertidumbre.
- [ ] Diseñar una evaluación retrospectiva científica con años reservados y particiones temporales. Si se evalúa información conocida en tiempo real, conseguir snapshots históricos de publicación; el archivo NOAA actual no basta.
- [ ] Exportar y revisar JSON reales; sustituir fixtures únicamente después de validar toda la cadena y conservar sus avisos y límites.

## Revisión conjunta antes de la demo

- [ ] Ant y Justin aprueban parámetros, calendario, manejo y ecuaciones por escrito, con versiones de artefactos.
- [ ] Angelina conecta los JSON reales y mantiene el aviso de estimaciones; el banner mock se retira solo cuando corresponda a los datos de esa pantalla.
- [ ] Verificar tres rotaciones por cuatro escenarios disponibles o un estado de indisponibilidad comprensible; ningún dato ficticio se oculta como real.
- [ ] Revisar tarjetas, gráficos, deck y página del proyecto para que déficit modelado no se transforme en ahorro demostrado ni las distancias KNN en probabilidades.
- [ ] Completar fuentes y declaración de IA por persona. En la implementación de Abe constan Codex y sus subagentes; no se presume el uso de otros integrantes.
- [ ] Registrar explícitamente que no hubo validación de campo, salvo que el equipo efectivamente la realice y aporte su evidencia.

## Referencias primarias para la revisión

- [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/): acceso diario, formatos y estándares temporales.
- [NOAA CPC ONI actual](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/) y [RONI](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/): definición, interpretación oficial y revisiones de índices.
- [FAO-56, Allen et al. (1998)](https://www.fao.org/4/x0490e/x0490e00.htm): referencia de ET0, coeficientes y estrés que debe contrastarse con el kernel.
- [ISRIC SoilGrids](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs.html): naturaleza de las predicciones de propiedades del suelo y referencias técnicas.
