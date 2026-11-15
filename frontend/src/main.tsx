import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import "@fontsource-variable/instrument-sans/wght.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import App from "./App";
import "./index.css";

// A direct visit opens the map; explicit hash links keep their destination.
if (!window.location.hash || window.location.hash === "#") {
  window.history.replaceState(window.history.state, "", `${window.location.pathname}${window.location.search}#/mapa`);
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </StrictMode>,
);
