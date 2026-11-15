import { z } from "zod";
import { ApiError } from "./api";
import { METRIC_IDS, SCENARIO_IDS } from "./types";

export const chatSelectionSchema = z.object({
  canton_ids: z.array(z.string().min(1)).min(1).max(5)
    .refine((ids) => new Set(ids).size === ids.length, "No repitas cantones."),
  start: z.string().date().optional(),
  end: z.string().date().optional(),
  scenario_id: z.enum(SCENARIO_IDS).nullable().optional(),
  metric: z.enum([...METRIC_IDS, "precipitation_mm", "et0_mm"]).nullable().optional(),
  years: z.array(z.number().int()).max(2).optional(),
}).strict();

const chatTurnSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string().min(1).max(6000),
}).strict();

export const chatRequestSchema = z.object({
  question: z.string().min(1).max(4000).regex(/\S/),
  selection: chatSelectionSchema,
  history: z.array(chatTurnSchema).max(12).optional(),
  farm: z.object({
    crop: z.string().max(120).nullable().optional(),
    growth_stage: z.string().max(120).nullable().optional(),
    irrigation: z.string().max(300).nullable().optional(),
  }).strict().optional(),
  language: z.enum(["es", "en"]).optional(),
}).strict();

export const chatContextSchema = z.object({
  model_scope: z.literal("regional_pilot"),
  _mock: z.literal(false),
  generated_at: z.string().datetime({ offset: true }),
  selection: chatSelectionSchema,
  // Preserve evidence, units, coverage, nulls, simulation runs and provenance
  // unchanged. The backend owns the scientific contracts and calculations.
  cantons: z.array(z.object({
    id: z.string(),
    status: z.enum(["available", "partial", "unavailable"]),
  }).passthrough()),
  sources: z.array(z.object({ id: z.string(), url: z.string(), provider: z.string() }).passthrough()),
  warnings: z.array(z.string()),
}).passthrough();

export const chatResponseSchema = z.object({
  answer: z.string().min(1),
  model: z.string().min(1),
  thinking_level: z.literal("low"),
  context: chatContextSchema,
}).strict();

export type ChatSelection = z.infer<typeof chatSelectionSchema>;
export type ChatRequest = z.infer<typeof chatRequestSchema>;
export type ChatContext = z.infer<typeof chatContextSchema>;
export type ChatResponse = z.infer<typeof chatResponseSchema>;

async function postChat(apiBase: string, path: string, payload: unknown, signal?: AbortSignal): Promise<unknown> {
  if (!apiBase.trim()) throw new ApiError(503, "Configura el backend para usar el asistente.");
  const response = await fetch(`${apiBase.replace(/\/$/, "")}${path}`, {
    method: "POST", signal,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body && typeof body === "object" && "detail" in body && typeof body.detail === "string"
      ? body.detail : "No se pudo completar la consulta al asistente.";
    throw new ApiError(response.status, detail);
  }
  return body;
}

function requireSelection(context: ChatContext, selection: ChatSelection): void {
  const sameIds = JSON.stringify(context.selection.canton_ids) === JSON.stringify(selection.canton_ids)
    && JSON.stringify(context.cantons.map(({ id }) => id)) === JSON.stringify(selection.canton_ids);
  const sameFilters = (["start", "end", "scenario_id", "metric"] as const)
    .every((key) => selection[key] === undefined || context.selection[key] === selection[key]);
  const sameYears = selection.years === undefined
    || JSON.stringify(context.selection.years) === JSON.stringify(selection.years);
  if (!sameIds || !sameFilters || !sameYears) {
    throw new ApiError(502, "La respuesta del asistente no corresponde a la selección actual.");
  }
}

/** Calls our server; Gemini credentials never enter the browser. */
export async function askChat(apiBase: string, request: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  const parsed = chatRequestSchema.parse(request);
  const response = chatResponseSchema.safeParse(await postChat(apiBase, "/chat", parsed, signal));
  if (!response.success) throw new ApiError(502, "El asistente devolvió una respuesta inválida.");
  requireSelection(response.data.context, parsed.selection);
  return response.data;
}

export async function loadChatContext(apiBase: string, selection: ChatSelection, signal?: AbortSignal): Promise<ChatContext> {
  const parsed = chatSelectionSchema.parse(selection);
  const response = chatContextSchema.safeParse(await postChat(apiBase, "/chat/context", parsed, signal));
  if (!response.success) throw new ApiError(502, "El contexto del asistente es inválido.");
  requireSelection(response.data, parsed);
  return response.data;
}
