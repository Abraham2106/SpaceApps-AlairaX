import type { Lang } from "../lib/types";

/**
 * Carga y error de la comparación con la misma forma en todas las pantallas.
 * La carga se anuncia (role="status"); el error se anuncia (role="alert") y ofrece reintentar.
 */
export function QueryState({
  pending,
  error,
  onRetry,
  lang,
}: {
  pending: boolean;
  error: boolean;
  onRetry: () => void;
  lang: Lang;
}) {
  const spanish = lang === "es";
  if (pending) {
    return (
      <div className="state state-loading" role="status">
        <p>{spanish ? "Cargando la comparación…" : "Loading the comparison…"}</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="state state-error" role="alert">
        <p>
          {spanish
            ? "No se pudo leer la comparación. Revisa la conexión e inténtalo de nuevo."
            : "The comparison could not be loaded. Check the connection and try again."}
        </p>
        <button type="button" onClick={onRetry}>{spanish ? "Reintentar" : "Try again"}</button>
      </div>
    );
  }
  return null;
}
