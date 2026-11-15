import { useState, type FormEvent } from "react";
import { Ledger } from "../components/Ledger";
import { QueryState } from "../components/QueryState";
import { useComparison } from "../data/queries";
import { probeHealth } from "../lib/api";
import { useInstrument } from "../store";

export function TrustScreen() {
  const lang = useInstrument((state) => state.lang);
  const spanish = lang === "es";
  const apiBase = useInstrument((state) => state.apiBase);
  const setApiBase = useInstrument((state) => state.setApiBase);
  const [draft, setDraft] = useState(apiBase);
  const [connecting, setConnecting] = useState(false);
  const [note, setNote] = useState<{ text: string; error: boolean } | null>(null);
  const comparison = useComparison();
  const loaded = comparison.data;
  const compare = loaded?.compare;
  const zona = compare?.zona ?? loaded?.catalog.zona;
  const missing = spanish ? "sin dato" : "no data";

  const sources = [
    {
      name: "NASA POWER",
      use: spanish ? "Clima para las corridas de la API" : "Climate input for API runs",
      detail: spanish ? "Lluvia, temperaturas, humedad, viento a 2 m y radiación diarios de la comunidad agrícola (AG). Los datos de prueba son sintéticos." : "Daily rain, temperatures, humidity, wind at 2 m, and radiation from the agricultural community (AG). Sample figures are synthetic.",
    },
    {
      name: "NOAA ONI / RONI",
      use: spanish ? "Selección de años parecidos" : "Selection of similar years",
      detail: spanish ? "Identifica la fase climática que usa el cálculo para armar el escenario." : "Identifies the climate phase used to build the scenario.",
    },
    {
      name: "SoilGrids, CHIRPS y FAO-56",
      use: spanish ? "Suelo, contraste de lluvia y método" : "Soil, rainfall cross-check, and method",
      detail: spanish ? "FAO-56 aporta el método del balance. CHIRPS se usa para contrastar la lluvia." : "FAO-56 supplies the water balance method. CHIRPS provides a rainfall cross-check.",
    },
    {
      name: "NASA GIBS",
      use: spanish ? "Imágenes del mapa" : "Map imagery",
      detail: spanish ? "MODIS Terra del 12 de marzo de 2024 y Blue Marble. Estas capas son visuales." : "MODIS Terra for 12 March 2024 and Blue Marble. These layers provide imagery.",
    },
    {
      name: "Esri / Maxar",
      use: spanish ? "Fotografía de referencia" : "Reference photography",
      detail: spanish ? "Fotografía satelital que se muestra por defecto en el mapa." : "The default satellite photography on the map.",
    },
    {
      name: spanish ? "Relieve AWS" : "AWS relief",
      use: spanish ? "Iluminación del terreno" : "Terrain lighting",
      detail: spanish ? "Las teselas regionales citan GMTED2010 y ETOPO1." : "The regional tiles cite GMTED2010 and ETOPO1.",
    },
  ];

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (connecting) return;
    const value = draft.trim();
    if (!value) {
      setApiBase("");
      setNote({ text: spanish ? "Se activaron los datos de prueba." : "Sample data is active.", error: false });
      return;
    }
    if (!/^https?:\/\//.test(value)) {
      setNote({ text: spanish ? "La dirección debe empezar por http:// o https://." : "The address must start with http:// or https://.", error: true });
      return;
    }
    setConnecting(true);
    setNote(null);
    try {
      const ok = await probeHealth(value);
      if (ok) {
        setApiBase(value);
        setNote({ text: spanish ? "La API respondió. Se está consultando el escenario." : "The API responded. The scenario is being requested.", error: false });
      } else {
        setNote({ text: spanish ? "Esa dirección no respondió en /health. Se conserva la fuente anterior." : "That address did not answer /health. The previous source is still active.", error: true });
      }
    } finally {
      setConnecting(false);
    }
  }

  return (
    <div className="screen">
      <article className="detail-page">
        <header className="detail-header">
          <h1>{spanish ? "Confianza y procedencia" : "Trust and provenance"}</h1>
          <p>{spanish ? "Qué se ha validado y qué aporta cada fuente al modelo o al mapa." : "What has been validated and what each source contributes to the model or the map."}</p>
        </header>
        <div className="detail-layout trust-layout">
          <section className="detail-panel trust-overview" aria-labelledby="trust-validation">
            <h2 id="trust-validation">{spanish ? "Estado de validación" : "Validation status"}</h2>
            <QueryState pending={comparison.isPending} error={comparison.isError} onRetry={() => comparison.refetch()} lang={lang} />
            {loaded?.httpDetail ? <p className="warn" role="alert">{loaded.httpDetail}</p> : null}
            <dl className="trust-facts">
              <div>
                <dt>{spanish ? "Punto del modelo" : "Model point"}</dt>
                <dd>{zona ? (zona.validated ? (spanish ? "Marcado como validado" : "Marked as validated") : (spanish ? "Provisional" : "Provisional")) : missing}</dd>
              </div>
              <div>
                <dt>{spanish ? "Años en la muestra" : "Years in the sample"}</dt>
                <dd>{compare?.analog_years.length ?? missing}</dd>
              </div>
              <div>
                <dt>{spanish ? "ET0 en la documentación" : "ET0 in the documentation"}</dt>
                <dd><code>reviewed: false</code></dd>
              </div>
              <div>
                <dt>{spanish ? "Perfil hidráulico" : "Hydraulic profile"}</dt>
                <dd>{spanish ? "Pendiente de aprobación" : "Approval pending"}</dd>
              </div>
            </dl>
            <p className="detail-footnote">{spanish ? "La revisión de ET0 y del perfil proviene de la documentación del proyecto. 2026 sigue en observación." : "ET0 and profile review status comes from the project documentation. Monitoring for 2026 is ongoing."}</p>
          </section>
          <section className="detail-panel trust-sources" aria-labelledby="trust-sources">
            <h2 id="trust-sources">{spanish ? "Fuentes y su uso" : "Sources and their role"}</h2>
            <ul className="source-list">
              {sources.map(({ name, use, detail }) => (
                <li key={name}>
                  <h3>{name}</h3>
                  <p className="source-use">{use}</p>
                  <p>{detail}</p>
                </li>
              ))}
            </ul>
            <details className="detail-disclosure">
              <summary>{spanish ? "Datos NASA fuera del balance" : "NASA data outside the balance"}</summary>
              <ul>
                <li><strong>GPM IMERG.</strong> {spanish ? "El plan del equipo lo dejó fuera por la licencia." : "The team plan left it out because of the license."}</li>
                <li><strong>SMAP.</strong> {spanish ? "Mide humedad de suelo a escala gruesa. El perfil hidráulico sigue pendiente." : "Measures soil moisture at coarse resolution. The hydraulic profile is pending."}</li>
                <li><strong>HLS.</strong> {spanish ? "La resolución de 30 m podría ayudar a ubicar una parcela." : "The 30 m resolution could help locate a field."}</li>
              </ul>
            </details>
          </section>
          <section className="detail-panel trust-api" aria-labelledby="trust-connect">
            <h2 id="trust-connect">{spanish ? "Conectar la API" : "Connect the API"}</h2>
            <p id="api-help" className="detail-lead">
              {spanish ? "Dejá la dirección vacía para usar los datos de prueba. La aplicación comprueba /health antes de cambiar de fuente." : "Leave the address empty to use sample data. The app checks /health before switching sources."}
            </p>
            <form className="trust-form" onSubmit={connect}>
              <label className="detail-field">{spanish ? "Dirección de la API" : "API address"}
                <input className="search" type="text" inputMode="url" spellCheck={false} autoComplete="off" aria-describedby="api-help" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="http://127.0.0.1:8000" disabled={connecting} />
              </label>
              <button type="submit" disabled={connecting}>{connecting ? (spanish ? "Comprobando…" : "Checking…") : (spanish ? "Conectar" : "Connect")}</button>
            </form>
            {connecting ? <p className="detail-footnote" role="status">{spanish ? "Consultando /health…" : "Checking /health…"}</p> : null}
            {note ? <p className={note.error ? "warn" : "detail-footnote"} role={note.error ? "alert" : "status"}>{note.text}</p> : null}
          </section>
          {loaded ? (
            <details className="detail-panel detail-disclosure trust-record">
              <summary>{spanish ? "Registro del cálculo" : "Calculation record"}</summary>
              <Ledger loaded={loaded} lang={lang} />
            </details>
          ) : null}
        </div>
      </article>
    </div>
  );
}
