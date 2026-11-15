// shadcn/ui New York Card slots, styled through this application's CSS.
import type { ComponentProps } from "react";

export function Card(props: ComponentProps<"div">) {
  const { className = "", ...rest } = props;
  return <div data-slot="card" className={`card ${className}`} {...rest} />;
}

export function CardHeader(props: ComponentProps<"div">) {
  return <div data-slot="card-header" {...props} />;
}

export function CardTitle(props: ComponentProps<"h2">) {
  return <h2 data-slot="card-title" {...props} />;
}

export function CardContent(props: ComponentProps<"div">) {
  return <div data-slot="card-content" {...props} />;
}
