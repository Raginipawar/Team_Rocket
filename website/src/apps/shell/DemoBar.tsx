import { useState } from "react";
import { STAGE_LABEL, useDemoActions } from "../../demo/actions";
import Icon from "../../ui/Icon";

const LINKS = [
  ["Patient", "#/app"], ["Ambulance", "#/crew"], ["Hospital", "#/hospital"], ["Family link", "#/track/8Kq2"], ["Ops", "#/ops"],
] as const;

/** Floating demo controls shown on every app surface (not part of the real product). */
export default function DemoBar({ inline }: { inline?: boolean }) {
  const { s, d, actions } = useDemoActions();
  const [open, setOpen] = useState(!!inline);

  if (!open) {
    return (
      <button className="demobar-pill" onClick={() => setOpen(true)} aria-label="Open demo controls">
        <span className="pulse-dot" />Demo<span className="demobar-stage-t">· {STAGE_LABEL[d.stage]}</span>
      </button>
    );
  }

  return (
    <div className={`demobar${inline ? " demobar-inline" : ""}`}>
      <div className="demobar-head">
        <span><span className="pulse-dot" /><b>Live demo</b> · simulated data</span>
        {!inline && <button aria-label="Close demo controls" onClick={() => setOpen(false)}><Icon name="x" size={16} /></button>}
      </div>
      <p className="demobar-stage">{STAGE_LABEL[d.stage]}</p>
      <div className="demobar-row">
        <button className="btn2 btn2-dark btn2-sm" onClick={actions.next}>Next step</button>
        <button className="btn2 btn2-light btn2-sm" onClick={actions.reset}>Reset</button>
      </div>
      <label className="switch-row">
        <span>Autoplay<small>Bots act for anyone not tapping</small></span>
        <input type="checkbox" className="switch" checked={s.autoplay} onChange={(e) => actions.setAutoplay(e.target.checked)} />
      </label>
      <div className="demobar-seg" role="group" aria-label="Ambulance signal">
        {(["ok", "weak", "lost"] as const).map((sig) => (
          <button key={sig} aria-pressed={s.signal === sig} onClick={() => actions.setSignal(sig)}>
            {sig === "ok" ? "Signal live" : sig === "weak" ? "Weak" : "Lost"}
          </button>
        ))}
      </div>
      <p className="demobar-hint">Open the apps in separate tabs and they stay in sync.</p>
      <div className="demobar-links">
        {LINKS.map(([label, href]) => <a key={href} href={href} target="_blank" rel="noreferrer">{label}</a>)}
      </div>
    </div>
  );
}
