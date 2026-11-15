/**
 * Puntos de quiebre del instrumento. Los mismos números viven en styles/responsive.css:
 *   móvil   ≤ 767   barra de abajo, hoja inferior con tres alturas
 *   tablet  768–1099  barra lateral solo con íconos, controles en dos filas
 *   ancho   ≥ 1100  barra lateral con nombres
 *   amplio  ≥ 1440  barra superior completa
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
