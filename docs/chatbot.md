# Asistente agrícola y piloto por cantón

El piloto cubre **los 11 cantones de Guanacaste**. Cada cantón usa su punto de
referencia, clima NASA POWER y retención de agua SoilGrids propios. No es una
medición de toda la superficie del cantón ni una validación de finca.

## Configuración local

El backend carga `.env.local` desde la raíz, sin sobrescribir variables del
entorno. Ese archivo está ignorado por Git y excluido del paquete de despliegue.
La clave nunca debe tener prefijo `VITE_` ni guardarse en el frontend.

```dotenv
GEMINI_API_KEY=tu_clave
```

Instalar `requirements.txt` y ejecutar:

```sh
python -m uvicorn backend.app.api.main:app --host 127.0.0.1 --port 8000
```

En despliegue se configura `GEMINI_API_KEY` en el entorno del servicio backend.
La configuración local no configura automáticamente el alojamiento remoto.

## Contratos HTTP

Las rutas están bajo `/api` en el proxy de Vite y en Vercel; directamente en
FastAPI usan las rutas siguientes:

| Ruta | Uso |
| --- | --- |
| `GET /chat/cantons` | Puntos canónicos de los 11 cantones de Guanacaste. |
| `POST /cantons/{id}/compare` | Contrato `CompareRequest` existente con la zona canónica del cantón. Devuelve las tres rotaciones y balances diarios. |
| `GET /cantons/{id}/recent` | Reproducciones anuales 2017–2026 para almacenamiento, mapas de calor y reproductor. |
| `POST /chat/context` | Evidencia del servidor para la selección, sin invocar Gemini. |
| `POST /chat` | Pregunta, selección, historial textual y datos opcionales de finca. |

Ejemplo de solicitud al chat:

```json
{
  "question": "¿Qué significa el déficit y qué debería revisar?",
  "selection": {
    "canton_ids": ["canas"],
    "start": "2025-01-01",
    "end": "2025-01-31",
    "scenario_id": "neutral",
    "metric": "modeled_water_deficit_mm",
    "years": [2025, 2024]
  },
  "history": [],
  "farm": {"crop": "arroz", "growth_stage": "vegetativa"},
  "language": "es"
}
```

La selección admite de uno a cinco cantones y hasta 366 días históricos. Si se
omiten las fechas, se consultan los 30 días anteriores a hoy en Costa Rica.
`scenario_id` agrega la comparación de rotaciones. `years` agrega hasta dos
reproducciones anuales cuando se solicita un escenario. Los valores científicos
se cargan en el servidor: el cliente no puede proporcionar un balance inventado.

El servidor devuelve `answer`, `model`, `thinking_level` y `context`. El contexto
conserva coordenadas, unidades, cobertura, faltantes, fuentes y advertencias. Para
mantener la respuesta dentro de los límites de Vercel, el contexto resume los
balances diarios de simulación; los detalles completos están disponibles en las
rutas de comparación y temporadas. El historial y los datos declarados de finca
se marcan como no verificados.

## Interpretación y límites

- Gemini usa `gemini-4-hydrogen`, nivel `low`, con el prompt versionado en
  `backend/app/application/chat_prompt.py`.
- La API de Interactions recibe `store: false`; el backend no guarda chats.
  El procesamiento por Google sigue sujeto a las condiciones de la cuenta.
- Los años análogos se conservan como señal regional compartida. No se afirma
  que el KNN haya sido recalculado o validado individualmente en cada cantón.
- El clima, elevación y suelo sí corresponden al punto del cantón seleccionado.
  Calendarios, profundidad de referencia y manejo son supuestos del piloto:
  secano y humedad inicial de 50 % del agua útil.
- ET0 FAO-56 es evapotranspiración de referencia. No equivale por sí sola a
  demanda del cultivo, déficit de suelo, estrés o una dosis de riego.
- La simulación calcula esas métricas de cultivo mediante el kernel existente.
  Los cuantiles describen años análogos; no son un pronóstico o intervalo de
  confianza. No se infiere rendimiento, rentabilidad ni causalidad.
- La cobertura reciente puede terminar antes de la fecha solicitada. Se indica
  la fecha disponible y no se sustituyen faltantes por cero ni por clima de otro
  cantón. Si no hay evidencia utilizable, el chat lo explica sin inventar análisis.
- Al seleccionar varios cantones, los paneles de simulación usan el primero;
  el chat puede consultar hasta cinco e identificar cada uno por separado.

Las descargas de clima se conservan temporalmente con procedencia y huella de
contenido; las respuestas recientes se refrescan para recoger días publicados
con retraso. Un primer cálculo puede tardar más mientras se descargan datos.

Documentación de referencia: [texto e instrucciones de Gemini](https://aistudio.google.com/docs/text-generation),
[niveles de razonamiento](https://aistudio.google.com/docs/thinking),
[NASA POWER](https://power.larc.nasa.gov/docs/services/api/temporal/daily/),
[FAO-56](https://www.fao.org/4/x0490e/x0490e00.htm).
