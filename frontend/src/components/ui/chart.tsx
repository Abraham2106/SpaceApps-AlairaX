// Adapted from shadcn/ui New York Chart for the existing CSS and theme tokens.
import { createContext, useContext, type ComponentProps, type CSSProperties, type ReactNode } from "react";
import { ResponsiveContainer, Tooltip } from "recharts";

export type ChartConfig = Record<string, { label: ReactNode; color: string }>;
const ChartContext = createContext<ChartConfig>({});

export function ChartContainer({ config, children, style, className = "", ...props }: ComponentProps<"div"> & {
  config: ChartConfig;
  children: ComponentProps<typeof ResponsiveContainer>["children"];
}) {
  const colors = Object.fromEntries(Object.entries(config).map(([key, { color }]) => [`--color-${key}`, color]));
  return (
    <ChartContext.Provider value={config}>
      <div data-slot="chart" className={`min-w-0 text-xs [&_.recharts-layer]:outline-none ${className}`} style={{ ...style, ...colors } as CSSProperties} {...props}>
        <ResponsiveContainer initialDimension={{ width: 300, height: 175 }}>{children}</ResponsiveContainer>
      </div>
    </ChartContext.Provider>
  );
}

export const ChartTooltip = Tooltip;

export function ChartTooltipContent({ active, payload, format }: {
  active?: boolean;
  payload?: ReadonlyArray<{ name?: unknown; value?: unknown; dataKey?: unknown; payload?: { rotation?: string } }>;
  format: (value: number) => string;
}) {
  const config = useContext(ChartContext);
  if (!active || !payload?.length) return null;
  return (
    <div data-slot="chart-tooltip">
      {payload.map((entry) => {
        const key = entry.payload?.rotation ?? String(entry.dataKey);
        const item = config[key];
        return (
          <div key={String(entry.dataKey)}>
            <i style={{ background: item?.color }} aria-hidden="true" /> {item?.label ?? String(entry.name)}
            <strong>{typeof entry.value === "number" ? format(entry.value) : "—"}</strong>
          </div>
        );
      })}
    </div>
  );
}
