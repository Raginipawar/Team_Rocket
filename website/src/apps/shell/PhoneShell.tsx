import type { ReactNode } from "react";
import DemoBar from "./DemoBar";

/**
 * On a laptop, a mobile app is shown inside the citizen style oval phone frame
 * with the demo controls beside it. On a real phone it simply fills the screen.
 */
export default function PhoneShell({ children, dark, title, landscape }: { children: ReactNode; dark?: boolean; title: string; landscape?: boolean }) {
  return (
    <div className={`pshell${dark ? " pshell-dark" : ""}`}>
      <div className="pshell-side">
        <a href="#/" className="pshell-brand"><span className="logo-dot" aria-hidden="true">+</span>GoldenHour</a>
        <h1>{title}</h1>
        <p>Every hospital, ambulance and person here is simulated sample data from the project plan.</p>
        <DemoBar inline />
      </div>
      <div className={`pshell-device${landscape ? " landscape" : ""}`}>
        <div className={`pshell-screen${dark ? " app-dark" : ""}`}>{children}</div>
      </div>
      <div className="pshell-mobile-bar"><DemoBar /></div>
    </div>
  );
}
