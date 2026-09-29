import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import Icon, { CategoryIcon } from "../../ui/Icon";
import { AmbType, CountdownRing, Empty, Eta, Freshness, SeverityBadge, SignalBadge, SimTag, WhyChips } from "../../ui/Bits";
import DemoMap from "../../ui/DemoMap";
import { Dialog, ReasonDialog } from "../../ui/Dialog";
import { useToast } from "../../ui/toast";
import { CATEGORY_LABEL, REASONS, TEAM } from "../../demo/data";
import { useDemoActions } from "../../demo/actions";
import { clock, mmss } from "../../demo/format";
import type { Room } from "./shared";
import { useHospitalTone } from "./shared";


export function Sbar() {
  return (
    <div className="sbar">
      <p><b>S:</b> 60-year-old male with chest pain and sweating for ~40 min.</p>
      <p><b>B:</b> Diabetic on metformin, aspirin allergy.</p>
      <p><b>A:</b> Suspected heart attack; conscious, breathing difficulty.</p>
      <p><b>R:</b> Prepare cath lab and cardiologist.</p>
    </div>
  );
}

/* Column 1 · request card */
function RequestCard({ rooms, sounds }: { rooms: Room[]; sounds: boolean }) {
  const { s, d, now, actions } = useDemoActions();
  const toast = useToast();
  const [acceptOpen, setAcceptOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [room, setRoom] = useState("Resus Bay 2");
  const [team, setTeam] = useState<string[]>(TEAM);
  const pending = d.stage === "asking" && d.hospitalId === "greenfield";
  const expired = d.reroute && d.reroute.from === "greenfield" && now - d.reroute.at < 15000;
  useHospitalTone(pending, sounds);

  if (expired) {
    return (
      <div className="req expired">
        <p className="card-k">Request</p>
        <p>{s.gfRejectedAt ? "Rejected: moved to another hospital." : "Moved to another hospital: no response."}</p>
      </div>
    );
  }
  if (!pending) return <Empty icon="bell" text="No incoming requests right now." />;

  const free = rooms.filter((r) => r.status === "free" && (r.type === "Resus" || r.type === "ER"));
  return (
    <motion.div className="req" initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
      <div className="req-top">
        <div className="row-c left">
          <SeverityBadge level={s.confirm.severity} />
          <span className="chip"><CategoryIcon c={s.confirm.category} size={15} />{CATEGORY_LABEL[s.confirm.category].toUpperCase()}</span>
          <span className="tag-soft ok"><Icon name="check" size={12} stroke={2.6} /> Confirmed by paramedic</span>
        </div>
        <div className="req-ring"><CountdownRing secs={d.hospitalSecsLeft} total={45} size={58} /><span>Respond in {mmss(d.hospitalSecsLeft)}</span></div>
      </div>
      <p className="req-patient">Male · ~60</p>
      <p className="profile-line">Blood <b>B+</b> · <span className="allergy-inline">Allergy: Aspirin</span> · Diabetes · Metformin 500 mg</p>
      <Sbar />
      <div>
        <p className="card-k">Prepare</p>
        <div className="prep">
          {[["Cardiologist", 94], ["Cath lab", 88], ["Defibrillator", 81], ["Blood B+ 2 units", 52]].map(([k, v]) => (
            <span key={k as string} className="prep-item"><b>{k}</b><i style={{ width: `${v}%` }} /><em>{v}%</em></span>
          ))}
        </div>
      </div>
      <div className="req-amb">
        <span><b>MH14 AB 1234</b> <AmbType type="ALS" /> · ETA <Eta min={11} /></span>
        <SignalBadge signal={s.signal} />
      </div>
      <p className="card-k">Why you</p>
      <WhyChips items={[{ icon: "check", text: "Cath lab available" }, { icon: "doctor", text: "Cardiologist on duty at arrival" }, { icon: "clock", text: "11 min" }]} />
      <div className="row-2">
        <button className="btn2 btn2-green btn2-lg" onClick={() => setAcceptOpen(true)}>Accept</button>
        <button className="btn2 btn2-danger-o btn2-lg" onClick={() => setRejectOpen(true)}>Reject</button>
      </div>

      <Dialog open={acceptOpen} title="Accept this patient" onClose={() => setAcceptOpen(false)}
        actions={<><button className="btn2 btn2-light" onClick={() => setAcceptOpen(false)}>Cancel</button>
          <button className="btn2 btn2-dark" onClick={() => { actions.hospitalAccept(room); setAcceptOpen(false); toast(`Accepted. ${room} reserved.`); }}>Confirm</button></>}>
        <label className="lbl">Room<select className="field" value={room} onChange={(e) => setRoom(e.target.value)}>{free.map((r) => <option key={r.code}>{r.code}</option>)}</select></label>
        <p className="lbl-t">Team</p>
        {TEAM.map((t) => (
          <label key={t} className="check-row"><input type="checkbox" checked={team.includes(t)} onChange={(e) => setTeam(e.target.checked ? [...team, t] : team.filter((x) => x !== t))} />{t}</label>
        ))}
      </Dialog>
      <ReasonDialog open={rejectOpen} title="Reject this request?" reasons={REASONS.reject} confirmLabel="Reject" danger
        onClose={() => setRejectOpen(false)}
        onConfirm={(r) => { actions.hospitalReject(r); setRejectOpen(false); toast("Rejected. Sent to the next hospital."); }} />
    </motion.div>
  );
}

/* Column 2 · incoming */
function Incoming() {
  const nav = useNavigate();
  const { s, d, now } = useDemoActions();
  const live = d.hospitalId === "greenfield" && d.hospitalAcceptedAt !== null && d.stage === "transporting";
  const diverted = d.reroute && d.reroute.from === "greenfield" && d.hospitalAcceptedAt !== null && now - d.reroute.at < 20000 && d.stage === "transporting";
  return (
    <>
      <DemoMap d={live ? d : { ...d, active: false }} now={now} variant="hospital" height={180} signal={s.signal} severity={s.confirm.severity} />
      <div className="inc-list">
        <AnimatePresence>
          {live && (
            <motion.button key="live" className="inc-row live" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => nav("/hospital/patient")}>
              <span className="inc-title"><b>MH14 AB 1234</b><SeverityBadge level={s.confirm.severity} /><span>HEART</span></span>
              <span>ETA {s.signal === "lost" ? `~ ${d.etaMin} min (estimated)` : `${d.etaMin} min`} · {s.room}</span>
              {s.signal === "lost" ? <span className="danger-text small">Signal lost 3 min ago · estimated {d.etaMin} min</span> : <SignalBadge signal={s.signal} />}
              {s.worsenedAt && <span className="tag-soft bad">Patient condition worsened</span>}
            </motion.button>
          )}
          {diverted && (
            <motion.div key="div" className="inc-row faded" initial={{ opacity: 1 }} animate={{ opacity: 0.5 }}>
              <span><b>MH14 AB 1234</b> · Diverted to another hospital</span>
            </motion.div>
          )}
        </AnimatePresence>
        <div className="inc-row sim"><span className="inc-title"><b>MH14 CD 5678</b><SeverityBadge level="urgent" /><span>ACCIDENT</span></span><span>ETA 14 min · ER-5</span><SignalBadge signal="ok" /></div>
        <div className="inc-row sim"><span className="inc-title"><b>MH14 EF 2211</b><SeverityBadge level="stable" /><span>BREATHING</span></span><span>ETA 22 min · ER-3</span><SignalBadge signal="weak" /></div>
      </div>
    </>
  );
}

/* Column 3 · at the door */
function AtDoor() {
  const { d, now, actions } = useDemoActions();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const here = d.hospitalId === "greenfield" && d.stage === "atDoor";
  const late = d.doorSecs >= 15 * 60;
  const justDone = d.hospitalId === "greenfield" && d.received && now - d.received < 15000;
  return (
    <div className="inc-list">
      {here ? (
        <div className={`door-row${late ? " late" : ""}`}>
          <span><b>MH14 AB 1234</b> · arrived {clock(d.doorAt)}</span>
          <span className="door-wait">Door wait <b>{mmss(d.doorSecs)}</b></span>
          {late && <span className="danger-text small">Ambulance waiting at the door for {Math.floor(d.doorSecs / 60)} min</span>}
          <button className="btn2 btn2-dark" onClick={() => setOpen(true)}>Patient received</button>
        </div>
      ) : justDone ? (
        <div className="door-row done"><Icon name="check" size={18} stroke={2.6} /><span>MH14 AB 1234 received at {clock(d.received)}</span></div>
      ) : <Empty icon="ambulance" text="No ambulances at the door." />}
      <Dialog open={open} title="Patient received" onClose={() => setOpen(false)}
        actions={<><button className="btn2 btn2-light" onClick={() => setOpen(false)}>Cancel</button><button className="btn2 btn2-dark" onClick={() => { actions.received(); setOpen(false); toast("Handover recorded"); }}>Done</button></>}>
        <p>Receiving staff (optional)</p>
        {TEAM.map((t) => <label key={t} className="check-row"><input type="checkbox" defaultChecked={t.includes("Kulkarni")} />{t}</label>)}
      </Dialog>
    </div>
  );
}

/* Right strip · capacity snapshot */
export function Capacity() {
  const nav = useNavigate();
  const rows: [string, string, number][] = [
    ["ER beds", "4 free / 12", 3], ["Resus bays", "1 free / 3", 4], ["ICU beds", "2 free / 10", 18],
    ["Trauma bays", "0 free / 2", 6], ["Cath lab", "Available", 2], ["Ventilators", "3 / 8", 45],
  ];
  return (
    <aside className="cap">
      <h3>Capacity</h3>
      {rows.map(([k, v, m]) => (
        <div key={k} className="cap-row">
          <span>{k}</span><b>{v}</b>
          <Freshness minutes={m} estimate={k === "Ventilators" ? "64% chance still free" : undefined} />
        </div>
      ))}
      <div className="cap-links"><button className="link-btn" onClick={() => nav("/hospital/rooms")}>Update rooms</button><button className="link-btn" onClick={() => nav("/hospital/resources")}>Update resources</button></div>
    </aside>
  );
}

export default function Dashboard({ rooms, sounds }: { rooms: Room[]; sounds: boolean }) {
  return (
    <div className="h-dash">
      <section className="h-col">
        <h3 className="h-col-title">New requests</h3>
        <RequestCard rooms={rooms} sounds={sounds} />
      </section>
      <section className="h-col">
        <h3 className="h-col-title">Incoming</h3>
        <Incoming />
      </section>
      <section className="h-col">
        <h3 className="h-col-title">At the door</h3>
        <AtDoor />
        <div className="row-c left" style={{ marginTop: 12 }}><SimTag /></div>
      </section>
      <Capacity />
    </div>
  );
}

