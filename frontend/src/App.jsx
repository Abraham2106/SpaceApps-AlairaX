import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";

const API_KEY = import.meta.env.VITE_OPENWEATHER_KEY;

const CAPAS = [
  { nombre: "Temperatura", codigo: "temp_new", icono: "🌡️" },
  { nombre: "Lluvia", codigo: "precipitation_new", icono: "🌧️" },
  { nombre: "Nubes", codigo: "clouds_new", icono: "☁️" },
  { nombre: "Viento", codigo: "wind_new", icono: "💨" },
];

const banderaIcon = L.divIcon({
  className: "finca-marker",
  html: '<span class="cr-flag"></span>',
  iconSize: [42, 30],
  iconAnchor: [21, 15],
});

function SelectorDelMapa({ alSeleccionar }) {
  useMapEvents({
    click(event) {
      alSeleccionar({
        lat: event.latlng.lat,
        lon: event.latlng.lng,
      });
    },
  });

  return null;
}

function App() {
  const [coordenadas, setCoordenadas] = useState({
    lat: 9.93,
    lon: -84.08,
  });
  const [capaActiva, setCapaActiva] = useState(CAPAS[0]);
  const [clima, setClima] = useState(null);
  const [pronostico, setPronostico] = useState([]);
  const [finca, setFinca] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!API_KEY) {
      setError("No se encontró la clave de OpenWeather en el archivo .env.");
      return;
    }

    const controlador = new AbortController();

    async function consultarClima() {
      setCargando(true);
      setError("");

      const parametros = new URLSearchParams({
        lat: String(coordenadas.lat),
        lon: String(coordenadas.lon),
        appid: API_KEY,
        units: "metric",
        lang: "es",
      });

      try {
        const [respuestaClima, respuestaPronostico] = await Promise.all([
          fetch(
            `https://api.openweathermap.org/data/2.5/weather?${parametros}`,
            { signal: controlador.signal }
          ),
          fetch(
            `https://api.openweathermap.org/data/2.5/forecast?${parametros}&cnt=6`,
            { signal: controlador.signal }
          ),
        ]);

        if (!respuestaClima.ok || !respuestaPronostico.ok) {
          throw new Error(
            "OpenWeather no aceptó la solicitud. Revisa la clave o espera a que se active."
          );
        }

        const datosClima = await respuestaClima.json();
        const datosPronostico = await respuestaPronostico.json();

        setClima(datosClima);
        setPronostico(datosPronostico.list || []);
      } catch (e) {
        if (e.name !== "AbortError") {
          setError(e.message || "No se pudo consultar el clima.");
        }
      } finally {
        setCargando(false);
      }
    }

    consultarClima();

    return () => controlador.abort();
  }, [coordenadas]);

  function guardarFinca(event) {
    event.preventDefault();
    const datos = new FormData(event.currentTarget);

    setFinca({
      ubicacion: datos.get("ubicacion"),
      cultivo: datos.get("cultivo"),
      hectareas: datos.get("hectareas"),
    });
  }

  const urlCapa = API_KEY
    ? `https://tile.openweathermap.org/map/${capaActiva.codigo}/{z}/{x}/{y}.png?appid=${API_KEY}`
    : null;

  return (
    <main className="dashboard">
      <header className="topbar">
        <Link className="brand" to="/">Aureva</Link>
        <span className="topbar-caption">
          Clima para decisiones agrícolas
        </span>
      </header>

      <MapContainer
        center={[coordenadas.lat, coordenadas.lon]}
        zoom={7}
        scrollWheelZoom
        className="weather-map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {urlCapa && (
          <TileLayer
            key={capaActiva.codigo}
            url={urlCapa}
            opacity={0.65}
            attribution="Weather data © OpenWeather"
          />
        )}

        <SelectorDelMapa
          alSeleccionar={(punto) => setCoordenadas(punto)}
        />

        <Marker
          position={[coordenadas.lat, coordenadas.lon]}
          icon={banderaIcon}
        >
          <Popup>Punto seleccionado en el mapa</Popup>
        </Marker>
      </MapContainer>

      <section className="side-panel">
        <div className="panel-heading">
          <div>
            <span className="section-label">MI FINCA</span>
            <h1>Información agrícola</h1>
          </div>
          <span className="status-dot">●</span>
        </div>

        <p className="map-instruction">
          Haz clic en el mapa para consultar el clima de otro lugar.
        </p>

        <form className="farm-form" onSubmit={guardarFinca}>
          <label htmlFor="ubicacion">Nombre o ubicación de la finca</label>
          <input
            id="ubicacion"
            name="ubicacion"
            placeholder="Ej. Guanacaste, Costa Rica"
            required
          />

          <label htmlFor="cultivo">Cultivo principal</label>
          <select id="cultivo" name="cultivo" defaultValue="" required>
            <option value="" disabled>Selecciona un cultivo</option>
            <option value="Arroz">Arroz</option>
            <option value="Maíz">Maíz</option>
            <option value="Frijol">Frijol</option>
            <option value="Café">Café</option>
            <option value="Otro">Otro</option>
          </select>

          <label htmlFor="hectareas">Área de la finca (hectáreas)</label>
          <input
            id="hectareas"
            name="hectareas"
            type="number"
            min="0.1"
            step="0.1"
            placeholder="Ej. 5"
            required
          />

          <button className="submit-button" type="submit">
            Guardar información
          </button>
        </form>

        {finca && (
          <div className="farm-summary">
            <span className="section-label">FINCA REGISTRADA</span>
            <strong>{finca.ubicacion}</strong>
            <span>{finca.cultivo} · {finca.hectareas} hectáreas</span>
          </div>
        )}

        <section className="conditions">
          <span className="section-label">CLIMA EN EL PUNTO SELECCIONADO</span>

          {cargando && <p className="message">Consultando el clima…</p>}
          {error && <p className="error-message">{error}</p>}

          {clima && (
            <>
              <div className="temperature">
                <strong>{Math.round(clima.main.temp)}°C</strong>
                <span>{clima.weather?.[0]?.description}</span>
              </div>

              <div className="condition-row">
                <span>Sensación térmica</span>
                <strong>{Math.round(clima.main.feels_like)}°C</strong>
              </div>

              <div className="condition-row">
                <span>Humedad</span>
                <strong>{clima.main.humidity}%</strong>
              </div>

              <div className="condition-row">
                <span>Viento</span>
                <strong>{Math.round(clima.wind.speed * 3.6)} km/h</strong>
              </div>

              <div className="condition-row">
                <span>Lluvia registrada</span>
                <strong>{clima.rain?.["1h"] ?? 0} mm</strong>
              </div>
            </>
          )}
        </section>

        {pronostico.length > 0 && (
          <section className="forecast">
            <span className="section-label">PRÓXIMAS HORAS</span>

            {pronostico.map((periodo) => (
              <div className="forecast-row" key={periodo.dt}>
                <span>{periodo.dt_txt.slice(5, 16)}</span>
                <span>{Math.round(periodo.main.temp)}°C</span>
                <span>
                  {Math.round((periodo.pop || 0) * 100)}% prob. lluvia
                </span>
              </div>
            ))}
          </section>
        )}
      </section>

      <nav className="layers" aria-label="Capas del clima">
        <span className="section-label">CAPAS DEL MAPA</span>

        {CAPAS.map((capa) => (
          <button
            key={capa.codigo}
            type="button"
            className={
              capaActiva.codigo === capa.codigo
                ? "layer-button selected"
                : "layer-button"
            }
            onClick={() => setCapaActiva(capa)}
          >
            <span>{capa.icono}</span>
            {capa.nombre}
          </button>
        ))}
      </nav>
    </main>
  );
}

export default App;