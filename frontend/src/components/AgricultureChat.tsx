import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { ArrowUp, ChevronDown, MapPin, RotateCcw, X } from "lucide-react";
import { useCantons } from "../data/queries";
import { useRecentSeasons } from "../data/recent";
import { askChat, type ChatContext, type ChatRequest, type ChatSelection } from "../lib/chat";
import { translate } from "../lib/i18n";
import { useInstrument } from "../store";
import type { Lang } from "../lib/types";
import idleMascot from "../assets/chat/bloub-idle.svg";
import attentiveMascot from "../assets/chat/bloub-attentive.svg";
import speakingMascot from "../assets/chat/bloub-speaking.gif";
import stillMascot from "../assets/chat/bloub-still.svg";

type Message = { role: "user" | "assistant"; content: string; context?: ChatContext };
type CantonOption = { id: string; name: string };

const COPY = {
  es: {
    title: "Guaní", subtitle: "Tu asistente de campo", open: "Preguntarle a Guaní", close: "Cerrar asistente",
    greeting: "Entendamos lo que pasa en el campo.",
    intro: "Te ayudo a leer los datos del cantón y la simulación: qué muestran, qué conviene revisar y qué hace falta para decidir.",
    choose: "Elige un cantón de Guanacaste para empezar.", canton: "Cantón para la consulta", noCanton: "Seleccionar cantón",
    suggestions: "Podemos empezar por aquí", placeholder: "¿Qué significan estos datos para mi cultivo?",
    input: "Tu pregunta sobre los datos agrícolas", send: "Enviar pregunta", working: "Revisando los datos de tu cantón…",
    thinking: "Analizando", speaking: "Respuesta lista", ready: "Lista para ayudarte", you: "Tú",
    retry: "Intentar de nuevo", reset: "Nueva conversación", error: "No pude completar la consulta. Vuelve a intentarlo.",
    offline: "El asistente no está disponible en esta versión. Puedes seguir consultando los datos del mapa.",
    tooMany: "Selecciona hasta cinco cantones para hacer una consulta.", loading: "Cargando cantones…",
    loadError: "No se pudieron cargar los cantones. Intenta abrir el asistente nuevamente.",
    pilot: "Piloto regional · Verifica las decisiones en tu finca.", context: "Contexto de la consulta",
    coverage: "Clima consultado", sources: "Fuentes de esta respuesta", recent: "Clima reciente disponible",
    multiple: "cantones", keyboard: "Enter para enviar · Mayús + Enter para una nueva línea",
    prompts: ["¿Qué está pasando con el agua?", "¿Cómo se comparan las rotaciones?", "¿Qué debería revisar en mi finca?", "¿Qué limitaciones tienen estos datos?"],
  },
  en: {
    title: "Guaní", subtitle: "Your field assistant", open: "Ask Guaní", close: "Close assistant",
    greeting: "Let's understand what's happening in the field.",
    intro: "I help you interpret your canton's data and simulation: what they show, what to check and what is needed to decide.",
    choose: "Choose a canton in Guanacaste to begin.", canton: "Canton for this question", noCanton: "Select canton",
    suggestions: "A few places to start", placeholder: "What do these data mean for my crop?",
    input: "Your question about agricultural data", send: "Send question", working: "Reviewing your canton's data…",
    thinking: "Analyzing", speaking: "Answer ready", ready: "Ready to help", you: "You",
    retry: "Try again", reset: "New conversation", error: "The question could not be completed. Please try again.",
    offline: "The assistant is unavailable in this version. You can still explore the map data.",
    tooMany: "Select up to five cantons for a question.", loading: "Loading cantons…",
    loadError: "The cantons could not be loaded. Try opening the assistant again.",
    pilot: "Regional pilot · Verify decisions on your farm.", context: "Question context",
    coverage: "Climate period", sources: "Sources for this answer", recent: "Recent available climate",
    multiple: "cantons", keyboard: "Enter to send · Shift + Enter for a new line",
    prompts: ["What is happening with the water?", "How do the rotations compare?", "What should I check on my farm?", "What are the limits of these data?"],
  },
};

function Mascot({ state = "idle", className = "" }: { state?: "idle" | "working" | "speaking"; className?: string }) {
  const animated = state === "working" ? attentiveMascot : state === "speaking" ? speakingMascot : idleMascot;
  return <span className={`nanda-mascot ${className}`} aria-hidden="true" data-state={state}>
    <img className="nanda-mascot-motion" src={animated} alt="" width="72" height="72" />
    <img className="nanda-mascot-still" src={stillMascot} alt="" width="72" height="72" />
  </span>;
}

/** Small safe text treatment: React escapes content; the model cannot inject HTML. */
function inlineText(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => part.startsWith("**") && part.endsWith("**")
    ? <strong key={index}>{part.slice(2, -2)}</strong> : part);
}

function Answer({ text }: { text: string }) {
  return <div className="nanda-answer">{text.split(/\n\s*\n/).map((block, index) => {
    const lines = block.split("\n");
    if (lines.every((line) => /^\s*[-*]\s/.test(line))) {
      return <ul key={index}>{lines.map((line, i) => <li key={i}>{inlineText(line.replace(/^\s*[-*]\s/, ""))}</li>)}</ul>;
    }
    return <p key={index}>{inlineText(block.replace(/^#{1,4}\s/, ""))}</p>;
  })}</div>;
}

function Evidence({ context, lang }: { context: ChatContext; lang: Lang }) {
  const copy = COPY[lang];
  const sourceNames = [...new Set(context.sources.map((source) => source.provider))];
  return <details className="nanda-evidence">
    <summary>{copy.sources}<ChevronDown size={12} aria-hidden /></summary>
    <div>
      {context.selection.start && context.selection.end && <p>{copy.coverage}: {context.selection.start} → {context.selection.end}</p>}
      {context.cantons.some((canton) => canton.status !== "available") && <p>{lang === "es" ? "La cobertura climática tiene faltantes. Los valores ausentes no representan cero." : "Climate coverage has gaps. Missing values do not represent zero."}</p>}
      {sourceNames.length > 0 && <p>{sourceNames.join(" · ")}</p>}
      {context.warnings.map((warning) => <p key={warning}>{warning}</p>)}
    </div>
  </details>;
}

type SessionProps = {
  open: boolean;
  onClose: () => void;
  onRestoreFocus: () => void;
  apiBase: string;
  selection: ChatSelection;
  cantons: CantonOption[];
  cantonsPending: boolean;
  cantonsError: boolean;
  lang: Lang;
};

function ChatSession({ open, onClose, onRestoreFocus, apiBase, selection, cantons, cantonsPending, cantonsError, lang }: SessionProps) {
  const copy = COPY[lang];
  const titleId = useId();
  const inputId = useId();
  const selectOnly = useInstrument((state) => state.selectOnly);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryQuestion, setRetryQuestion] = useState<string | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const cantonSelect = useRef<HTMLSelectElement>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const controller = useRef<AbortController | null>(null);
  const isSending = useRef(false);
  const alive = useRef(true);
  const nearBottom = useRef(true);
  const knownIds = new Set(cantons.map((canton) => canton.id));
  const validSelection = selection.canton_ids.length > 0 && selection.canton_ids.length <= 5
    && selection.canton_ids.every((id) => knownIds.has(id));
  const enabled = validSelection && Boolean(apiBase) && !pending;
  const names = selection.canton_ids.map((id) => cantons.find((canton) => canton.id === id)?.name ?? id);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; controller.current?.abort(); };
  }, []);

  useEffect(() => {
    if (open) (validSelection ? input.current : cantonSelect.current)?.focus();
  }, [open, validSelection]);

  useEffect(() => {
    if (!open) return;
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.defaultPrevented) {
        onClose();
        onRestoreFocus();
      }
    };
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [open, onClose, onRestoreFocus]);

  useEffect(() => {
    if (transcript.current && nearBottom.current) transcript.current.scrollTop = transcript.current.scrollHeight;
  }, [messages, pending, error]);

  useEffect(() => {
    if (!speaking) return;
    const timer = window.setTimeout(() => setSpeaking(false), 6500);
    return () => window.clearTimeout(timer);
  }, [speaking]);

  async function send(question: string, retry = false) {
    const trimmed = question.trim();
    if (!trimmed || !enabled || isSending.current) return;
    isSending.current = true;
    const requestController = new AbortController();
    controller.current = requestController;
    setPending(true);
    setSpeaking(false);
    setError(null);
    setRetryQuestion(null);
    setDraft("");
    input.current?.focus();
    nearBottom.current = true;
    const historyMessages = retry ? messages.slice(0, -1) : messages;
    const history: ChatRequest["history"] = historyMessages.slice(-12)
      .map(({ role, content }) => ({ role, content: content.slice(0, 6000) }));
    if (!retry) setMessages((current) => [...current, { role: "user", content: trimmed }]);
    try {
      const response = await askChat(apiBase, { question: trimmed, selection, history, language: lang }, requestController.signal);
      if (requestController.signal.aborted || !alive.current) return;
      setMessages((current) => [...current, { role: "assistant", content: response.answer, context: response.context }]);
      setSpeaking(true);
    } catch (failure) {
      if (requestController.signal.aborted || !alive.current) return;
      // The server's provider details and internal stack never belong in this surface.
      const rateLimited = failure && typeof failure === "object" && "status" in failure && failure.status === 429;
      setError(rateLimited
        ? lang === "es" ? "Hay muchas consultas en este momento. Espera un poco y vuelve a intentarlo." : "There are too many questions right now. Wait a moment and try again."
        : copy.error);
      setRetryQuestion(trimmed);
    } finally {
      if (alive.current && !requestController.signal.aborted) {
        setPending(false);
        isSending.current = false;
      }
    }
  }

  function reset() {
    controller.current?.abort();
    isSending.current = false;
    setPending(false);
    setSpeaking(false);
    setMessages([]);
    setError(null);
    setRetryQuestion(null);
    setDraft("");
    input.current?.focus();
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  return <section className="nanda-chat-panel" data-open={open} inert={!open} aria-hidden={!open} role="dialog" aria-modal="false"
    aria-labelledby={titleId} onKeyDown={(event) => {
      if (event.key === "Escape") { event.stopPropagation(); onClose(); onRestoreFocus(); }
    }}>
    <header className="nanda-chat-header">
      <div className="nanda-chat-identity"><Mascot state={pending ? "working" : speaking ? "speaking" : "idle"} />
        <div><h2 id={titleId}>{copy.title}</h2></div>
      </div>
      <div className="nanda-chat-actions">
        {messages.length > 0 && <button type="button" onClick={reset} aria-label={copy.reset} title={copy.reset}><RotateCcw size={16} aria-hidden /></button>}
        <button type="button" onClick={() => { onClose(); onRestoreFocus(); }} aria-label={copy.close}><X size={19} aria-hidden /></button>
      </div>
    </header>

    <div className="nanda-chat-context" aria-label={copy.context}>
      <MapPin size={14} aria-hidden />
      <label className="sr-only" htmlFor={`${inputId}-canton`}>{copy.canton}</label>
      <select ref={cantonSelect} id={`${inputId}-canton`} value={selection.canton_ids[0] ?? ""}
        onChange={(event) => selectOnly(event.target.value)} disabled={cantonsPending || cantonsError}>
        <option value="" disabled>{cantonsPending ? copy.loading : copy.noCanton}</option>
        {cantons.map((canton) => <option key={canton.id} value={canton.id}>{canton.name}</option>)}
      </select>
      {names.length > 1 && <span className="nanda-chat-multi" title={names.join(", ")}>+{names.length - 1}</span>}
      <span className="nanda-chat-context-scenario">{selection.scenario_id ? translate(lang, `scenario.${selection.scenario_id}`) : copy.recent}</span>
    </div>

    <div ref={transcript} className="nanda-chat-transcript" onScroll={() => {
      const element = transcript.current;
      if (element) nearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
    }}>
      {messages.length === 0 ? <div className="nanda-chat-intro">
        <Mascot className="nanda-mascot-welcome" />
        <h3>{copy.greeting}</h3>
        <p>{copy.intro}</p>
        {!validSelection && <p className="nanda-chat-hint">{selection.canton_ids.length > 5 ? copy.tooMany : copy.choose}</p>}
        <div className="nanda-chat-suggestions">
          <p>{copy.suggestions}</p>
          {copy.prompts.map((prompt) => <button type="button" key={prompt} disabled={!enabled} onClick={() => void send(prompt)}>
            <span>{prompt}</span><ArrowUp size={15} aria-hidden />
          </button>)}
        </div>
      </div> : <div className="nanda-chat-messages" role="log" aria-live="polite" aria-relevant="additions" aria-label={lang === "es" ? "Conversación con Guaní" : "Conversation with Guaní"}>
        {messages.map((message, index) => <article className={`nanda-message nanda-message-${message.role}`} key={index}>
          <div className="nanda-message-label">{message.role === "assistant" && <Mascot />}<span>{message.role === "assistant" ? copy.title : copy.you}</span></div>
          <Answer text={message.content} />
          {message.context && <Evidence context={message.context} lang={lang} />}
        </article>)}
      </div>}
      {pending && <div className="nanda-chat-pending" role="status"><Mascot state="working" /><span>{copy.working}</span></div>}
      {cantonsError && <p className="nanda-chat-notice" role="alert">{copy.loadError}</p>}
      {!apiBase && <p className="nanda-chat-notice" role="status">{copy.offline}</p>}
      {error && <div className="nanda-chat-error" role="alert"><p>{error}</p>
        {retryQuestion && <button type="button" disabled={!enabled} onClick={() => void send(retryQuestion, true)}><RotateCcw size={14} aria-hidden />{copy.retry}</button>}
      </div>}
    </div>

    <footer className="nanda-chat-footer">
      {selection.years && selection.years.length > 0 && <p className="nanda-chat-years">{lang === "es" ? "Temporadas consultadas" : "Seasons in view"}: {selection.years.join(" / ")}</p>}
      <form className="nanda-chat-composer" onSubmit={submit}>
        <label className="sr-only" htmlFor={inputId}>{copy.input}</label>
        <textarea ref={input} id={inputId} value={draft} maxLength={4000} rows={2}
          placeholder={validSelection ? copy.placeholder : copy.choose} disabled={!validSelection || !apiBase}
          onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (!pending) void send(draft); }
          }} />
        <button type="submit" aria-label={copy.send} disabled={!enabled || !draft.trim()}><ArrowUp size={20} strokeWidth={2} aria-hidden /></button>
      </form>
    </footer>
  </section>;
}

export function AgricultureChat() {
  const lang = useInstrument((state) => state.lang);
  const selected = useInstrument((state) => state.selected);
  const scenarioId = useInstrument((state) => state.scenarioId);
  const metric = useInstrument((state) => state.metric);
  const yearA = useInstrument((state) => state.yearA);
  const yearB = useInstrument((state) => state.yearB);
  const apiBase = useInstrument((state) => state.apiBase);
  const [open, setOpen] = useState(false);
  const launcher = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  const cantonQuery = useCantons();
  const recent = useRecentSeasons();
  const cantons = (cantonQuery.data?.features ?? []).filter((feature) => feature.properties.guanacaste)
    .map((feature) => ({ id: String(feature.id), name: feature.properties.name })).sort((a, b) => a.name.localeCompare(b.name, lang));
  const availableYears = recent.data?.seasons.map(({ year }) => year).sort((a, b) => b - a) ?? [];
  const activeA = yearA !== null && availableYears.includes(yearA) ? yearA : availableYears[0];
  const activeB = yearB !== null && availableYears.includes(yearB) ? yearB : availableYears[1] ?? availableYears[0];
  const years = [...new Set([activeA, activeB].filter((year): year is number => year !== undefined))];
  const selection: ChatSelection = { canton_ids: selected, scenario_id: scenarioId, metric, ...(years.length ? { years } : {}) };
  // A new context gets a new session. Unmount aborts its request so a previous
  // canton's answer can never appear under a different selection.
  const contextKey = JSON.stringify([selected, scenarioId, metric, years, lang, apiBase]);
  useEffect(() => {
    if (wasOpen.current && !open) launcher.current?.focus();
    wasOpen.current = open;
  }, [open]);
  return <div className="nanda-chat">
    <ChatSession key={contextKey} open={open} onClose={() => setOpen(false)} onRestoreFocus={() => launcher.current?.focus()}
      apiBase={apiBase} selection={selection} cantons={cantons} cantonsPending={cantonQuery.isPending} cantonsError={cantonQuery.isError} lang={lang} />
    <button ref={launcher} className="nanda-chat-launcher" type="button" aria-expanded={open}
      aria-label={COPY[lang].open} hidden={open} onClick={() => setOpen(true)}>
      <Mascot />
    </button>
  </div>;
}
