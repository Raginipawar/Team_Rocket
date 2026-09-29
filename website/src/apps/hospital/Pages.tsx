import { useState } from "react";
import Icon, { CategoryIcon } from "../../ui/Icon";
import { Empty, Freshness, RoomChip, SeverityBadge, SimTag, type RoomStatus } from "../../ui/Bits";
import { Dialog, ReasonDialog } from "../../ui/Dialog";
import { useToast } from "../../ui/toast";
import { CASE_ID, QUESTIONS, REASONS, TEAM } from "../../demo/data";
import { useDemoActions } from "../../demo/actions";
import { useDemo, useNow } from "../../demo/store";
import { clock } from "../../demo/format";
import { useLiveRooms, type Room } from "./shared";
import { Sbar } from "./Dashboard";

const MIN = 60000;

/* ---------- H3 · Rooms board ---------- */
export function Rooms({ rooms, setRooms }: { rooms: Room[]; setRooms: (r: Room[]) => void }) {
  const toast = useToast();
  const { update, s } = useDemo();
  const { d, now } = useDemoActions();
  const live = useLiveRooms(rooms);
  const [type, setType] = useState("All");
  const [status, setStatus] = useState("All");
  const [editing, setEditing] = useState<string | null>(null);
  const [override, setOverride] = useState<string | null>(null);
  const types = ["All", "ER", "Resus", "Trauma", "ICU", "Labour", "Burns", "Pediatric ER"];
  const statuses = ["All", "free", "reserved", "occupied", "cleaning", "out"];
  const shown = live.filter((r) => (type === "All" || r.type === type) && (status === "All" || r.status === status));

  const setStatusOf = (code: string, st: RoomStatus) => {
    setRooms(rooms.map((r) => (r.code === code ? { ...r, status: st, since: Date.now() } : r)));
    toast("Saved");
  };
  const doOverride = (code: string, reason: string) => {
    const alt = rooms.find((r) => r.status === "free" && r.code !== code && (r.type === "ER" || r.type === "Resus"));
    setRooms(rooms.map((r) => (r.code === code ? { ...r, status: "occupied", since: Date.now() } : r)));
    if (alt) {
      update({ room: alt.code });
      toast(`Override (${reason.toLowerCase()}). Reservation moved to ${alt.code}`);
    } else {
      toast("No free room. Ambulance redirected to Riverside Multispeciality");
    }
    setOverride(null);
  };

  return (
    <div className="h-page">
      <div className="h-filters">
        <div className="chips-wrap">{types.map((t) => <button key={t} className={`pick${type === t ? " on" : ""}`} onClick={() => setType(t)}>{t}</button>)}</div>
        <div className="chips-wrap">{statuses.map((t) => <button key={t} className={`pick${status === t ? " on" : ""}`} onClick={() => setStatus(t)}>{t === "out" ? "Out of service" : t === "All" ? "All statuses" : t[0].toUpperCase() + t.slice(1)}</button>)}</div>
      </div>
      <div className="room-grid">
        {shown.map((r) => (
          <button key={r.code} className={`room-tile rt-${r.status}`} onClick={() => (r.status === "reserved" ? setOverride(r.code) : setEditing(r.code))}>
            <b>{r.code}</b>
            <span className="muted-s">{r.loc}</span>
            <RoomChip status={r.status} />
            {r.detail && <span className="room-detail">{r.detail}</span>}
            <span className="muted-s small">for {Math.max(0, Math.round((now - r.since) / MIN))} min</span>
          </button>
        ))}
      </div>
      {d.hospitalId === "greenfield" && d.hospitalAcceptedAt === null && d.stage === "asking" && <p className="help">Accepting the pending request will reserve {s.room}.</p>}

      <Dialog open={editing !== null} title={`Change ${editing}`} onClose={() => setEditing(null)} actions={<button className="btn2 btn2-light" onClick={() => setEditing(null)}>Close</button>}>
        <div className="radio-list">
          {(["free", "occupied", "cleaning", "out"] as RoomStatus[]).map((st) => (
            <button key={st} className="radio" onClick={() => { setStatusOf(editing!, st); setEditing(null); }}>
              <RoomChip status={st} />
            </button>
          ))}
        </div>
      </Dialog>
      <ReasonDialog
        open={override !== null}
        title={`This room is reserved for an incoming critical patient (${d.etaMin || 6} min).`}
        reasons={REASONS.roomOverride} confirmLabel="Override" danger
        onClose={() => setOverride(null)}
        onConfirm={(r) => doOverride(override!, r)}
      />
    </div>
  );
}

/* ---------- H4 · Resources ---------- */
interface Res { name: string; total: number; avail: number; reserved: number; updated: number }
export function Resources() {
  const toast = useToast();
  const now = useNow(30000);
  const [rows, setRows] = useState<Res[]>(() => [
    { name: "Ventilators", total: 8, avail: 3, reserved: 0, updated: now - 45 * MIN },
    { name: "Cath lab", total: 1, avail: 1, reserved: 0, updated: now - 2 * MIN },
    { name: "CT scanner", total: 2, avail: 1, reserved: 0, updated: now - 9 * MIN },
    { name: "MRI", total: 1, avail: 1, reserved: 0, updated: now - 26 * MIN },
    { name: "Defibrillators", total: 6, avail: 5, reserved: 1, updated: now - 4 * MIN },
    { name: "Blood O-", total: 10, avail: 4, reserved: 0, updated: now - 12 * MIN },
    { name: "Blood O+", total: 20, avail: 12, reserved: 0, updated: now - 12 * MIN },
    { name: "Blood A+", total: 16, avail: 9, reserved: 0, updated: now - 12 * MIN },
    { name: "Blood B+", total: 14, avail: 6, reserved: 2, updated: now - 12 * MIN },
    { name: "Blood AB+", total: 6, avail: 2, reserved: 0, updated: now - 12 * MIN },
    { name: "Dialysis", total: 4, avail: 2, reserved: 0, updated: now - 35 * MIN },
    { name: "Operating theatres", total: 5, avail: 1, reserved: 0, updated: now - 7 * MIN },
  ]);
  const change = (i: number, delta: number) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, avail: Math.min(r.total - r.reserved, Math.max(0, r.avail + delta)) } : r)));
  const save = (i: number) => { setRows((rs) => rs.map((r, j) => (j === i ? { ...r, updated: Date.now() } : r))); toast("Saved"); };
  return (
    <div className="h-page">
      <div className="h-page-head">
        <p className="help">Every number shows how old it is. Old numbers are trusted less when choosing hospitals.</p>
        <button className="btn2 btn2-dark" onClick={() => { setRows((rs) => rs.map((r) => ({ ...r, updated: Date.now() }))); toast("All numbers confirmed as current"); }}>Confirm all numbers are current</button>
      </div>
      <table className="h-table">
        <thead><tr><th>Resource</th><th>Total</th><th>Available</th><th>Reserved</th><th>Last updated</th><th /></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.name}>
              <td><b>{r.name}</b></td>
              <td>{r.total}</td>
              <td><span className="pm"><button aria-label={`Fewer ${r.name}`} onClick={() => change(i, -1)}><Icon name="minus" size={14} /></button><b>{r.avail}</b><button aria-label={`More ${r.name}`} onClick={() => change(i, 1)}><Icon name="plus" size={14} /></button></span></td>
              <td>{r.reserved}</td>
              <td><Freshness minutes={Math.floor((now - r.updated) / MIN)} /></td>
              <td><button className="btn2 btn2-light btn2-sm" onClick={() => save(i)}>Save</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- H5 · Staff & shifts ---------- */
const STAFF = [
  { name: "Dr. A. Kulkarni", role: "Cardiologist", start: 20, end: 32 },
  { name: "Dr. R. Shah", role: "Emergency physician", start: 18, end: 30 },
  { name: "Dr. N. Iyer", role: "Emergency physician", start: 8, end: 20 },
  { name: "Dr. K. Desai", role: "Trauma surgeon", start: 8, end: 26 },
  { name: "Nurse P. Joshi", role: "Nurse", start: 20, end: 32 },
  { name: "Nurse S. Kale", role: "Nurse", start: 20, end: 32 },
  { name: "Nurse A. Mane", role: "Nurse", start: 14, end: 26 },
];
export function Staff() {
  const toast = useToast();
  const [add, setAdd] = useState(false);
  const hour = new Date().getHours();
  const onDuty = (s: (typeof STAFF)[number]) => (hour >= s.start && hour < s.end) || (hour + 24 >= s.start && hour + 24 < s.end);
  const groups = ["Cardiologist", "Emergency physician", "Trauma surgeon", "Nurse"].map((g) => ({ g, n: STAFF.filter((s) => s.role === g && onDuty(s)).length }));
  return (
    <div className="h-page">
      <div className="duty-cards">
        {groups.map(({ g, n }) => <div key={g} className={`duty-card${n === 0 ? " warn" : ""}`}><b>{n}{n === 0 && <Icon name="alert" size={16} stroke={2.2} />}</b><span>{g}{n === 1 ? "" : "s"}</span></div>)}
      </div>
      <div className="banner banner-warning"><Icon name="alert" size={18} /><span className="banner-text">No trauma surgeon between 2 AM and 8 AM</span></div>
      <div className="shift-chart">
        <div className="shift-axis"><span />{Array.from({ length: 13 }, (_, i) => <span key={i}>{String((8 + i * 2) % 24).padStart(2, "0")}:00</span>)}</div>
        {STAFF.map((s) => (
          <div key={s.name} className="shift-row">
            <span className="shift-name"><b>{s.name}</b><small>{s.role}</small></span>
            <span className="shift-track">
              <i style={{ left: `${((s.start - 8) / 24) * 100}%`, width: `${((s.end - s.start) / 24) * 100}%` }} className={onDuty(s) ? "on" : ""} />
              <em className="now-line" style={{ left: `${(((hour < 8 ? hour + 24 : hour) - 8) / 24) * 100}%` }} />
            </span>
          </div>
        ))}
      </div>
      <div className="row-c left">
        <button className="btn2 btn2-dark" onClick={() => setAdd(true)}><Icon name="plus" size={18} />Add shift</button>
      </div>
      <Dialog open={add} title="Add shift" onClose={() => setAdd(false)}
        actions={<><button className="btn2 btn2-light" onClick={() => setAdd(false)}>Cancel</button><button className="btn2 btn2-dark" onClick={() => { setAdd(false); toast("Saved"); }}>Save</button></>}>
        <label className="lbl">Staff<select className="field">{STAFF.map((s) => <option key={s.name}>{s.name}</option>)}</select></label>
        <div className="row-2"><label className="lbl">Start<input className="field" type="time" defaultValue="02:00" /></label><label className="lbl">End<input className="field" type="time" defaultValue="08:00" /></label></div>
      </Dialog>
    </div>
  );
}

/* ---------- H6 · Patient detail ---------- */
export function PatientDetail() {
  const { s, d, now } = useDemoActions();
  const toast = useToast();
  const [room, setRoom] = useState(s.room);
  const mine = d.hospitalId === "greenfield" && d.confirmed !== null;
  if (!mine) return <div className="h-page"><Empty icon="user" text="No incoming patient selected." /></div>;
  const status = d.stage === "asking" ? "Request pending" : d.stage === "transporting" ? `Incoming · ${d.etaMin} min` : d.stage === "atDoor" ? "At the door" : "Received";
  const timeline: [string, number | null][] = [
    ["Requested", s.sosAt], ["Ambulance assigned", d.accepted], ["Picked up", d.confirmed], ["Accepted by hospital", d.hospitalAcceptedAt], ["Arrived", d.doorAt], ["Received", d.received],
  ];
  return (
    <div className="h-page h-detail">
      <div className="h-detail-head">
        <h2>Case #{CASE_ID}</h2>
        <SeverityBadge level={s.confirm.severity} size="lg" />
        <span className="chip"><CategoryIcon c={s.confirm.category} size={15} />HEART</span>
        <span className="tag-soft">{status}</span>
        <SimTag />
      </div>
      <div className="h-detail-grid">
        <section className="card"><p className="card-k">Patient</p><div className="kv"><div><span>Name</span><b>Rajesh Kulkarni</b></div><div><span>Age</span><b>61</b></div><div><span>Sex</span><b>Male</b></div></div></section>
        <section className="card"><p className="card-k">Health profile</p><div className="kv"><div><span>Blood</span><b>B+</b></div><div><span>Conditions</span><b>Diabetes</b></div><div><span>Medicines</span><b>Metformin 500 mg twice daily</b></div></div><div className="allergy">Allergy: Aspirin</div></section>
        <section className="card span2"><p className="card-k">Handover</p><Sbar /><p className="muted-s">Source: caller's report and answers</p></section>
        <section className="card"><p className="card-k">Caller answers</p>
          {s.answers.length === 0 ? <p className="muted-s">No answers yet.</p> : (
            <div className="kv">{QUESTIONS.filter((q) => s.answers.some((a) => a.id === q.id)).map((q) => { const a = s.answers.find((x) => x.id === q.id)!; return <div key={q.id}><span>{q.text}</span><b>{a.answer} · {clock(a.at)}</b></div>; })}</div>
          )}
        </section>
        <section className="card"><p className="card-k">Timeline</p><ul className="timeline">{timeline.map(([k, t]) => <li key={k}><span>{k}</span><b>{t && t <= now ? clock(t) : "…"}</b></li>)}</ul></section>
        <section className="card"><p className="card-k">Assignment</p>
          <label className="lbl">Room<select className="field" value={room} onChange={(e) => setRoom(e.target.value)}>{["Resus Bay 2", "ER-2", "ER-3", "ER-5"].map((r) => <option key={r}>{r}</option>)}</select></label>
          <p className="muted-s">{TEAM.join(" · ")}</p>
          <button className="btn2 btn2-light btn2-sm" onClick={() => toast("Saved")}>Save</button>
        </section>
        <section className="card"><p className="card-k">Flags</p><p className="muted-s">No medico-legal flag (not an accident or assault).</p>
          <p className="card-k" style={{ marginTop: 8 }}>Unknown patient</p><p className="muted-s">Not needed: patient identified from the family profile.</p></section>
      </div>
    </div>
  );
}

/* ---------- H8 · Alerts ---------- */
export function Alerts() {
  const { s, d } = useDemoActions();
  const live: { t: string; text: string; tone: string }[] = [];
  if (d.hospitalId === "greenfield" && d.stage === "atDoor" && d.doorSecs > 15 * 60) live.push({ t: "now", text: `MH14 AB 1234 waiting ${Math.floor(d.doorSecs / 60)} min at the door`, tone: "bad" });
  if (s.signal === "lost" && d.active && d.accepted) live.push({ t: "now", text: "Ambulance MH14 AB 1234 signal lost", tone: "bad" });
  if (s.worsenedAt && d.hospitalId === "greenfield") live.push({ t: clock(s.worsenedAt), text: "Incoming patient condition worsened, now CRITICAL", tone: "bad" });
  if (d.reroute && d.reroute.from === "greenfield") live.push({ t: clock(d.reroute.at), text: `Incoming patient diverted to another hospital, reason: ${d.reroute.reason}`, tone: "warn" });
  const past = [
    { t: "10:14 PM", text: "A request expired without a response at 10:14 PM", tone: "warn" },
    { t: "9:52 PM", text: "ICU numbers not updated for 35 min", tone: "warn" },
  ];
  const all = [...live, ...past];
  return (
    <div className="h-page">
      {all.length === 0 ? <Empty icon="check" text="All clear." /> : (
        <div className="list">
          {all.map((a, i) => (
            <div key={i} className="list-row"><span className={`alert-dot ${a.tone}`}><Icon name="alert" size={16} /></span><span className="list-main"><b>{a.text}</b></span><span className="muted-s">{a.t}</span></div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- H9 · Settings ---------- */
export function HSettings({ sounds, setSounds, onLogout }: { sounds: boolean; setSounds: (v: boolean) => void; onLogout: () => void }) {
  return (
    <div className="h-page h-narrow">
      <div className="card">
        <label className="switch-row"><span>Alert sounds<small>New requests repeat every 10 s until handled</small></span><input type="checkbox" className="switch" checked={sounds} onChange={(e) => setSounds(e.target.checked)} /></label>
        <label className="switch-row"><span>Browser notifications</span><input type="checkbox" className="switch" defaultChecked /></label>
      </div>
      <div className="card"><p className="card-k">Language</p><p className="muted-s">English (default for hospital staff)</p></div>
      <button className="btn2 btn2-light" onClick={onLogout}><Icon name="logout" size={18} />Log out</button>
    </div>
  );
}
