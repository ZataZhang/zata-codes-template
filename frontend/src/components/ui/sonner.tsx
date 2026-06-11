import type { CSSProperties } from "react";
import { Toaster as Sonner, type ToasterProps } from "sonner";

const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      closeButton
      className="toaster group"
      style={
        {
          "--normal-bg": "rgba(255, 255, 255, 0.96)",
          "--normal-text": "rgb(15 23 42)",
          "--normal-border": "rgb(226 232 240)",
          "--border-radius": "18px",
        } as CSSProperties
      }
      toastOptions={{
        duration: 2000,
        classNames: {
          toast: "border border-border bg-popover text-accent-foreground shadow-sm",
          title: "text-sm font-semibold text-popover-foreground",
          description: "text-sm text-muted-foreground",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };
