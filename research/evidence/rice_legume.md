# Ficha de evidencia: rice_legume (arroz de secano seguido de leguminosa de cobertura)

Estado: evidencia **preliminar**. Fecha 2026-11-14.

**Por qué se compara.** Alternativa de cobertura sin riego en el segundo cultivo.

**Evidencia.**
- Mucuna y canavalia no tienen parámetros FAO-56: quedan `null`. Se usa **caupí** como sustituto declarado (Kc 0.40/1.05/0.60, etapas 20/30/30/20, Zr 1.0 m, p 0.45; FAO-56 Tablas 11, 12, 22).
- Kernel 2015 (modelado): demanda del caupí 343.8 mm. No hay veredicto contra el rango FAO (el rango del código es de "Bean").
- Calendario por defecto: arroz 05-15 (termina el 11-oct) y caupí 10-15, sin solape. La fecha anterior del arroz (06-01) se solapaba. Falta validar el calendario con productores.

**Beneficios posibles (hipótesis, no verificadas aquí).** Cobertura del suelo y fijación de nitrógeno por leguminosas son efectos agronómicos generales; este proyecto no los modela ni los cuantifica.

**Vacíos.** Identidad real del cultivo de cobertura (mucuna, canavalia o caupí); Kc final según destino (0.60 fresco, 0.35 grano seco); calendario local; el modelo no incluye nitrógeno ni biomasa.

**Riesgos.** Sustituir mucuna/canavalia por caupí puede no representar la práctica real; el resultado es de agua, no de suelo ni de rendimiento.

**Lenguaje público.** "Cobertura modelada con caupí como sustituto"; sin afirmar mejora de suelo.
