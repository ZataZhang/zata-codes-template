import * as React from "react";

import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-9 w-full min-w-0 rounded-md border border-border bg-transparent px-3 py-1 text-base shadow-xs transition-[color,box-shadow] outline-none placeholder:text-muted-foreground disabled:pointer-events-none disabled:opacity-50 md:text-sm dark:border-border dark:placeholder:text-slate-400",
        "focus-visible:border-slate-950 focus-visible:ring-[3px] focus-visible:ring-slate-950/50 dark:focus-visible:border-slate-300 dark:focus-visible:ring-slate-300/50",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
