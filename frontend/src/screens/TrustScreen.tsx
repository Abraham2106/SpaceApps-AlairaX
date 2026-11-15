import { useState } from "react";
import { Ledger } from "../components/Ledger";
import { useComparison } from "../data/queries";
import { probeHealth } from "../lib/api";
import { useInstrument } from "../store";

export function TrustScreen() {
  const lang = useInstrument((state) => state.lang);
  const spanish = lang === "es";
  const apiBase = useInstrument((state) => state.apiBase);
  const setApiBase = useInstrument((state) => state.setApiBase);
  const [draft, setDraft] = useState(apiBase);
  const [note, setNote] = useState<string | null>(null);
  const comparison = useComparison();
  const loaded = comparison.data;
  const compare = loaded?.compare;
  const zona = compare?.zona ?? loaded?.catalog.zona;

  async function connect() {
    const value = draft.trim();
    if (!value) {
      setApiBase("");
      setNote(spanish ? "Se vuelve a los fixtures." : "Back to the fixtures.");
      return;
    }
    if (!/^https?:\/\//.test(value)) {
      setNote(spanish ? "La dirección tiene que empezar por http:// o https://." : "The address must start with http:// or https://.");
      return;
    }
    const ok = await probeHealth(value);
    if (!ok) {
      setNote(spanish ? "Esa dirección no respondió en /health. No se cambia la fuente." : "That address did not answer /health. The source stays as it was.");
      return;
    }
    setApiBase(value);
    setNote(spanish ? "API conectada. Si un escenario no está disponible, se muestra el motivo y no se rellena con el fixture." : "API connected. If a scenario is unavailable, the reason is shown and the fixture is not used to fill it.");
  }

  return (
    <div className="screen">
      <article className="section stack">
        <p className="kicker">{spanish ? "Qué se puede creer" : "What can be believed"}</p>
        <h1>{spanish ? "Confianza y procedencia" : "Trust and provenance"}</h1>
        <div className="status-block">
          <p>{zona?.validated ? (spanish ? "La zona viene marcada como validada." : "The zone is marked validated.") : (spanish ? "La zona no está validada. El punto es provisional." : "The zone is not validated. The point is provisional.")}</p>
          <p>{spanish ? "La documentación del proyecto tiene la ET0 con reviewed: false y el perfil hidráulico sin aprobar. Esta respuesta no trae esos campos. No se dan por aprobados." : "The project documentation has ET0 reviewed: false and the hydraulic profile unapproved. This response does not carry those fields. They are not treated as approved."}</p>
          <p>{spanish ? "2026 es seguimiento. No se usa como año análogo." : "2026 is monitoring. It is not used as an analog year."}</p>
          <p>{compare ? (spanish ? `Muestra de esta respuesta: ${compare.analog_years.length}.` : `Sample in this response: ${compare.analog_years.length}.`) : null}</p>
        </div>
        {loaded ? <Ledger loaded={loaded} lang={lang} /> : null}
        <h2>{spanish ? "Datos de la NASA, separados de las cifras" : "NASA data, kept apart from the numbers"}</h2>
        <table>
          <caption>{spanish ? "Qué es NASA y qué no" : "What is NASA and what is not"}</caption>
          <thead>
            <tr>
              <th>{spanish ? "Fuente" : "Source"}</th>
              <th>{spanish ? "Dónde está" : "Where it is"}</th>
              <th>{spanish ? "Entra al balance" : "Enters the balance"}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">NASA POWER</th>
              <td>{spanish ? "Clima diario del pipeline real: lluvia, temperaturas, humedad, viento a 2 m, radiación. Comunidad AG." : "Daily climate of the real pipeline: rain, temperatures, humidity, 2 m wind, radiation. AG community."}</td>
              <td>{spanish ? "Sí, cuando hay una corrida real. No en un fixture." : "Yes, when there is a real run. Not in a fixture."}</td>
            </tr>
            <tr>
              <th scope="row">NASA GIBS</th>
              <td>{spanish ? "MODIS Terra del 12 de marzo de 2024 y Blue Marble, en el mapa." : "MODIS Terra for 12 March 2024 and Blue Marble, on the map."}</td>
              <td>{spanish ? "No. Es imagen." : "No. It is imagery."}</td>
            </tr>
            <tr>
              <th scope="row">{spanish ? "Relieve AWS" : "AWS relief"}</th>
              <td>{spanish ? "Iluminación del terreno. La tesela regional cita GMTED2010 y ETOPO1." : "Terrain lighting. The regional tile cites GMTED2010 and ETOPO1."}</td>
              <td>{spanish ? "No." : "No."}</td>
            </tr>
            <tr>
              <th scope="row">Esri / Maxar</th>
              <td>{spanish ? "Fotografía nítida de referencia." : "Sharp reference photography."}</td>
              <td>{spanish ? "No. Y no es NASA." : "No. And it is not NASA."}</td>
            </tr>
            <tr>
              <th scope="row">NOAA ONI / RONI</th>
              <td>{spanish ? "Fase del escenario en el pipeline." : "Scenario phase in the pipeline."}</td>
              <td>{spanish ? "Como rasgo del análogo, no como mapa." : "As an analog feature, not as a map."}</td>
            </tr>
            <tr>
              <th scope="row">SoilGrids, CHIRPS, FAO-56</th>
              <td>{spanish ? "Suelo, contraste de lluvia y método del balance. No son NASA." : "Soil, rain contrast, and the balance method. Not NASA."}</td>
              <td>{spanish ? "El método sí. CHIRPS es contraste, no la serie del kernel." : "The method, yes. CHIRPS is a contrast, not the kernel series."}</td>
            </tr>
          </tbody>
        </table>
        <h2>{spanish ? "Datos NASA que todavía no entran" : "NASA data that still stays out"}</h2>
        <ul>
          <li>{spanish ? "GPM IMERG podría afinar la lluvia. El plan del equipo lo dejó fuera por la licencia. No se pinta una lluvia que el contrato no entrega." : "GPM IMERG could refine rainfall. The team plan left it out because of the license. Rain the contract does not deliver is not painted."}</li>
          <li>{spanish ? "SMAP mide humedad de suelo a escala gruesa. No reemplaza el perfil hidráulico pendiente." : "SMAP measures coarse soil moisture. It does not replace the pending hydraulic profile."}</li>
          <li>{spanish ? "HLS, a 30 m, podría ayudar a ubicar una parcela. La nota de procedencia dice que no entra al balance." : "HLS, at 30 m, could help place a field. The provenance note says it does not enter the balance."}</li>
        </ul>
        <h2>{spanish ? "Conectar la API" : "Connect the API"}</h2>
        <p>{spanish ? "Vacío usa los fixtures. Una URL viva usa /health, /scenarios, /rotations, /sources y POST /compare. Un 409 o un 503 se muestran con su motivo." : "Empty uses the fixtures. A live URL uses /health, /scenarios, /rotations, /sources and POST /compare. A 409 or 503 is shown with its reason."}</p>
        <div className="row">
          <input className="search" value={draft} onChange={(event) => setDraft(event.target.value)} aria-label={spanish ? "Dirección de la API" : "API address"} placeholder="http://127.0.0.1:8000" />
          <button onClick={connect}>{spanish ? "Conectar" : "Connect"}</button>
        </div>
        {note ? <p role="status">{note}</p> : null}
      </article>
    </div>
  );
}
