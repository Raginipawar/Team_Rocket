"use client";

import { useState } from "react";
import { Sheet } from "@/components/ui/sheet";
import Icon from "@/components/ui/icon";

/** Small "i" button meant to sit absolutely-positioned in a map's corner
 * (caller wraps <Map/> in a `relative` container). Opens the server's own
 * route_explanation text -- the actual numbers that picked this route
 * (real OSRM distance/time), not a made-up score. Renders nothing when
 * there's no route yet, same "don't claim what we don't have" rule the
 * explanation text itself follows. */
export default function RouteInfoButton({ explanation }: { explanation?: string | null }) {
  const [open, setOpen] = useState(false);
  if (!explanation) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Why this route"
        className="absolute bottom-4 right-4 z-20 grid h-10 w-10 place-items-center rounded-full bg-ink/90 text-white shadow-lg backdrop-blur active:scale-95"
      >
        <Icon name="info" size={20} stroke={2.4} />
      </button>
      <Sheet open={open} onOpenChange={setOpen} title="Why this route" description="What actually decided the path drawn on the map.">
        <p className="text-[16px] leading-relaxed">{explanation}</p>
      </Sheet>
    </>
  );
}
