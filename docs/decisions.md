# Decisiones de implementación

## 2026-11-14 · Tres vecinos en el escenario Niño fuerte

El WBS original proponía k=5 en los cuatro escenarios. El snapshot ONI de agosto–octubre (ASO) solo contiene tres años entre 1981–2025 con anomalía ≥1,5 °C: 1997, 2015 y 2023. Los tres tienen las seis variables POWER completas, aunque todavía falta calcular y revisar ET0.

Se consultó al usuario entre usar tres análogos para ese escenario o mantenerlo indisponible. El usuario delegó elegir la mejor opción. La decisión es **k=3 para `strong_el_nino` y k=5 para los demás escenarios**. Se mantiene el umbral; no se incorporan años de otra fase. Es una excepción explícita de producto, no una reducción automática ante faltantes.

La CLI registra el k de cada escenario, el catálogo de frontend lo refleja y la comparación con menos de cinco años emite una advertencia de evidencia limitada. Si faltan años después del control de calidad, el escenario sigue `unavailable`; no se reduce de nuevo k. Los cuantiles con tres años son descripciones de esa pequeña muestra y no intervalos de confianza.

Esta decisión no convierte los mocks en resultados físicos ni elimina las dependencias de ET0, suelo, parámetros y kernel.
