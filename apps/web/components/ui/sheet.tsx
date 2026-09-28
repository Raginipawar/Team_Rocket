"use client";

import * as D from "@radix-ui/react-dialog";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import Icon from "./icon";

/** Bottom sheet on phones, centred dialog on wider screens. Focus trapped, Esc closes. */
export function Sheet({ open, onOpenChange, title, description, children, footer, wide }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: string; children?: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-[80] bg-black/45 backdrop-blur-[1px]" />
        <D.Content
          className={cn(
            "fixed inset-x-0 bottom-0 z-[90] flex max-h-[92dvh] flex-col rounded-t-[28px] bg-card text-ink shadow-2xl outline-none",
            "sm:inset-auto sm:left-1/2 sm:top-1/2 sm:w-full sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-[28px]",
            wide ? "sm:max-w-2xl" : "sm:max-w-lg",
          )}
        >
          <div className="flex items-start gap-3 px-6 pt-6">
            <div className="min-w-0 flex-1">
              <D.Title className="text-[22px] font-bold leading-tight">{title}</D.Title>
              {description ? <D.Description className="mt-1 text-[16px] text-muted">{description}</D.Description> : <D.Description className="sr-only">{title}</D.Description>}
            </div>
            <D.Close className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-soft" aria-label="Close">
              <Icon name="x" size={20} />
            </D.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">{children}</div>
          {footer && <div className="flex flex-col gap-2 border-t border-line px-6 py-4 sm:flex-row sm:justify-end">{footer}</div>}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}
