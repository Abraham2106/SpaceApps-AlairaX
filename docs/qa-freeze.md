# QA y estado del freeze · 14 de noviembre de 2026

La API local expone los cinco endpoints del plan. `POST /compare` ejecuta
el kernel FAO-56 sobre los lotes preparados por el pipeline.

| Verificación | Resultado |
| --- | --- |
| Arroz–melón, arroz–leguminosa y arroz–sorgo × Niño fuerte, neutral, Niña y Como 2026 | 12/12 combinaciones HTTP con el kernel real y fixtures marcados `_mock: true`, dos temporadas por combinación |
| Errores de API | 422 para escenario inválido, 404 para zona desconocida, 409 para análogos insuficientes o lote incompatible, 503 para lote ausente o catálogo sintético en la app normal |
| Catálogo científico del repo | Los cuatro escenarios devuelven 409 con el motivo de indisponibilidad |
| Smoke del artefacto Pages | Se armó localmente el mismo placeholder estático del workflow. La portada y los seis JSON respondieron HTTP 200 en el cliente ASGI. Las comparaciones publicadas se identifican como sintéticas |

`python -m pytest backend/tests -q` dio **224 aprobadas y 3 xfail**.
Los xfail corresponden a los casos manuales pendientes ya documentados.
El smoke local cubre el contenido servido y no ejecuta JavaScript en un
navegador ni verifica un despliegue público.

El **freeze del demo científico queda pendiente**. Falta revisión de ET₀,
confirmación de zona, calendarios y suelo, preparación de lotes reales y
QA de las 12 combinaciones con esos lotes. «Como 2026» tiene un hueco de
radiación documentado en [la revisión de ET₀](et0-review.md).
El repositorio contiene el placeholder de Pages y aún no tiene el build
de la interfaz definitiva. El smoke del build definitivo queda pendiente.

## Cómo cerrar el QA científico

El `main` remoto en `57fa9bd` incorpora la revisión de Ant y corrige
los solapes de calendario. Las fechas siguen provisionales y quedan
decisiones abiertas sobre los parámetros. NASA POWER sigue devolviendo
el valor de relleno `-999` para la radiación del 7 de septiembre de 2026.

Con la ET₀ aprobada, regenerar los análogos con
`python -m scripts.build_analogs --et0`. Generar un lote por escenario en
`outputs/inputs/<scenario_id>.json` con `scripts.prepare_comparison`,
el `ComparisonSetup` aprobado y el periodo de mayo a abril. Exportar
las comparaciones con `scripts.run_comparison` y usar esos JSON al
construir la interfaz definitiva.

Desde la raíz del repo, con el build en `frontend/dist`:

```powershell
python -m scripts.qa_scientific_release
```

El comando ejecuta las comparaciones por HTTP y coteja los resultados
con los JSON que sirve el build en la ruta de GitHub Pages. Devuelve
un código distinto de cero ante datos incompletos, sintéticos o
distintos de los publicados. Con los archivos actuales enumera cuatro
escenarios bloqueados por ET₀ y la ausencia de `frontend/dist`.
El smoke en navegador se realiza con la interfaz definitiva.
