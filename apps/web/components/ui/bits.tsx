import type { HTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/cn";
import Icon, { type IconName } from "./icon";
import { Button } from "./button";

export function Card({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-[24px] border border-line bg-card p-5", className)} {...p} />;
}

export function SectionLabel({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn("text-[13px] font-bold uppercase tracking-[0.08em] text-muted", className)}>{children}</p>;
}

type Tone = "neutral" | "red" | "green" | "amber" | "blue" | "dark";
const tones: Record<Tone, string> = {
  neutral: "bg-soft text-ink",
  red: "bg-red-soft text-red-ink",
  green: "bg-green-soft text-green",
  amber: "bg-amber-soft text-amber",
  blue: "bg-blue-soft text-blue",
  dark: "bg-ink text-bg",
};

export function Pill({ tone = "neutral", icon, children, className }: { tone?: Tone; icon?: IconName; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1 text-[14px] font-semibold", tones[tone], className)}>
      {icon && <Icon name={icon} size={15} stroke={2.2} />}
      {children}
    </span>
  );
}

/** Every simulated entity shows this badge (UI rule 10). */
export function SimulatedBadge({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center rounded-full border border-dashed border-line px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-muted", className)} title="Simulated data for the demo">
      Simulated
    </span>
  );
}

export function Field({ label, hint, error, children, htmlFor }: { label: string; hint?: string; error?: string | null; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-[16px] font-semibold text-ink">{label}</label>
      {children}
      {hint && !error && <p className="text-[15px] text-muted">{hint}</p>}
      {error && <p className="flex items-center gap-1.5 text-[15px] font-medium text-red-ink" role="alert"><Icon name="alert" size={16} />{error}</p>}
    </div>
  );
}

const inputCls = "w-full rounded-2xl border-2 border-line bg-card px-4 text-[18px] text-ink placeholder:text-muted/70 focus:border-ink focus:outline-none";

export function Input({ className, ...p }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(inputCls, "h-14", className)} {...p} />;
}

export function Textarea({ className, ...p }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(inputCls, "min-h-32 py-3 leading-relaxed", className)} {...p} />;
}

export function Select({ className, children, ...p }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(inputCls, "h-14 appearance-none bg-[length:20px] bg-[right_16px_center] bg-no-repeat pr-12", className)}
      style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2357534e' stroke-width='2.2' stroke-linecap='round'%3E%3Cpath d='M5 9l7 7 7-7'/%3E%3C/svg%3E\")" }}
      {...p}>
      {children}
    </select>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <span className={cn("inline-block h-6 w-6 animate-spin rounded-full border-[3px] border-current border-t-transparent", className)} aria-hidden />;
}

/* ---------- screen states (§23: loading, empty, error, conflict, offline) ---------- */
export function LoadingState({ text = "Loading" }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted" role="status">
      <Spinner />
      <p className="text-[17px]">{text}…</p>
    </div>
  );
}

export function EmptyState({ icon = "info", title, text, action }: { icon?: IconName; title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-[24px] border-2 border-dashed border-line px-6 py-12 text-center">
      <span className="grid h-14 w-14 place-items-center rounded-full bg-soft text-muted"><Icon name={icon} size={26} /></span>
      <p className="text-[19px] font-semibold">{title}</p>
      {text && <p className="max-w-sm text-[16px] text-muted">{text}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ title = "Could not load this", text, onRetry }: { title?: string; text?: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-[24px] border-2 border-red/30 bg-red-soft px-6 py-10 text-center" role="alert">
      <Icon name="alert" size={28} className="text-red-ink" />
      <p className="text-[19px] font-semibold">{title}</p>
      {text && <p className="max-w-sm text-[16px] text-muted">{text}</p>}
      {onRetry && <Button variant="outline" onClick={onRetry}><Icon name="refresh" size={18} />Try again</Button>}
    </div>
  );
}

export function Banner({ tone = "amber", icon = "alert", children, action }: { tone?: "amber" | "red" | "blue" | "green"; icon?: IconName; children: ReactNode; action?: ReactNode }) {
  const t = { amber: "bg-amber-soft text-amber border-amber/30", red: "bg-red text-white border-red", blue: "bg-blue-soft text-blue border-blue/30", green: "bg-green-soft text-green border-green/30" }[tone];
  return (
    <div className={cn("flex items-center gap-3 rounded-2xl border px-4 py-3 text-[16px] font-semibold", t)} role={tone === "red" ? "alert" : "status"}>
      <Icon name={icon} size={20} className="shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
      {action}
    </div>
  );
}

export function KV({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="divide-y divide-line">
      {rows.map(([k, v]) => (
        <div key={k} className="flex items-start justify-between gap-4 py-2.5">
          <dt className="text-muted">{k}</dt>
          <dd className="text-right font-semibold">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
