# NandaView · AlairaX

**Un laboratorio de decisiones agrícolas para Guanacaste, Costa Rica.**

NandaView ayuda a explorar cómo distintas rotaciones de cultivo podrían responder a condiciones climáticas históricas. Combina datos públicos, un modelo de balance hídrico y visualizaciones interactivas para que productores y equipos técnicos puedan entender las diferencias entre escenarios y formular mejores preguntas para su finca.

El proyecto fue desarrollado por el equipo AlairaX para el reto **Field Shift** de NASA Space Apps Challenge. Es un **piloto regional**, no una recomendación agronómica validada para una finca.

## Qué permite hacer

- Explorar el mapa y seleccionar uno de los **11 cantones de Guanacaste**.
- Comparar tres rotaciones: arroz–melón, arroz–leguminosa y arroz–sorgo.
- Revisar demanda hídrica del cultivo, déficit de agua modelado y días de estrés, con resultados y variación entre temporadas análogas.
- Explorar series diarias de temporadas y consultar la procedencia y las limitaciones de los datos.
- Preguntar a **Guaní**, un asistente conectado a Gemini que interpreta el cantón, el escenario y los resultados seleccionados.

El mapa abre primero al ingresar a la aplicación. La capa de referencia por cantón corresponde a enero–marzo de 2014; no representa condiciones actuales. Guaní puede consultar clima más reciente disponible de NASA POWER, indicando sus fechas y posibles faltantes.

## Cómo funciona

1. **Datos climáticos:** NASA POWER aporta estimaciones diarias de precipitación, temperatura, humedad, viento y radiación para el punto de referencia. Los índices climáticos de NOAA apoyan la selección de escenarios.
2. **Temporadas análogas:** se identifican años históricos semejantes mediante características climáticas y búsqueda KNN. La selección de años es una señal regional compartida; no se recalcula para cada cantón.
3. **Simulación:** el modelo usa evapotranspiración de referencia FAO-56 Penman–Monteith, suelo estimado con SoilGrids y supuestos regionales de calendario y manejo para calcular el balance hídrico de cada rotación.
4. **Comparación:** las rotaciones se evalúan sobre los mismos años análogos. Los percentiles resumen la variación de las simulaciones; no son pronósticos ni intervalos de confianza.
5. **Interpretación:** Guaní recibe la selección, los resultados disponibles, las fuentes y las advertencias. Si falta evidencia, debe comunicarlo en lugar de inventar datos.

### Alcance y límites

Cada cantón está representado por un **punto de referencia**; no se trata de una medición en cada finca ni del promedio de todo el cantón. Las estimaciones de suelo y clima requieren validación local. Los calendarios, el manejo en secano y las condiciones iniciales son supuestos del piloto.

La disponibilidad reciente de las fuentes puede tener retrasos o faltantes. Cuando faltan entradas necesarias para continuar el balance, los resultados afectados se muestran como desconocidos. El modelo no demuestra ahorro de agua ni predice rendimiento, rentabilidad o una rotación ganadora. Las decisiones de manejo deben contrastarse con observaciones de campo y asesoría técnica.

## Ejecutar localmente

**Requisitos:** Python 3.12+, Node.js 22 y npm. Los comandos se ejecutan desde la raíz del repositorio, salvo indicación contraria.

### 1. Backend

```bash
python -m venv .venv
```

Activa el entorno virtual (`.venv\Scripts\activate` en PowerShell o `source .venv/bin/activate` en macOS/Linux) y ejecuta:

```bash
python -m pip install -r requirements.txt
python -m uvicorn backend.app.api.main:app --host 127.0.0.1 --port 8000
```

La documentación interactiva de la API está disponible en `http://127.0.0.1:8000/docs`.

### 2. Guaní

Copia `.env.example` a `.env.local` en la raíz y configura la variable del servidor:

```dotenv
GEMINI_API_KEY=tu_clave_de_gemini
```

La clave se mantiene en el backend y `.env.local` está excluido de Git. No uses el prefijo `VITE_` para credenciales. Sin la clave, el mapa y la simulación pueden utilizarse, pero Guaní no puede generar respuestas.

### 3. Frontend

En otra terminal:

```bash
cd frontend
npm ci
npm run dev
```

Abre la dirección local que indique Vite. En desarrollo, `/api` se redirige al backend en `127.0.0.1:8000`. Para usar otro servidor, consulta [frontend/.env.example](frontend/.env.example).

## Pruebas

```bash
# Backend, desde la raíz
python -m pytest backend/tests -q

# Frontend
cd frontend
npm test
npm run build
```

Las pruebas incluyen contratos, simulación, manejo de datos faltantes, selección de cantón e integración del asistente. Los resultados sintéticos utilizados en pruebas se identifican como tales.

## Despliegue

[vercel.json](vercel.json) define los servicios del frontend y del backend. Para habilitar Guaní, configura `GEMINI_API_KEY` como variable de entorno del proyecto en Vercel para **Production** y **Preview**. Las variables nuevas se aplican a despliegues posteriores. La función está configurada con un máximo de 300 segundos; verifica que el plan y la configuración del proyecto admitan esa duración.

También se incluye un flujo de GitHub Actions para publicar el frontend estático en GitHub Pages. Guaní y las consultas en vivo requieren un backend accesible; los archivos estáticos incluyen simulaciones precalculadas por cantón.

## Estructura del repositorio

```text
backend/app/       API, simulación, inteligencia y fuentes de datos
frontend/          Aplicación React, mapa y Guaní
datasets/          Datos procesados, ejemplos y controles de calidad
outputs/inputs/    Entradas preparadas para las comparaciones
research/          Parámetros y fuentes de investigación
scripts/           Ingesta, preparación, exportación y validación
docs/              Método, contratos y documentación técnica
```

## Documentación y fuentes

- [Asistente agrícola y API por cantón](docs/chatbot.md)
- [Ingesta y procedencia de datos](docs/data-ingestion.md)
- [Selección de análogos](docs/analog-method.md)
- [Validación del kernel](docs/kernel_validation.md)
- [Limitaciones de la lluvia](docs/rain_bias.md)
- [NASA POWER](https://power.larc.nasa.gov/) · [NOAA Climate Prediction Center](https://www.cpc.ncep.noaa.gov/) · [SoilGrids](https://soilgrids.org/) · [FAO-56](https://www.fao.org/4/x0490e/x0490e00.htm)

## Participantes

- Abraham Solano Parrales (Abe)
- Angelina
- Justin
- Antonio (Ant)

## Uso de IA

Se utilizaron herramientas de asistencia con IA durante el desarrollo. Las salidas del modelo y del asistente requieren revisión humana; la implementación no equivale a validación científica o de campo.

## Licencia

[MIT](LICENSE).
