# Integración del kernel real · NandaView

La entrega de Justin incluye `simulate_rotation` y ET0 FAO-56. El comparador ya puede ejecutar ese callback y validar sus métricas y series diarias. La preparación admite temporadas mayo–abril con `--end-year-offset 1`, requiriendo todos los datos del año siguiente. La ventana usada para seleccionar análogos sigue siendo independiente y comparable entre años.

## Comprobación reproducible sin revisión científica pendiente

```powershell
python -m scripts.smoke_kernel
python -m scripts.inspect_calendars
python -m unittest backend.tests.test_kernel_handoff -v
```

El primer comando ejecuta el motor real con clima, suelo, manejo y vecinos sintéticos: tres rotaciones y dos temporadas, con 365 y 366 días. Escribe `datasets/examples/kernel-smoke.mock.json`, con `_mock=true`. Usa fechas de prueba explícitas para evitar traslapes y conserva las advertencias de parámetros no verificados. No es una selección KNN ni una aprobación del calendario; su finalidad es comprobar la conexión técnica y la exportación.

El segundo comando inspecciona los YAML originales sin modificarlos y escribe `datasets/processed/readiness/calendars.json`. Con las fechas actuales no hay solapes: el arroz sembrado el 15 de mayo, con 150 días, termina el 11 de octubre, antes del caupí y el sorgo (15 de octubre). Con las fechas anteriores (arroz el 1 de junio, sorgo el 1 de octubre) el arroz terminaba el 28 de octubre y se solapaba con ambos. Las fechas siguen sin validar con productores. El melón del 1 de diciembre termina el 29 de marzo de 2016 para la temporada 2015; requiere clima del año siguiente. No se acortan etapas ni se desplazan fechas automáticamente.

## Paso a resultados reales

El artefacto ET0 entregado contiene 16.754 fechas y 15.653 valores; conserva `reviewed=false` y `reviewed_by=null`. El lector admite sus metadatos de método, elevación y generación. Las guardas siguen impidiendo usarlo como revisado hasta que Justin confirme su revisión.

Ant y Justin deben confirmar los calendarios, parámetros y perfil hidráulico. Los conflictos del YAML no afectan la prueba sintética explícita, pero impiden considerar aprobadas esas rotaciones reales. El reporte de calendario y las salidas de prueba permiten avanzar con la integración mientras se realiza esa revisión.
