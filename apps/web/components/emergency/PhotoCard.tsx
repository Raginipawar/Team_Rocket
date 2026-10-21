"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import type { PhotoAnalysis } from "@/lib/api-types";
import { Sheet } from "@/components/ui/sheet";
import Icon from "@/components/ui/icon";
import { cn } from "@/lib/cn";

const LABEL_TEXT: Record<string, string> = {
  bleeding: "Visible bleeding", burn: "Visible burn",
  bruise_fracture: "Bruising / possible fracture", none_minor: "No major visible injury",
  unclear: "Unclear",
};

/** The caller's attached photo, with its AI read (services/ml photo_triage:
 * a vision LLM + a separately fine-tuned classifier, shown together on tap
 * rather than picking one to display -- see PhotoAnalysis's own doc comment
 * in lib/api-types.ts for why). A plain <img> with the access token as a
 * query param, same fallback get_current_user already supports for the WS
 * connection, since an <img> tag can't send an Authorization header. */
export default function PhotoCard({ emergencyId, hasPhoto, analysis }: { emergencyId: string; hasPhoto?: boolean; analysis?: PhotoAnalysis }) {
  const { session } = useAuth();
  const [open, setOpen] = useState(false);
  if (!hasPhoto || !session?.token) return null;
  const src = `/api/v1/emergencies/${emergencyId}/photo?token=${encodeURIComponent(session.token)}`;
  const label = analysis?.finetuned_classifier?.label ?? analysis?.vision_llm?.label;

  return (
    <div className="flex flex-col gap-1.5">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <button type="button" onClick={() => setOpen(true)} className="relative block overflow-hidden rounded-2xl border border-line">
        <img src={src} alt="Photo from caller" className="h-40 w-full object-cover" />
        <span className={cn("absolute bottom-2 left-2 inline-flex items-center gap-1 rounded-full px-3 py-1 text-[13px] font-bold",
          !analysis ? "bg-ink/70 text-white" : analysis.needs_review ? "bg-amber text-white" : "bg-ink/85 text-white")}>
          {!analysis ? <><Icon name="clock" size={13} stroke={2.6} />Analyzing...</> : (label ? LABEL_TEXT[label] ?? label : "Unclear")}
        </span>
      </button>
      {analysis?.needs_review && (
        <p className="flex items-center gap-1.5 text-[13px] font-semibold text-amber">
          <Icon name="alert" size={14} stroke={2.6} />AI reads disagreed on this photo -- please look at it directly.
        </p>
      )}

      <Sheet open={open} onOpenChange={setOpen} title="Photo from caller" wide>
        <div className="flex flex-col gap-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt="Photo from caller" className="w-full rounded-2xl" />
          {analysis ? (
            <div className="flex flex-col gap-2 text-[15px]">
              <p>Vision model read: <b>{LABEL_TEXT[analysis.vision_llm.label] ?? analysis.vision_llm.label}</b>
                {analysis.vision_llm.confidence > 0 && <span className="text-muted"> ({Math.round(analysis.vision_llm.confidence * 100)}%)</span>}
              </p>
              <p>Fine-tuned classifier read: <b>{LABEL_TEXT[analysis.finetuned_classifier.label] ?? analysis.finetuned_classifier.label}</b>
                {analysis.finetuned_classifier.confidence > 0 && <span className="text-muted"> ({Math.round(analysis.finetuned_classifier.confidence * 100)}%)</span>}
              </p>
              <p className={cn("font-bold", analysis.agreement ? "text-green" : "text-amber")}>
                {analysis.agreement ? "Both models agree" : "Models disagree -- treat as needing human review"}
              </p>
            </div>
          ) : (
            <p className="flex items-center gap-1.5 text-[15px] text-muted"><Icon name="clock" size={16} stroke={2.4} />AI analysis still running...</p>
          )}
        </div>
      </Sheet>
    </div>
  );
}
