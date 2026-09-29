import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Icon from "../../ui/Icon";
import { Banner, SeverityBadge, SimTag } from "../../ui/Bits";
import DemoMap from "../../ui/DemoMap";
import { useToast } from "../../ui/toast";
import { ChartCard, HBars, Heatmap, StatTile } from "../../ui/charts";
import { AMBULANCES, CASE_ID, HOSPITALS } from "../../demo/data";
import { useDemoActions } from "../../demo/actions";
import { clock, mmss } from "../../demo/format";
import DemoBar from "../shell/DemoBar";

type Tab = "incident" | "analytics" | "scenarios";

/* ---------- O1 · Incident (scripted escalation: every hospital full) ---------- */
const OPTIONS = [
  { id: "stabilise", label: "Stabilise at Unity Community Hospital, transfer later", def: true },
  { id: "partial", label: "Best partial match: Hillview (no cath lab)" },
  { id: "force", label: "Force Greenfield" },
  { id: "widen", label: "Search up to 40 km" },
];

function Incident() {
  const toast = useToast();
  const { d, now } = useDemoActions();
  const [opened] = useState(() => Date.now() - 60000);
  const [claimed, setClaimed] = useState(false);
  const [picked, setPicked] = useState<null | { by: string; label: string; at: number }>(null);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [ovHospital, setOvHospital] = useState("hillview");
  const [ovReason, setOvReason] = useState("");
  const autoAt = opened + 120000;
  const secsLeft = Math.max(0, Math.ceil((autoAt - now) / 1000));

  // Nobody chose in 2 minutes: the safe default runs by itself.
  const resolved = picked ?? (secsLeft === 0 ? { by: "system", label: OPTIONS[0].label, at: autoAt } : null);

  const pick = (label: string) => { setClaimed(true); setPicked({ by: "you", label, at: now }); toast("Resolved"); };
  const timeline: [number, string][] = [
    [opened - 180000, "Paramedic confirmed Heart · Critical"],
    [opened - 170000, "Greenfield Heart Centre asked"],
    [opened - 150000, "Greenfield rejected: no bed"],
    [opened - 148000, "Riverside Multispeciality asked"],
    [opened - 103000, "Riverside: no response in 45 s"],
    [opened - 100000, "Metro Neuro & Stroke Centre asked"],
    [opened - 70000, "Metro Neuro rejected: not equipped for this case"],
    [opened, "Escalated to on call team (Telegram)"],
  ];
  if (claimed) timeline.push([opened + 5000, "Claimed by you"]);
  if (resolved) timeline.push([resolved.at, resolved.by === "system" ? `Auto-executed default: ${resolved.label}` : `Resolved by you: ${resolved.label}`]);

  return (
    <div className="ops-body">
      <p className="help small">Scripted scenario "All hospitals full". Live cases from the demo appear under Analytics.</p>
      <div className="ops-head">
        <span className="esc-badge">NO HOSPITAL ACCEPTING</span>
        <span>Case #{CASE_ID}</span>
        <span className="muted-s">Opened {Math.max(1, Math.round((now - opened) / 60000))} min ago</span>
      </div>

      {resolved ? (
        <Banner type="success">{resolved.by === "system" ? "Auto-executed default" : "Resolved by you"}: {resolved.label}</Banner>
      ) : claimed ? (
        <Banner type="info">Claimed by you. Others see "Claimed by you".</Banner>
      ) : (
        <button className="btn2 btn2-dark btn2-full btn2-lg" onClick={() => { setClaimed(true); toast("Claimed by you"); }}>I'm handling this</button>
      )}

      <div className="card">
        <p className="card-k">Summary</p>
        <p className="fg-s">Critical heart patient in MH14 AB 1234. Greenfield rejected (no bed), Riverside no response, Metro Neuro rejected (not equipped).</p>
        <div className="row-c left"><SeverityBadge level="critical" /><span className="chip">Heart</span></div>
      </div>

      <DemoMap d={{ ...d, active: true, accepted: 1, leg: "patient", progress: 1, stage: "asking", hospitalAcceptedAt: null }} now={now} variant="ops" height={420} showHospitals />

      {!resolved && (
        <div className="card">
          <p className="card-k">Options</p>
          <div className="stack">
            {OPTIONS.map((o) => (
              <button key={o.id} className={`opt${o.def ? " def" : ""}`} onClick={() => pick(o.label)}>
                {o.def && <Icon name="star" size={16} />}
                <span>{o.label}</span>
                {o.def && <em>Auto in {mmss(secsLeft)}</em>}
              </button>
            ))}
            <button className="link-btn" onClick={() => setOverrideOpen((v) => !v)}>Manual override</button>
          </div>
          <AnimatePresence>
            {overrideOpen && (
              <motion.div className="form" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} style={{ overflow: "hidden", display: "flex", flexDirection: "column", gap: 10 }}>
                <label className="lbl">Hospital<select className="field" value={ovHospital} onChange={(e) => setOvHospital(e.target.value)}>{HOSPITALS.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}</select></label>
                <label className="lbl">Reason (required)<input className="field" value={ovReason} onChange={(e) => setOvReason(e.target.value)} placeholder="Why this hospital" /></label>
                <button className="btn2 btn2-dark" disabled={!ovReason.trim()} onClick={() => pick(`Force ${HOSPITALS.find((h) => h.id === ovHospital)!.name} (${ovReason.trim()})`)}>Assign</button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      <div className="card">
        <p className="card-k">Timeline</p>
        <ul className="timeline">{timeline.map(([t, text]) => <li key={text}><span>{text}</span><b>{clock(t)}</b></li>)}</ul>
      </div>
    </div>
  );
}

/* ---------- O2 · Analytics ---------- */
function Analytics() {
  const { d } = useDemoActions();
  const busy = AMBULANCES.filter((a) => a.status === "On job").length;
  const zones = ["Nigdi", "Akurdi", "Chinchwad", "Pimpri", "Bhosari", "Wakad", "Ravet"];
  const hours = ["Now", "+1 h", "+2 h", "+3 h", "+4 h", "+5 h"];
  const predicted = [[3, 4, 5, 4, 3, 2], [4, 5, 6, 5, 3, 2], [2, 3, 5, 6, 4, 3], [5, 6, 7, 6, 5, 3], [1, 2, 3, 3, 2, 1], [3, 4, 4, 5, 6, 4], [1, 1, 2, 2, 2, 1]];
  const actual = [[3, 5, 0, 0, 0, 0], [4, 4, 0, 0, 0, 0], [3, 3, 0, 0, 0, 0], [6, 6, 0, 0, 0, 0], [1, 2, 0, 0, 0, 0], [2, 5, 0, 0, 0, 0], [1, 2, 0, 0, 0, 0]].map((r) => r.slice(0, 2));
  return (
    <div className="ops-body">
      <div className="kpis">
        <StatTile label="Active emergencies" value={String(d.active ? 1 : 0)} sub="live demo case" />
        <StatTile label="Ambulances" value={`${AMBULANCES.filter((a) => a.status === "Available").length} free`} sub={`${busy} busy · 1 cleaning`} />
        <StatTile label="Hospitals" value="6 fresh" sub="2 stale" tone="warn" />
        <StatTile label="Response time" value="7 min" sub="median · 90th percentile 12 min" />
        <StatTile label="Door wait" value="11 min" sub="median across hospitals" />
        <StatTile label="AI triage accuracy" value="91%" sub="agrees with paramedic" tone="good" />
        <StatTile label="Escalations" value="3" sub="today · 1 auto default" />
      </div>
      <div className="charts">
        <ChartCard title="Rejections by hospital" note="Last 7 days" table={{ head: ["Hospital", "Rejections"], rows: [["Greenfield", 7], ["Metro Neuro", 5], ["Riverside", 4], ["Hillview", 2], ["Northgate", 1]] }}>
          <HBars data={[{ label: "Greenfield", value: 7 }, { label: "Metro Neuro", value: 5 }, { label: "Riverside", value: 4 }, { label: "Hillview", value: 2 }, { label: "Northgate", value: 1 }]} />
        </ChartCard>
        <ChartCard title="Rejections by reason" note="Last 7 days" table={{ head: ["Reason", "Count"], rows: [["No bed", 9], ["No specialist", 5], ["Over capacity", 3], ["Equipment down", 2]] }}>
          <HBars data={[{ label: "No bed", value: 9 }, { label: "No specialist", value: 5 }, { label: "Over capacity", value: 3 }, { label: "Equipment down", value: 2 }]} />
        </ChartCard>
        <ChartCard title="Demand: predicted calls per zone" note="Next 6 hours" table={{ head: ["Zone", ...hours], rows: zones.map((z, i) => [z, ...predicted[i]]) }}>
          <Heatmap rows={zones} cols={hours} values={predicted} unit="calls" />
        </ChartCard>
        <ChartCard title="Demand: actual calls per zone" note="So far" table={{ head: ["Zone", "Now", "+1 h"], rows: zones.map((z, i) => [z, ...actual[i]]) }}>
          <Heatmap rows={zones} cols={hours.slice(0, 2)} values={actual} unit="calls" />
        </ChartCard>
      </div>
    </div>
  );
}

/* ---------- O3 · Scenarios ---------- */
const SCENARIOS: [string, string][] = [
  ["Normal heart emergency", "Voice SOS to handover, start to finish"],
  ["Nearest hospital lacks cath lab", "Rerouted to the right one"],
  ["Stale hospital data", "Old numbers flagged, AI estimate used"],
  ["Double booking", "Two ambulances, one last bed: one wins"],
  ["Two drivers accept at once", "Only one gets it"],
  ["Walk-in takes reserved bed", "Automatic re-allocation"],
  ["Hospital rejects / no response", "Automatic fallback in 45 s"],
  ["All hospitals full", "Team alerted, safe default at 2 min"],
  ["Ambulance loses network", "Bed held, taps queued, SMS fallback"],
  ["Patient worsens", "Diversion only if 3+ min faster"],
  ["Wrong AI triage", "Paramedic corrects, AI learns"],
  ["Duplicate calls", "Five calls, one incident"],
  ["Prank call", "Verified, never blocked"],
  ["Mass casualty", "Patients spread by capacity"],
  ["No ambulance accepts", "Radius widens, then escalation"],
  ["Ambulance breakdown", "Next ambulance to the breakdown point"],
  ["Family chooses another hospital", "Trade-off shown, consent recorded"],
  ["SMS from basic phone", "Full flow over SMS"],
  ["Unknown patient", "Temporary ID, linked later"],
  ["Driver idle / wrong direction", "Alert, then reassignment"],
];
const CHECKS = ["World reset", "Emergency created", "Offers sent", "State checks pass", "No double bookings", "Timeline recorded"];

function Scenarios() {
  const { actions } = useDemoActions();
  const toast = useToast();
  const [speed, setSpeed] = useState(1);
  const [running, setRunning] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [results, setResults] = useState<Record<string, boolean>>({ "Normal heart emergency": true, "Double booking": true });

  useEffect(() => {
    if (!running) return;
    const t = setTimeout(() => {
      if (step + 1 >= CHECKS.length) {
        setResults((r) => ({ ...r, [running]: true }));
        setRunning(null);
      } else setStep((s) => s + 1);
    }, 700 / speed);
    return () => clearTimeout(t);
  }, [running, step, speed]);

  const run = (name: string) => {
    if (name === "Normal heart emergency") {
      actions.reset();
      setTimeout(() => { actions.setAutoplay(true); actions.sos("papa", "voice"); }, 50);
      toast("Running live: open the Patient, Ambulance and Hospital apps to watch");
    }
    setRunning(name);
    setStep(0);
  };

  return (
    <div className="ops-body">
      <div className="ops-controls">
        <div className="seg3" role="group" aria-label="Speed">{[1, 2, 5, 10].map((x) => <button key={x} aria-pressed={speed === x} onClick={() => setSpeed(x)}>{x}×</button>)}</div>
        <button className="btn2 btn2-light btn2-sm" onClick={() => { actions.reset(); setResults({}); toast("World reset"); }}>Reset world</button>
      </div>
      <p className="help small">"Normal heart emergency" drives the real live demo. The others preview the runner's checks; the real runner plays them against the simulator.</p>
      <div className="list">
        {SCENARIOS.map(([name, desc]) => (
          <div key={name} className="list-row">
            <span className={`res-dot ${results[name] ? "ok" : ""}`}>{results[name] ? <Icon name="check" size={14} stroke={2.8} /> : null}</span>
            <span className="list-main"><b>{name}</b><small>{desc}</small></span>
            <button className="btn2 btn2-dark btn2-sm" disabled={running !== null} onClick={() => run(name)}>{running === name ? "Running…" : "Run"}</button>
          </div>
        ))}
      </div>
      {running && (
        <div className="card">
          <p className="card-k">{running}</p>
          <ul className="checks">{CHECKS.map((c, i) => <li key={c} className={i < step ? "done" : i === step ? "now" : ""}>{i < step ? <Icon name="check" size={14} stroke={2.8} /> : <span className="spin sm" />}{c}</li>)}</ul>
        </div>
      )}
    </div>
  );
}

export default function OpsApp() {
  const [tab, setTab] = useState<Tab>("incident");
  return (
    <div className="ops">
      <header className="ops-top">
        <a href="#/" className="pshell-brand"><span className="logo-dot" aria-hidden="true">+</span>GoldenHour</a>
        <span className="muted-s">Ops · opened from Telegram</span>
        <SimTag />
      </header>
      <nav className="ops-tabs" role="tablist">
        {([["incident", "Incident"], ["analytics", "Analytics"], ["scenarios", "Scenarios"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>
        ))}
      </nav>
      {tab === "incident" && <Incident />}
      {tab === "analytics" && <Analytics />}
      {tab === "scenarios" && <Scenarios />}
      <div className="demobar-fixed"><DemoBar /></div>
    </div>
  );
}
