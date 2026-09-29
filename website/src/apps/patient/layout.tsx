import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import Icon from "../../ui/Icon";

export function TopBar({ title, back, right, sub }: { title: ReactNode; back?: string | true; right?: ReactNode; sub?: ReactNode }) {
  const nav = useNavigate();
  return (
    <header className="ptop">
      {back && (
        <button className="icon-btn" aria-label="Back" onClick={() => (back === true ? nav(-1) : nav(back))}>
          <Icon name="back" />
        </button>
      )}
      <div className="ptop-title">
        <h2>{title}</h2>
        {sub && <span>{sub}</span>}
      </div>
      <div className="ptop-right">{right}</div>
    </header>
  );
}

export function TabBar() {
  const tabs = [
    ["/app", "home", "Home"], ["/app/family", "users", "Family"], ["/app/profile", "user", "Profile"], ["/app/history", "history", "History"],
  ] as const;
  return (
    <nav className="tabbar" aria-label="Main">
      {tabs.map(([to, icon, label]) => (
        <NavLink key={to} to={to} end className={({ isActive }) => (isActive ? "on" : "")}>
          <Icon name={icon} size={22} />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export function Call108({ compact }: { compact?: boolean }) {
  return (
    <a href="tel:108" className={`call108${compact ? " compact" : ""}`}>
      <Icon name="phone" size={18} />Call 108
    </a>
  );
}

/** Scrolling body + fixed bottom area, used by every patient screen. */
export function Screen({ children, bottom, tabs }: { children: ReactNode; bottom?: ReactNode; tabs?: boolean }) {
  return (
    <div className="pscreen">
      <div className="pscroll">{children}</div>
      {(bottom || tabs) && (
        <div className="pbottom">
          {bottom}
          {tabs && <TabBar />}
        </div>
      )}
    </div>
  );
}
