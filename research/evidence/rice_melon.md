# Ficha de evidencia: rice_melon (arroz de secano seguido de melón regado)

Rotación actual de referencia. Estado: evidencia **preliminar**, sin validación de campo. Fecha 2026-11-14.

**Por qué se compara.** Es el punto de referencia (`is_current`); las otras dos se comparan contra ella por año.

**Evidencia.**
- Parámetros FAO-56 (Tablas 11, 12, 22) para arroz y melón; todos `verified: false` (ver `parameters/REVIEW_I3.md`).
- Kernel 2015 (modelado): arroz 810.1 mm de demanda, melón 615.1 mm, requerimiento de riego de la rotación 558.2 mm. El arroz queda por encima del rango FAO 450-700 mm y el melón apenas sobre 400-600 mm.
- Lluvia: POWER ≈ +29.5 % sobre IMN AIDO (1,545.9 mm/año, 2005-2025); el dato IMN de 1,652.7 mm/año aparece solo como **no verificado**.

**Beneficios posibles (hipótesis, no resultados).** Menor déficit hídrico del segundo cultivo por tener riego. Cualquier ahorro o rendimiento queda fuera de alcance.

**Vacíos.** Sin calendario local; sin Kc de arroz de secano; melón con etapas mediterráneas; perfil de suelo sin aprobar; calor del melón `null`; manejo del riego (láminas y turnos) no definido por fuente local.

**Riesgos.** El riego del melón depende de agua disponible no modelada; el arroz modelado como upland puede sobrestimar la demanda; un resultado favorable podría leerse como promesa.

**Lenguaje público.** Decir "déficit modelado" y "requerimiento de riego modelado"; no usar "ahorro", "rendimiento" ni "mejor rotación".
