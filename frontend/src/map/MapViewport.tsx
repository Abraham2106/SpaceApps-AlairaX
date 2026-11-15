import { translate } from "../lib/i18n";
import { Component, lazy, Suspense, useState, type ReactNode } from "react";
import type { Lang } from "../lib/types";

const LazyMap = lazy(() => import("./NandaMap").then(({ NandaMap }) => ({ default: NandaMap })));

class MapLoadBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export function MapViewport({ visible, lang }: { visible: boolean; lang: Lang }) {
  const [visited, setVisited] = useState(visible);
  if (visible && !visited) setVisited(true);
  if (!visible && !visited) return null;

  return (
    <MapLoadBoundary fallback={visible ? (
      <div className="map-load-state" role="alert">
        <p>{translate(lang, "mapViewport.mapCouldNotBeOpened")}</p>
        <button type="button" onClick={() => window.location.reload()}>
          {translate(lang, "mapViewport.reloadMap")}
        </button>
      </div>
    ) : null}>
      <Suspense fallback={visible ? (
        <p className="map-load-state" role="status">
          {translate(lang, "mapViewport.loadingMap")}
        </p>
      ) : null}>
        <LazyMap hidden={!visible} inset={visible ? "panel" : "open"} />
      </Suspense>
    </MapLoadBoundary>
  );
}
