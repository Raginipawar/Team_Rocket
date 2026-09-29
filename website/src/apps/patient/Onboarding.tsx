import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import Icon from "../../ui/Icon";
import { Call108, Screen, TopBar } from "./layout";
import { getSession, setSession } from "./session";

/* P1 · Splash */
export function Splash() {
  const nav = useNavigate();
  useEffect(() => {
    const t = setTimeout(() => {
      const s = getSession();
      nav(s ? (s.setupDone ? "/app" : "/app/setup") : "/app/phone", { replace: true });
    }, 1200);
    return () => clearTimeout(t);
  }, [nav]);
  return (
    <div className="splash">
      <motion.div className="splash-logo" initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 0.5 }}>
        <span className="logo-dot big" aria-hidden="true">+</span>
        <h1>GoldenHour</h1>
        <p>The right hospital, ready before you arrive.</p>
      </motion.div>
      <Call108 compact />
    </div>
  );
}

/* P3 · Phone number */
export function PhoneEntry() {
  const nav = useNavigate();
  const [num, setNum] = useState("");
  const [touched, setTouched] = useState(false);
  const valid = /^\d{10}$/.test(num);
  return (
    <Screen bottom={<Call108 compact />}>
      <TopBar title="" />
      <div className="pad">
        <h1 className="ptitle">Enter your mobile number</h1>
        <div className={`phone-field${touched && !valid ? " err" : ""}`}>
          <span>+91</span>
          <input
            inputMode="numeric" autoFocus aria-label="Mobile number" placeholder="98765 43210"
            value={num} onChange={(e) => setNum(e.target.value.replace(/\D/g, "").slice(0, 10))} onBlur={() => setTouched(true)}
          />
        </div>
        {touched && num.length > 0 && !valid ? <p className="err-text">Please enter a valid 10-digit number</p> : <p className="help">We'll send a 6-digit code by SMS.</p>}
        <button className="btn2 btn2-dark btn2-full btn2-lg" disabled={!valid} onClick={() => nav("/app/otp", { state: { num } })}>Send code</button>
        <p className="fine">By continuing you agree to <a href="#/app/settings">Terms</a> &amp; <a href="#/app/settings">Privacy</a>.</p>
      </div>
    </Screen>
  );
}

/* P4 · OTP */
export function Otp() {
  const nav = useNavigate();
  const [digits, setDigits] = useState(["", "", "", "", "", ""]);
  const [tries, setTries] = useState(5);
  const [err, setErr] = useState("");
  const [wait, setWait] = useState(30);
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  const check = (code: string) => {
    if (code === "482913") {
      setSession({ phone: "+91 98XXX XX321", name: "Rahul", setupDone: false });
      nav("/app/permissions", { replace: true });
    } else {
      const left = tries - 1;
      setTries(left);
      setErr(left <= 0 ? "Too many attempts, try in 10 min" : `Wrong code, ${left} tries left`);
      setDigits(["", "", "", "", "", ""]);
      refs.current[0]?.focus();
    }
  };

  const set = (i: number, v: string) => {
    const c = v.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[i] = c;
    setDigits(next);
    setErr("");
    if (c && i < 5) refs.current[i + 1]?.focus();
    if (next.every(Boolean)) check(next.join(""));
  };

  return (
    <Screen bottom={<Call108 compact />}>
      <TopBar title="" back="/app/phone" />
      <div className="pad">
        <h1 className="ptitle">Enter the code sent to +91 98XXX XX321</h1>
        <div className="otp" role="group" aria-label="6 digit code">
          {digits.map((v, i) => (
            <input
              key={i} ref={(el) => { refs.current[i] = el; }} inputMode="numeric" maxLength={1} value={v} aria-label={`Digit ${i + 1}`}
              autoFocus={i === 0} disabled={tries <= 0}
              onChange={(e) => set(i, e.target.value)}
              onKeyDown={(e) => { if (e.key === "Backspace" && !v && i > 0) refs.current[i - 1]?.focus(); }}
            />
          ))}
        </div>
        {err ? <p className="err-text">{err}</p> : <p className="help">Demo code: <b>482913</b></p>}
        <button className="link-btn" disabled={wait > 0} onClick={() => setWait(30)}>
          {wait > 0 ? `Resend code in 0:${String(wait).padStart(2, "0")}` : "Resend code"}
        </button>
        <button className="link-btn" onClick={() => nav("/app/phone")}>Change number</button>
      </div>
    </Screen>
  );
}

function PermCard({ icon, title, line, state, onAllow }: { icon: string; title: string; line: string; state: string; onAllow: () => void }) {
  return (
  <div className="perm">
    <span className="perm-icon"><Icon name={icon} size={22} /></span>
    <div><b>{title}</b><p>{line}</p></div>
    {state === "ok" ? <span className="perm-ok"><Icon name="check" size={16} stroke={2.6} />Allowed</span>
      : state === "denied" ? <span className="perm-no">Off</span>
      : <button className="btn2 btn2-dark btn2-sm" onClick={onAllow}>Allow</button>}
  </div>
  );
}

/* P5 · Permissions (asks the browser for real) */
export function Permissions() {
  const nav = useNavigate();
  const [loc, setLoc] = useState<"idle" | "ok" | "denied">("idle");
  const [notif, setNotif] = useState<"idle" | "ok" | "denied">("idle");

  const askLoc = () => {
    if (!navigator.geolocation) return setLoc("denied");
    navigator.geolocation.getCurrentPosition(() => setLoc("ok"), () => setLoc("denied"), { timeout: 8000 });
  };
  const askNotif = async () => {
    if (!("Notification" in window)) return setNotif("denied");
    const r = await Notification.requestPermission();
    setNotif(r === "granted" ? "ok" : "denied");
  };

  return (
    <Screen bottom={<Call108 compact />}>
      <TopBar title="" />
      <div className="pad">
        <h1 className="ptitle">Two quick permissions</h1>
        <PermCard icon="pin" title="Location" line="So the ambulance can find you instantly." state={loc} onAllow={askLoc} />
        <PermCard icon="bell" title="Notifications" line="So we can tell you when the ambulance and hospital are ready." state={notif} onAllow={askNotif} />
        <button className="btn2 btn2-dark btn2-full btn2-lg" onClick={() => nav("/app/setup")}>Continue</button>
        <p className="fine">You can continue even without these.</p>
      </div>
    </Screen>
  );
}

/* P6 · Quick setup (3 steps, skippable) */
const BLOOD = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-", "Don't know"];
const ALLERGY = ["Penicillin", "Aspirin", "Sulfa", "Peanuts", "Latex", "None"];
const CONDITIONS = ["Diabetes", "High BP", "Heart disease", "Asthma", "Epilepsy", "Pregnancy", "Kidney disease", "None"];

export function Setup() {
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [blood, setBlood] = useState("O+");
  const [allergies, setAllergies] = useState<string[]>(["None"]);
  const [conds, setConds] = useState<string[]>(["None"]);
  const toggle = (list: string[], set: (v: string[]) => void, v: string) =>
    set(v === "None" ? ["None"] : list.includes(v) ? list.filter((x) => x !== v) : [...list.filter((x) => x !== "None"), v]);
  const finish = () => {
    const s = getSession();
    setSession({ phone: s?.phone ?? "", name: s?.name ?? "Rahul", setupDone: true });
    nav("/app", { replace: true });
  };

  return (
    <Screen bottom={
      <div className="pad-x row-2">
        <button className="btn2 btn2-light" onClick={finish}>Skip for now</button>
        <button className="btn2 btn2-dark" onClick={() => (step < 2 ? setStep(step + 1) : finish())}>{step < 2 ? "Next" : "Done"}</button>
      </div>
    }>
      <TopBar title="" />
      <div className="pad">
        <div className="dots" aria-label={`Step ${step + 1} of 3`}>{[0, 1, 2].map((i) => <i key={i} className={i <= step ? "on" : ""} />)}</div>
        {step === 0 && (
          <>
            <h1 className="ptitle">About you</h1>
            <label className="lbl">Your name<input className="field" defaultValue="Rahul Kulkarni" /></label>
            <div className="row-2">
              <label className="lbl">Age<input className="field" inputMode="numeric" defaultValue="32" /></label>
              <label className="lbl">Sex<select className="field" defaultValue="M"><option value="M">Male</option><option value="F">Female</option><option value="O">Other</option></select></label>
            </div>
          </>
        )}
        {step === 1 && (
          <>
            <h1 className="ptitle">Critical health info</h1>
            <p className="lbl-t">Blood group</p>
            <div className="chips-wrap">{BLOOD.map((b) => <button key={b} className={`pick${blood === b ? " on" : ""}`} onClick={() => setBlood(b)}>{b}</button>)}</div>
            <p className="lbl-t">Allergies</p>
            <div className="chips-wrap">{ALLERGY.map((a) => <button key={a} className={`pick${allergies.includes(a) ? " on" : ""}`} onClick={() => toggle(allergies, setAllergies, a)}>{a}</button>)}</div>
            <p className="lbl-t">Major conditions</p>
            <div className="chips-wrap">{CONDITIONS.map((c) => <button key={c} className={`pick${conds.includes(c) ? " on" : ""}`} onClick={() => toggle(conds, setConds, c)}>{c}</button>)}</div>
          </>
        )}
        {step === 2 && (
          <>
            <h1 className="ptitle">Family</h1>
            <p className="help">A family space lets anyone call help for anyone, and share health profiles.</p>
            <button className="option" onClick={() => { finish(); nav("/app/family"); }}><Icon name="users" /><span><b>Create a family space</b><small>Invite parents, siblings, add grandparents without phones</small></span><Icon name="chevron" /></button>
            <button className="option" onClick={() => { finish(); nav("/app/family/join"); }}><Icon name="userPlus" /><span><b>Join with a code</b><small>Someone in your family already has one</small></span><Icon name="chevron" /></button>
            <button className="option" onClick={finish}><Icon name="clock" /><span><b>Later</b><small>You can do this anytime from Family</small></span><Icon name="chevron" /></button>
          </>
        )}
      </div>
    </Screen>
  );
}
