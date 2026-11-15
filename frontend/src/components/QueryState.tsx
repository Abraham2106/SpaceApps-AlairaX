import { translate } from "../lib/i18n";
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
  if (pending) {
    return (
      <div className="state state-loading" role="status">
        <p>{translate(lang, "queryState.loadingComparison")}</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="state state-error" role="alert">
        <p>
          {translate(lang, "queryState.comparisonCouldNotBeLoaded")}
        </p>
        <button type="button" onClick={onRetry}>{translate(lang, "queryState.tryAgain")}</button>
      </div>
    );
  }
  return null;
}
