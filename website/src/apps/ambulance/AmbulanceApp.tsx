import { useEffect, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import PhoneShell from "../shell/PhoneShell";
import Icon, { CategoryIcon } from "../../ui/Icon";
import { AmbType, Banner, Confidence, CountdownRing, Eta, SeverityBadge, SignalBadge, WhyChips } from "../../ui/Bits";
import DemoMap from "../../ui/DemoMap";
import { Dialog, ReasonDialog } from "../../ui/Dialog";
import { useToast } from "../../ui/toast";
import { CATEGORIES, CATEGORY_LABEL, HOSPITALS, QUESTIONS, QUESTION_SHORT, REASONS, type Category, type Severity } from "../../demo/data";
import { useDemoActions } from "../../demo/actions";
import { hospitalInfo } from "../../demo/hospitalInfo";
import { clock, mmss } from "../../demo/format";
import { useAlertTone, useCrew } from "./crew";

/* ---------- scaffolding ---------- */
function AScreen({ children, bottom, tabs }: { children: ReactNode; bottom?: ReactNode; tabs?: boolean }) {
  return (
    <div className="pscreen amb">
      <div className="pscroll">{children}</div>
      {(bottom || tabs) && (
        <div className="pbottom">
          {bottom}
          {tabs && (
            <nav className="tabbar tabbar-3" aria-label="Crew">
              {([["/crew", "home", "Duty"], ["/crew/history", "history", "History"], ["/crew/settings", "settings", "Settings"]] as const).map(([to, i, l]) => (
                <NavLink key={to} to={to} end className={({ isActive }) => (isActive ? "on" : "")}><Icon name={i} size={22} /><span>{l}</span></NavLink>
              ))}
            </nav>
          )}
        </div>
      )}
    </div>
  );
}

function ATop({ title, right }: { title: ReactNode; right?: ReactNode }) {
  return <header className="ptop atop"><div className="ptop-title"><h2>{title}</h2></div><div className="ptop-right">{right}</div></header>;
}

/* ---------- A1 · Login ---------- */
function Login({ onDone }: { onDone: () => void }) {
  const [id, setId] = useState("SP-1042");
  const [pw, setPw] = useState("");
  const [show, setShow] = useState(false);
  const [err, setErr] = useState("");
  const submit = () => (pw === "demo" && id.trim() ? onDone() : setErr("Wrong ID or password"));
  return (
    <AScreen>
      <div className="pad amb-login">
        <span className="logo-dot big" aria-hidden="true">+</span>
        <h1 className="ptitle">Crew log in</h1>
        <label className="lbl">Staff ID<input className="field" value={id} onChange={(e) => setId(e.target.value)} /></label>
        <label className="lbl">Password
          <span className="pw"><input className="field" type={show ? "text" : "password"} value={pw} onChange={(e) => { setPw(e.target.value); setErr(""); }} onKeyDown={(e) => e.key === "Enter" && submit()} />
            <button className="icon-btn sm" aria-label={show ? "Hide password" : "Show password"} onClick={() => setShow((v) => !v)}><Icon name="eye" size={18} /></button></span>
        </label>
        {err ? <p className="err-text">{err}</p> : <p className="help">Demo password: <b>demo</b></p>}
        <button className="btn2 btn2-dark btn2-full btn2-lg" onClick={submit}>Log in</button>
      </div>
    </AScreen>
  );
}

/* ---------- A2 · Vehicle check ---------- */
function VehicleCheck({ onDone }: { onDone: () => void }) {
  const [eq, setEq] = useState({ Ventilator: true, Defibrillator: true, Oxygen: true, "Spine board": true });
  return (
    <AScreen bottom={<div className="pad-x"><button className="btn2 btn2-dark btn2-full btn2-lg" onClick={onDone}>Continue</button></div>}>
      <ATop title="Vehicle check" />
      <div className="pad">
        <div className="card"><div className="amb-head"><span className="amb-reg big">MH14 AB 1234</span><AmbType type="ALS" /></div><p>Paramedic: Sanjay Patil</p></div>
        <div className="card">
          <p className="card-k">Equipment</p>
          {Object.entries(eq).map(([k, v]) => (
            <label key={k} className="switch-row"><span>{k}</span><input type="checkbox" className="switch" checked={v} onChange={(e) => setEq({ ...eq, [k]: e.target.checked })} /></label>
          ))}
        </div>
        <Banner type="success">Verified. You can go online.</Banner>
      </div>
    </AScreen>
  );
}

/* ---------- A3 · Duty ---------- */
function Duty() {
  const { s, d, now, actions } = useDemoActions();
  const toast = useToast();
  const [repo, setRepo] = useState(true);
  const status = !s.online ? "Offline" : d.ambulance === "cleaning" ? "Cleaning" : "Available";
  return (
    <AScreen tabs>
      <ATop title="Duty" right={<SignalBadge signal={s.signal} />} />
      <div className="pad amb-grid">
        <div className="amb-col">
          <div className="duty-top">
            <span className={`status-chip st-${status.toLowerCase()}`}>{status}</span>
            <span className="muted-s">MH14 AB 1234 · <AmbType type="ALS" /></span>
          </div>
          <button className={`btn2 btn2-hero ${s.online ? "btn2-light" : "btn2-green"} btn2-full`} onClick={() => { actions.setOnline(!s.online); try { navigator.vibrate?.(30); } catch { /* */ } }}>
            {s.online ? "GO OFFLINE" : "GO ONLINE"}
          </button>
          {s.online && repo && (
            <div className="card repo">
              <p><Icon name="pin" size={18} /> <b>Move to Nigdi Pradhikaran</b>, a busy area is expected in the next hour (4 min drive)</p>
              <div className="row-2"><button className="btn2 btn2-dark btn2-sm" onClick={() => { setRepo(false); toast("Heading to Nigdi Pradhikaran"); }}>Go</button><button className="btn2 btn2-light btn2-sm" onClick={() => setRepo(false)}>Not now</button></div>
            </div>
          )}
          <div className="stats3">
            <div><b>3</b><span>Jobs</span></div><div><b>5 h 12 m</b><span>Online</span></div><div><b>7 min</b><span>Avg response</span></div>
          </div>
        </div>
        <div className="amb-col"><DemoMap d={{ ...d, active: false }} now={now} dark variant="ambulance" height={300} showHospitals /></div>
      </div>
    </AScreen>
  );
}

/* ---------- A4 · Incoming request (full screen takeover) ---------- */
function Incoming({ sounds }: { sounds: boolean }) {
  const { d, now, actions } = useDemoActions();
  const toast = useToast();
  const [declineOpen, setDeclineOpen] = useState(false);
  const [declinedRound, setDeclinedRound] = useState<number | null>(null);
  const hidden = declinedRound === d.offerRound;
  useAlertTone(!hidden, sounds);
  if (hidden) return <Duty />;
  return (
    <div className="incoming">
      <div className="inc-head">
        <div><p className="inc-k">NEW EMERGENCY</p><h1><SeverityBadge level="critical" size="lg" /> <span className="inc-cat"><CategoryIcon c="cardiac" size={22} />HEART</span></h1></div>
        <CountdownRing secs={d.offerSecsLeft} total={20} size={74} dark />
      </div>
      <div className="inc-body">
        <p className="inc-big">Male · ~60 · 1 patient</p>
        <p className="inc-loc"><Icon name="pin" size={18} />Near Ganesh Temple, Sector 26, Akurdi <span className="muted-s nowrap">± 20 m</span></p>
        <p className="inc-dist">2.4 km · <b>6 min</b></p>
        <DemoMap d={{ ...d, accepted: d.offeredAt, leg: "patient", progress: 0 }} now={now} dark variant="ambulance" height={170} />
      </div>
      <div className="inc-actions">
        <button className="btn2 accept-hero" onClick={() => { try { navigator.vibrate?.(60); } catch { /* */ } actions.accept(); }}>ACCEPT</button>
        <button className="link-btn light" onClick={() => setDeclineOpen(true)}>Decline</button>
      </div>
      <ReasonDialog open={declineOpen} title="Decline this request?" reasons={REASONS.decline} confirmLabel="Decline"
        onClose={() => setDeclineOpen(false)}
        onConfirm={(r) => { setDeclineOpen(false); setDeclinedRound(d.offerRound); toast(`Declined: ${r}. Offered to others.`); }} />
    </div>
  );
}

/* ---------- A5 · Going to patient ---------- */
const TURNS = ["In 300 m, turn left onto Pradhikaran Road", "In 500 m, keep right at Bhakti Shakti Chowk", "In 200 m, turn right into Sector 26", "Destination on the left: Ganesh Temple"];

function PatientCard() {
  const { s, d } = useDemoActions();
  const answered = QUESTIONS.filter((q) => s.answers.some((a) => a.id === q.id));
  return (
    <div className="card">
      <div className="row-c left">
        <SeverityBadge level={s.confirm.severity} ai={d.confirmed === null} confirmed={d.confirmed !== null} />
        <span className="chip"><CategoryIcon c={s.confirm.category} size={15} />{CATEGORY_LABEL[s.confirm.category]}</span>
        {d.confirmed === null && <span className="muted-s">(AI) <Confidence value={0.91} /></span>}
      </div>
      <p className="fg-s">Male ~60 · Understood: chest pain, breathing difficulty, sweating</p>
      <AnimatePresence>
        {answered.map((q) => {
          const a = s.answers.find((x) => x.id === q.id)!;
          return (
            <motion.p key={q.id} className="answer" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
              <Icon name="check" size={14} stroke={2.6} />{QUESTION_SHORT[q.id]}: <b>{a.answer}</b> <span className="muted-s">{clock(a.at)}</span>
            </motion.p>
          );
        })}
      </AnimatePresence>
      <div className="profile-line">Blood <b>B+</b> · <span className="allergy-inline">Allergy: Aspirin</span> · Diabetes · Metformin</div>
    </div>
  );
}

function Going() {
  const { s, d, now, actions } = useDemoActions();
  const toast = useToast();
  const [vehicle, setVehicle] = useState(false);
  const turn = TURNS[Math.min(TURNS.length - 1, Math.floor(d.progress * TURNS.length))];
  return (
    <AScreen bottom={
      <div className="pad-x row-2">
        <button className="btn2 btn2-light" onClick={actions.arriveNow}>I've arrived</button>
        <button className="btn2 btn2-danger-o" onClick={() => setVehicle(true)}><Icon name="alert" size={18} />Vehicle issue</button>
      </div>
    }>
      <div className="amb-bar">
        <b>Going to patient</b>
        <span className="nowrap">ETA <Eta min={d.etaMin} lost={s.signal === "lost"} /> · {(2.4 * (1 - d.progress)).toFixed(1)} km</span>
        <SignalBadge signal={s.signal} />
      </div>
      <div className="pad amb-grid">
        <div className="amb-col">
          <DemoMap d={d} now={now} dark variant="ambulance" height={260} signal={s.signal} />
          <div className="turn"><Icon name={turn.includes("right") ? "turnRight" : "turnLeft"} size={26} className="turn-ico" /><b>{turn}</b></div>
        </div>
        <div className="amb-col">
          <div className="card caller">
            <span className="list-main"><b>Reported by: Rahul (son)</b><small>Near Ganesh Temple, Sector 26, Akurdi</small></span>
            <a className="btn2 btn2-dark btn2-sm" href="tel:+919800000321"><Icon name="phone" size={16} />Call caller</a>
          </div>
          <PatientCard />
        </div>
      </div>
      <Dialog open={vehicle} title="Report a vehicle issue?" onClose={() => setVehicle(false)}
        actions={<><button className="btn2 btn2-light" onClick={() => setVehicle(false)}>Cancel</button><button className="btn2 btn2-danger" onClick={() => { setVehicle(false); toast("Another ambulance will come to your location"); }}>Report</button></>}>
        The next nearest ambulance will be sent to the patient.
      </Dialog>
    </AScreen>
  );
}

/* ---------- A6 · At scene: confirm patient ---------- */
function Confirm() {
  const { s, actions } = useDemoActions();
  const toast = useToast();
  const [cat, setCat] = useState<Category>(s.confirm.category);
  const [sev, setSev] = useState<Severity>(s.confirm.severity);
  const [n, setN] = useState(1);
  const [refuse, setRefuse] = useState(false);
  const [note, setNote] = useState("");
  const changed = cat !== "cardiac" || sev !== "critical";
  return (
    <AScreen bottom={
      <div className="pad-x">
        <button className="btn2 btn2-green btn2-full btn2-hero" onClick={() => { try { navigator.vibrate?.(60); } catch { /* */ } actions.confirm(cat, sev, n, changed); }}>CONFIRM</button>
        <button className="link-btn center-block light" onClick={() => setRefuse(true)}>Patient refused to go</button>
      </div>
    }>
      <ATop title="Confirm patient condition" />
      <div className="pad">
        <div className="ai-sugg">AI thinks: <b>Heart · Critical</b> (91% sure)</div>
        {changed && <p className="changed">Changed from AI suggestion</p>}
        <div className="tiles">
          {CATEGORIES.map((c) => (
            <button key={c} className={`tile${cat === c ? " on" : ""}`} aria-pressed={cat === c} onClick={() => setCat(c)}>
              <CategoryIcon c={c} size={30} /><span>{CATEGORY_LABEL[c]}</span>
            </button>
          ))}
        </div>
        <div className="sev-row">
          {(["critical", "urgent", "stable"] as const).map((v) => (
            <button key={v} className={`sev-btn sev-btn-${v}${sev === v ? " on" : ""}`} aria-pressed={sev === v} onClick={() => setSev(v)}>{v[0].toUpperCase() + v.slice(1)}</button>
          ))}
        </div>
        <div className="counter-row">
          <span>Number of patients</span>
          <div className="stepper-n"><button aria-label="Fewer" onClick={() => setN((x) => Math.max(1, x - 1))}><Icon name="minus" /></button><b>{n}</b><button aria-label="More" onClick={() => setN((x) => x + 1)}><Icon name="plus" /></button></div>
        </div>
      </div>
      <Dialog open={refuse} title="Patient refused to go?" onClose={() => setRefuse(false)}
        actions={<><button className="btn2 btn2-light" onClick={() => setRefuse(false)}>Back</button><button className="btn2 btn2-danger" onClick={() => { setRefuse(false); actions.cancel("Patient refused transport"); toast("Job ended. Back to duty."); }}>End job</button></>}>
        <textarea className="field" rows={3} placeholder="Add a note (what was said, who was present)" value={note} onChange={(e) => setNote(e.target.value)} />
      </Dialog>
    </AScreen>
  );
}

/* ---------- A7 · Transporting ---------- */
function Transporting() {
  const nav = useNavigate();
  const { s, d, now, actions } = useDemoActions();
  const toast = useToast();
  const [checking, setChecking] = useState<null | "checking" | "done">(null);
  const [vehicle, setVehicle] = useState(false);
  const info = hospitalInfo(d.hospitalId, s.room);
  const waiting = d.stage === "asking" || d.stage === "choosing";
  const offline = s.signal === "lost";

  useEffect(() => {
    if (checking !== "checking") return;
    const t = setTimeout(() => setChecking("done"), 2200);
    return () => clearTimeout(t);
  }, [checking]);

  return (
    <AScreen bottom={
      <div className="pad-x">
        <button className="btn2 btn2-red btn2-full btn2-hero" onClick={() => { actions.worsened(); setChecking("checking"); }}>PATIENT GOT WORSE</button>
        <div className="row-2">
          <button className="btn2 btn2-light btn2-sm" onClick={() => nav("/crew/family-choice")}>Family wants another hospital</button>
          <button className="btn2 btn2-danger-o btn2-sm" onClick={() => setVehicle(true)}><Icon name="alert" size={16} />Vehicle issue</button>
        </div>
      </div>
    }>
      <div className="amb-bar">
        <b>To hospital</b>
        <span>{waiting ? "ETA 11 min (9 to 14 min)" : <>ETA <Eta min={d.etaMin} lost={offline} /></>}</span>
        <SignalBadge signal={s.signal} />
      </div>
      <div className="pad amb-grid">
        <div className="amb-col">
          {offline && <Banner type="offline" action={<a className="banner-act" href={`sms:+919800000999?body=${encodeURIComponent("GH 4821 ONBOARD")}`}>Send by SMS</a>}>No internet, 2 actions waiting to send</Banner>}
          {d.reroute && !waiting && <Banner type="warning">New destination: {info.h.name}, {d.reroute.reason}</Banner>}
          {checking === "checking" && <Banner type="info">Checking for a closer hospital…</Banner>}
          {checking === "done" && <Banner type="success">Continue: current hospital is best</Banner>}
          <DemoMap d={d} now={now} dark variant="ambulance" height={240} severity={s.confirm.severity} signal={s.signal} />
        </div>
        <div className="amb-col">
          <div className="card dest">
            {d.stage === "choosing" ? <p className="loading-line"><span className="spin" />Finding the best hospital…</p> : (
              <>
                <h3 className="h-name">{info.h.name}</h3>
                {waiting ? (
                  <p className="loading-line"><span className="spin" />Waiting for hospital ({mmss(45 - d.hospitalSecsLeft)})</p>
                ) : (
                  <>
                    <p className="ok-text"><Icon name="check" size={16} stroke={2.6} />Accepted</p>
                    <div className="kv">
                      <div><span>Room</span><b>{info.room}</b></div>
                      <div><span>Gate</span><b>{info.gate}</b></div>
                      <div><span>Team</span><b>{info.doctor}</b></div>
                    </div>
                    <a className="btn2 btn2-light btn2-sm" href={`tel:${info.er}`}><Icon name="phone" size={16} />Call ER</a>
                  </>
                )}
                <WhyChips items={info.why} />
              </>
            )}
          </div>
          <PatientCard />
        </div>
      </div>
      <Dialog open={vehicle} title="Report a vehicle issue?" onClose={() => setVehicle(false)}
        actions={<><button className="btn2 btn2-light" onClick={() => setVehicle(false)}>Cancel</button><button className="btn2 btn2-danger" onClick={() => { setVehicle(false); toast("Another ambulance will come to your location"); }}>Report</button></>}>
        A second ambulance will meet you. The hospital bed stays held.
      </Dialog>
    </AScreen>
  );
}

/* ---------- A8 · Family wants another hospital ---------- */
function FamilyChoice() {
  const nav = useNavigate();
  const toast = useToast();
  const { d, actions } = useDemoActions();
  const [pick, setPick] = useState<string>("");
  const [consent, setConsent] = useState(false);
  const [who, setWho] = useState("");
  const others = [
    { id: "riverside", eta: "+3 min", chips: ["No cath lab"] },
    { id: "hillview", eta: "+14 min", chips: ["No cath lab", "Data 40 min old"] },
    { id: "lotus", eta: "+9 min", chips: ["No cath lab", "Bumpy road"] },
  ];
  const ok = pick && consent && who.trim();
  return (
    <AScreen bottom={
      <div className="pad-x row-2">
        <button className="btn2 btn2-light" onClick={() => nav("/crew")}>Keep recommended</button>
        <button className="btn2 btn2-dark" disabled={!ok} onClick={() => { actions.familyChoice(pick, who.trim()); toast("Asking the family's hospital"); nav("/crew"); }}>Go to selected hospital</button>
      </div>
    }>
      <ATop title="Family wants a different hospital" />
      <div className="pad">
        <div className="card current">
          <span className="tag-soft ok">Recommended</span>
          <h3 className="h-name">{hospitalInfo(d.hospitalId).h.name}</h3>
          <p className="muted-s">11 min · Cath lab ✓</p>
        </div>
        <div className="list">
          {others.map((o) => (
            <button key={o.id} className={`list-row pickable${pick === o.id ? " on" : ""}`} onClick={() => setPick(o.id)}>
              <span className="radio-dot" />
              <span className="list-main"><b>{HOSPITALS.find((h) => h.id === o.id)!.name}</b>
                <WhyChips negative items={[{ icon: "alert", text: o.eta }, ...o.chips.map((c) => ({ icon: "alert", text: c }))]} />
              </span>
            </button>
          ))}
        </div>
        <label className="check-row"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />Family understands the trade-off and agrees</label>
        <label className="lbl">Family member name<input className="field" value={who} onChange={(e) => setWho(e.target.value)} placeholder="e.g. Sunita Kulkarni" /></label>
      </div>
    </AScreen>
  );
}

/* ---------- A9 · At hospital ---------- */
function AtHospital() {
  const { s, d, actions } = useDemoActions();
  const info = hospitalInfo(d.hospitalId, s.room);
  const received = d.stage === "handedOver";
  const late = d.doorSecs >= 15 * 60;
  return (
    <AScreen bottom={received && d.ambulance === "cleaning" ? (
      <div className="pad-x"><button className="btn2 btn2-green btn2-full btn2-hero" onClick={actions.ready}>READY FOR NEXT CALL</button></div>
    ) : undefined}>
      <div className="amb-bar"><b>{received ? "Cleaning" : "At hospital"}</b><SignalBadge signal={s.signal} /></div>
      <div className="pad">
        <div className={`door${late ? " late" : ""}`}>
          <span>Waiting at door</span>
          <b>{mmss(d.doorSecs)}</b>
        </div>
        <div className="card">
          <h3 className="h-name">{info.h.name}</h3>
          <div className="kv"><div><span>Room</span><b>{info.room}</b></div><div><span>Gate</span><b>{info.gate}</b></div><div><span>Receiving</span><b>{info.team}</b></div></div>
        </div>
        {received ? (
          <Banner type="success">Patient received by {info.doctor} at {clock(d.received)}</Banner>
        ) : (
          <p className="loading-line"><span className="spin" />Waiting for the hospital to tap Patient received</p>
        )}
      </div>
    </AScreen>
  );
}

/* ---------- A10 · History ---------- */
function History() {
  const { s, d } = useDemoActions();
  return (
    <AScreen tabs>
      <ATop title="History" />
      <div className="pad">
        <div className="list">
          {d.received && (
            <div className="list-row"><span className="cat-dot"><CategoryIcon c={s.confirm.category} size={18} /></span><span className="list-main"><b>{clock(s.sosAt)} · Heart · Akurdi</b><small>{hospitalInfo(d.hospitalId).h.name} · total {Math.round(((d.received ?? 0) - (s.sosAt ?? 0)) / 1000)} s (demo)</small></span></div>
          )}
          <div className="list-row"><span className="cat-dot"><CategoryIcon c="trauma" size={18} /></span><span className="list-main"><b>6:12 PM · Accident · Wakad</b><small>Hillview Medical College Hospital · 31 min</small></span></div>
          <div className="list-row"><span className="cat-dot"><CategoryIcon c="respiratory" size={18} /></span><span className="list-main"><b>2:40 PM · Breathing · Nigdi</b><small>Greenfield Heart Centre · 24 min</small></span></div>
        </div>
      </div>
    </AScreen>
  );
}

/* ---------- A11 · Settings ---------- */
function Settings({ crew }: { crew: ReturnType<typeof useCrew> }) {
  const { d } = useDemoActions();
  const toast = useToast();
  const onJob = d.active && d.ambulance !== "available" && d.ambulance !== "offline" && d.ambulance !== "incoming";
  return (
    <AScreen tabs>
      <ATop title="Settings" />
      <div className="pad">
        <div className="card">
          <p className="card-k">Dark mode</p>
          <div className="seg3">
            {(["auto", "on", "off"] as const).map((v) => <button key={v} aria-pressed={crew.prefs.dark === v} onClick={() => crew.set({ dark: v })}>{v === "auto" ? "Auto (night)" : v === "on" ? "On" : "Off"}</button>)}
          </div>
        </div>
        <div className="card">
          <label className="switch-row"><span>Sounds for non-critical alerts<small>New request alerts always ring while on duty</small></span><input type="checkbox" className="switch" checked={crew.prefs.sounds} onChange={(e) => crew.set({ sounds: e.target.checked })} /></label>
          <label className="switch-row"><span>Landscape (phone on dashboard)</span><input type="checkbox" className="switch" checked={crew.prefs.landscape} onChange={(e) => crew.set({ landscape: e.target.checked })} /></label>
        </div>
        <div className="card"><p className="card-k">Language</p><p className="muted-s">English. More languages come with the app translation pass.</p></div>
        <button className="btn2 btn2-light btn2-full" disabled={onJob} onClick={() => { crew.set({ loggedIn: false, checked: false }); toast("Logged out"); }}>
          {onJob ? "Finish the current job first" : "Log out"}
        </button>
      </div>
    </AScreen>
  );
}

/* ---------- Duty router: the job screens take over based on the live emergency ---------- */
function DutyRouter({ sounds }: { sounds: boolean }) {
  const { s, d } = useDemoActions();
  if (!s.online && d.ambulance !== "going" && d.ambulance !== "atScene" && d.ambulance !== "transporting" && d.ambulance !== "atHospital") return <Duty />;
  switch (d.ambulance) {
    case "incoming": return <Incoming sounds={sounds} />;
    case "going": return <Going />;
    case "atScene": return <Confirm />;
    case "transporting": return <Transporting />;
    case "atHospital": return <AtHospital />;
    case "cleaning": return <AtHospital />;
    default: return <Duty />;
  }
}

export default function AmbulanceApp() {
  const crew = useCrew();
  const { prefs, set, isDark } = crew;
  let body: ReactNode;
  if (!prefs.loggedIn) body = <Login onDone={() => set({ loggedIn: true })} />;
  else if (!prefs.checked) body = <VehicleCheck onDone={() => set({ checked: true })} />;
  else body = (
    <Routes>
      <Route index element={<DutyRouter sounds={prefs.sounds} />} />
      <Route path="family-choice" element={<FamilyChoice />} />
      <Route path="history" element={<History />} />
      <Route path="settings" element={<Settings crew={crew} />} />
      <Route path="*" element={<Navigate to="/crew" replace />} />
    </Routes>
  );
  return <PhoneShell title="Ambulance app" dark={isDark} landscape={prefs.landscape}>{body}</PhoneShell>;
}

