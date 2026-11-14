# Ficha de evidencia: rice_sorghum (arroz de secano seguido de sorgo)

Estado: evidencia **preliminar**. Fecha 2026-11-14.

**Por qué se compara.** Alternativa de secano con cultivo de raíz profunda tras el arroz.

**Evidencia.**
- Parámetros de **sorgo grano** (Kc 0.30/1.05/0.55, etapas 20/35/40/30, Zr 2.0 m, p 0.55; FAO-56 Tablas 11, 12, 22). La rotación declara sorgo forrajero; FAO forrajero: Kc mid 1.20, end 1.05, p 0.50 (decisión humana).
- Kernel 2015 (modelado): demanda 470.1 mm, dentro del rango FAO 450-650 mm.
- La suma de etapas del YAML es 125 d, y la fuente citada dice 130 d: revisar la fila de Tabla 11.
- Calendario por defecto: arroz 05-15 (termina el 11-oct) y sorgo 10-15, sin solape. Las fechas anteriores (arroz 06-01, sorgo 10-01) se solapaban. Falta validar el calendario con productores.

**Beneficios posibles (hipótesis).** Menor demanda de riego al no regar ningún segmento; se mide como déficit modelado, no como ahorro.

**Vacíos.** Destino forrajero o grano; calendario local; Zr de 2.0 m depende de un suelo profundo no confirmado (SoilGrids sin aprobar); calor `null`.

**Riesgos.** Raíz de 2.0 m sobrestima agua disponible si el suelo es somero; confundir déficit modelado con rendimiento.

**Lenguaje público.** "Déficit hídrico modelado en secano"; sin promesas de ahorro ni rendimiento.
