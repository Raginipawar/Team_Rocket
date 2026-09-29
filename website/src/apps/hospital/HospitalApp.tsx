import { useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import Icon from "../../ui/Icon";
import { SimTag } from "../../ui/Bits";
import { useToast } from "../../ui/toast";
import DemoBar from "../shell/DemoBar";
import { useDemoActions } from "../../demo/actions";
import Dashboard from "./Dashboard";
import Analytics from "./Analytics";
import { Alerts, HSettings, PatientDetail, Resources, Rooms, Staff } from "./Pages";
import { initialRooms, useMinutesSince, type Room } from "./shared";

const KEY = "gh-hospital-login";

/* H1 · Login */
function Login({ onDone }: { onDone: () => void }) {
  const [id, setId] = useState("GHC-ER-07");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const submit = () => (pw === "demo" ? onDone() : setErr("Wrong ID or password"));
  return (
    <div className="h-login">
      <div className="h-login-card">
        <span className="logo-dot big" aria-hidden="true">+</span>
        <h1>Hospital log in</h1>
        <label className="lbl">Staff ID<input className="field" value={id} onChange={(e) => setId(e.target.value)} /></label>
        <label className="lbl">Password<input className="field" type="password" value={pw} onChange={(e) => { setPw(e.target.value); setErr(""); }} onKeyDown={(e) => e.key === "Enter" && submit()} /></label>
        {err ? <p className="err-text">{err}</p> : <p className="help">Demo password: <b>demo</b></p>}
        <button className="btn2 btn2-dark btn2-full btn2-lg" onClick={submit}>Log in</button>
        <a className="link-btn center-block" href="#/">Back to website</a>
      </div>
    </div>
  );
}

const MENU = [
  ["", "grid", "Dashboard"], ["rooms", "bed", "Rooms"], ["resources", "box", "Resources"], ["staff", "users", "Staff & shifts"],
  ["patient", "user", "Patients"], ["analytics", "chart", "Analytics"], ["alerts", "bell", "Alerts"], ["settings", "settings", "Settings"],
] as const;

export default function HospitalApp() {
  const nav = useNavigate();
  const toast = useToast();
  const { s, d } = useDemoActions();
  const [logged, setLogged] = useState(() => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } });
  const [rooms, setRooms] = useState<Room[]>(() => initialRooms(Date.now()));
  const [sounds, setSounds] = useState(true);
  const [confirmedAt, setConfirmedAt] = useState(() => Date.now() - 12 * 60000);
  const mins = useMinutesSince(confirmedAt);

  const setLogin = (v: boolean) => { setLogged(v); try { localStorage.setItem(KEY, v ? "1" : "0"); } catch { /* ignore */ } };
  if (!logged) return <Login onDone={() => setLogin(true)} />;

  const mine = d.hospitalId === "greenfield";
  const requests = mine && d.stage === "asking" ? 1 : 0;
  const incoming = 2 + (mine && d.stage === "transporting" ? 1 : 0);
  const atDoor = mine && d.stage === "atDoor" ? 1 : 0;
  const alerts = (s.signal === "lost" ? 1 : 0) + (s.worsenedAt ? 1 : 0) + 2;
  const tone = mins < 10 ? "ok" : mins <= 30 ? "warn" : "bad";

  return (
    <div className="h-app">
      <aside className="h-menu">
        <a href="#/" className="pshell-brand"><span className="logo-dot" aria-hidden="true">+</span>GoldenHour</a>
        <nav aria-label="Hospital">
          {MENU.map(([to, icon, label]) => (
            <NavLink key={label} to={`/hospital${to ? `/${to}` : ""}`} end={!to} className={({ isActive }) => (isActive ? "on" : "")}>
              <Icon name={icon} size={19} />{label}
              {label === "Alerts" && <span className="count">{alerts}</span>}
            </NavLink>
          ))}
        </nav>
        <p className="h-menu-foot">Best on a laptop, 1280 px or wider.</p>
      </aside>

      <div className="h-main">
        <header className="h-top">
          <div className="h-title"><h1>Greenfield Heart Centre</h1><SimTag /></div>
          <div className="h-avail">
            <button className="btn2 btn2-dark btn2-sm" onClick={() => { setConfirmedAt(Date.now()); toast("Availability confirmed"); }}>Confirm availability</button>
            <span className={`fresh fresh-${tone}`}><i />Last confirmed {mins === 0 ? "just now" : `${mins} min ago`}</span>
          </div>
          <div className="h-counters">
            <span className={requests ? "hot" : ""}><b>{requests}</b> {requests === 1 ? "request" : "requests"}</span>
            <span><b>{incoming}</b> incoming</span>
            <span className={atDoor ? "hot" : ""}><b>{atDoor}</b> at door</span>
          </div>
          <button className="icon-btn has-count" aria-label={`${alerts} alerts`} onClick={() => nav("/hospital/alerts")}><Icon name="bell" /><span>{alerts}</span></button>
          <div className="h-user"><b>Nurse P. Joshi</b><span>ER</span></div>
        </header>

        <Routes>
          <Route index element={<Dashboard rooms={rooms} sounds={sounds} />} />
          <Route path="rooms" element={<Rooms rooms={rooms} setRooms={setRooms} />} />
          <Route path="resources" element={<Resources />} />
          <Route path="staff" element={<Staff />} />
          <Route path="patient" element={<PatientDetail />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="settings" element={<HSettings sounds={sounds} setSounds={setSounds} onLogout={() => setLogin(false)} />} />
          <Route path="*" element={<Navigate to="/hospital" replace />} />
        </Routes>
      </div>
      <div className="demobar-fixed"><DemoBar /></div>
    </div>
  );
}
