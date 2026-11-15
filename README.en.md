# NandaView · AlairaX

[Español](README.md)

**An agricultural decision-making laboratory for Guanacaste, Costa Rica.**

NandaView helps explore how different crop rotations might respond to historical climate conditions. It combines public data, a water-balance model, and interactive visualizations so producers and technical teams can understand differences between scenarios and ask better questions about their farms.

The project was developed by the AlairaX team for the **Field Shift** challenge at the NASA Space Apps Challenge. It is a **regional pilot**, not an agronomic recommendation validated for any individual farm.

## What it lets you do

- Explore the map and select one of Guanacaste's **11 cantons**.
- Compare three rotations: rice–melon, rice–legume, and rice–sorghum.
- Review crop water demand, modeled water deficit, and stress days, including results and variation across analogous seasons.
- Explore daily season series and check data provenance and limitations.
- Ask **Guaní**, an assistant connected to Gemini that interprets the selected canton, scenario, and results.

The map is the first view when you open the application. The reference layer by canton corresponds to January–March 2014; it does not represent current conditions. Guaní can query the most recent climate data available from NASA POWER and report its dates and possible gaps.

## How it works

1. **Climate data:** NASA POWER provides daily estimates of precipitation, temperature, humidity, wind, and radiation for the reference point. NOAA climate indices support scenario selection.
2. **Analogous seasons:** Similar historical years are identified using climate features and KNN search. The selected years are a shared regional signal; they are not recalculated for each canton.
3. **Simulation:** The model uses FAO-56 Penman–Monteith reference evapotranspiration, soil estimates from SoilGrids, and regional calendar and management assumptions to calculate the water balance for each rotation.
4. **Comparison:** Rotations are evaluated over the same analogous years. Percentiles summarize variation across simulations; they are not forecasts or confidence intervals.
5. **Interpretation:** Guaní receives the selection, available results, sources, and warnings. If evidence is missing, it must say so rather than invent data.

### Scope and limitations

Each canton is represented by a **reference point**; this is not a measurement at each farm or an average for the entire canton. Soil and climate estimates require local validation. Calendars, rain-fed management, and initial conditions are pilot assumptions.

Recent source data may be delayed or missing. When required inputs are unavailable to continue the water balance, affected results are shown as unknown. The model does not demonstrate water savings or predict yield, profitability, or a winning rotation. Management decisions should be checked against field observations and technical advice.

## Run locally

**Requirements:** Python 3.12+, Node.js 22, and npm. Run commands from the repository root unless otherwise specified.

### 1. Backend

```bash
python -m venv .venv
```

Activate the virtual environment (`.venv\Scripts\activate` in PowerShell or `source .venv/bin/activate` on macOS/Linux), then run:

```bash
python -m pip install -r requirements.txt
python -m uvicorn backend.app.api.main:app --host 127.0.0.1 --port 8000
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

### 2. Guaní

Copy `.env.example` to `.env.local` in the root and configure the server variable:

```dotenv
GEMINI_API_KEY=tu_clave_de_gemini
```

The key stays in the backend, and `.env.local` is excluded from Git. Do not use the `VITE_` prefix for credentials. Without the key, the map and simulation can be used, but Guaní cannot generate responses.

### 3. Frontend

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open the local address shown by Vite. In development, `/api` is routed to the backend at `127.0.0.1:8000`. To use another server, see [frontend/.env.example](frontend/.env.example).

## Tests

```bash
# Backend, from the root
python -m pytest backend/tests -q

# Frontend
cd frontend
npm test
npm run build
```

The tests cover contracts, simulation, missing-data handling, canton selection, and assistant integration. Synthetic results used in tests are identified as such.

## Deployment

[vercel.json](vercel.json) defines the frontend and backend services. To enable Guaní, configure `GEMINI_API_KEY` as a project environment variable in Vercel for **Production** and **Preview**. New variables apply to subsequent deployments. The function is configured with a 300-second maximum; verify that the project plan and configuration support that duration.

A GitHub Actions workflow is also included to publish the static frontend to GitHub Pages. Guaní and live queries require an accessible backend; the static files include precomputed simulations by canton.

## Repository structure

```text
backend/app/       API, simulation, intelligence, and data sources
frontend/          React application, map, and Guaní
datasets/          Processed data, examples, and quality controls
outputs/inputs/    Prepared inputs for comparisons
research/          Research parameters and sources
scripts/           Ingestion, preparation, export, and validation
docs/              Methods, contracts, and technical documentation
```

## Documentation and sources

- [Agricultural assistant and canton API](docs/chatbot.md)
- [Data ingestion and provenance](docs/data-ingestion.md)
- [Analog selection](docs/analog-method.md)
- [Kernel validation](docs/kernel_validation.md)
- [Rainfall limitations](docs/rain_bias.md)
- [NASA POWER](https://power.larc.nasa.gov/) · [NOAA Climate Prediction Center](https://www.cpc.ncep.noaa.gov/) · [SoilGrids](https://soilgrids.org/) · [FAO-56](https://www.fao.org/4/x0490e/x0490e00.htm)

## Participants

- Abraham Solano Parrales (Abe)
- Angelina
- Justin
- Antonio (Ant)

## Use of AI

AI assistance tools were used during development. Model and assistant outputs require human review; the implementation does not constitute scientific or field validation.

## License

[MIT](LICENSE).
