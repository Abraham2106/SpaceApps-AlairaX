import type { ComponentProps } from "react";

export const buttonVariants = {
  default: "btn btn-primary",
  outline: "btn btn-quiet",
} as const;

export function Button({ className = "", variant = "default", ...props }: ComponentProps<"button"> & {
  variant?: keyof typeof buttonVariants;
}) {
  return <button data-slot="button" className={`${buttonVariants[variant]} ${className}`} {...props} />;
}
