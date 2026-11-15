/**
 * Puntos de quiebre del instrumento. Los mismos números viven en styles/shell.css y styles/map.css:
 *   móvil   ≤ 767   barra de abajo; el panel de lectura va debajo del mapa
 *   tablet  768–1099  rail flotante; panel de lectura más angosto
 *   ancho   ≥ 1100  rail flotante y panel completo
 */
export const MOBILE_QUERY = "(max-width: 767px)";
export const TABLET_QUERY = "(min-width: 768px) and (max-width: 1099px)";

export function isMobile(): boolean {
  return typeof window !== "undefined" && window.matchMedia(MOBILE_QUERY).matches;
}

export function isTablet(): boolean {
  return typeof window !== "undefined" && window.matchMedia(TABLET_QUERY).matches;
}
import { useSyncExternalStore } from "react";


function subscribeToMobile(callback: () => void) {
  const media = window.matchMedia(MOBILE_QUERY);
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}

export function useMobileViewport(): boolean {
  return useSyncExternalStore(subscribeToMobile, isMobile, () => false);
}
