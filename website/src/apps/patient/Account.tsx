import { useState } from "react";
import { Reorder } from "framer-motion";
import { useNavigate } from "react-router-dom";
import Icon, { CategoryIcon } from "../../ui/Icon";
import { Avatar, Empty } from "../../ui/Bits";
import { Dialog } from "../../ui/Dialog";
import { useToast } from "../../ui/toast";
import { CONTACTS } from "../../demo/data";
import { useDemoActions } from "../../demo/actions";
import { hospitalInfo } from "../../demo/hospitalInfo";
import { ago, clock } from "../../demo/format";
import { Call108, Screen, TopBar } from "./layout";
import { setSession } from "./session";
import { whoLabel } from "./people";

/* P22 · My health profile */
export function Profile() {
  const nav = useNavigate();
  const toast = useToast();
  const [famSee, setFamSee] = useState(true);
  return (
    <Screen tabs bottom={<Call108 compact />}>
      <TopBar title="My health profile" right={<button className="icon-btn" aria-label="Settings" onClick={() => nav("/app/settings")}><Icon name="settings" /></button>} />
      <div className="pad form">
        <div className="meter-card">
          <div className="meter-top"><b>Profile 70% complete</b><span>add medicines</span></div>
          <div className="meter"><span style={{ width: "70%" }} /></div>
        </div>
        <div className="member-head"><Avatar name="Rahul Kulkarni" size={56} /><div><h2>Rahul Kulkarni</h2><p className="muted-s">32 · Male</p></div></div>

        <p className="lbl-t">Basics</p>
        <div className="row-2">
          <label className="lbl">Date of birth<input className="field" type="date" defaultValue="1994-02-14" /></label>
          <label className="lbl">Sex<select className="field" defaultValue="M"><option value="M">Male</option><option value="F">Female</option><option value="O">Other</option></select></label>
        </div>

        <p className="lbl-t">Critical</p>
        <label className="lbl">Blood group<select className="field" defaultValue="O+">{["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-", "Don't know"].map((b) => <option key={b}>{b}</option>)}</select></label>
        <div className="allergy-card">
          <b>Allergies</b>
          <input className="field" placeholder="None known. Add Penicillin, Aspirin, Sulfa…" />
        </div>
        <label className="lbl">Conditions<input className="field" placeholder="e.g. Asthma" /></label>
        <label className="lbl">Current medicines<input className="field" placeholder="Name and dose (optional)" /></label>

        <p className="lbl-t">Insurance</p>
        <div className="row-2">
          <label className="lbl">Provider<input className="field" defaultValue="Star Health" /></label>
          <label className="lbl">Policy number<input className="field" defaultValue="SH-22XXXX19" /></label>
        </div>

        <p className="lbl-t">Home</p>
        <label className="lbl">Address<input className="field" defaultValue="Sector 26, Pradhikaran, Akurdi" /></label>

        <p className="lbl-t">Notes</p>
        <textarea className="field" rows={2} placeholder='e.g. "Has pacemaker", "Uses wheelchair"' />

        <p className="lbl-t">Who can see this</p>
        <label className="switch-row card"><span>Family members</span><input type="checkbox" className="switch" checked={famSee} onChange={(e) => setFamSee(e.target.checked)} /></label>
        <p className="help small">Ambulance and hospital see it only during an emergency.</p>
        <button className="btn2 btn2-dark btn2-full" onClick={() => toast("Saved")}>Save</button>
        <div className="row-2">
          <button className="btn2 btn2-light" onClick={() => nav("/app/contacts")}><Icon name="phone" size={18} />Emergency contacts</button>
          <button className="btn2 btn2-light" onClick={() => nav("/app/settings")}><Icon name="settings" size={18} />Settings</button>
        </div>
      </div>
    </Screen>
  );
}

/* P23 · Emergency contacts */
export function Contacts() {
  const toast = useToast();
  const [items, setItems] = useState(CONTACTS);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", phone: "", relation: "", lang: "Marathi" });
  const add = () => {
    if (!form.name || form.phone.replace(/\D/g, "").length < 10) return toast("Add a name and a 10-digit number");
    const masked = `+91 ${form.phone.replace(/\D/g, "").slice(0, 2)}XXX XX${form.phone.replace(/\D/g, "").slice(-3)}`;
    setItems((xs) => [...xs, { id: String(Date.now()), name: form.name, relation: form.relation || "Contact", phone: masked, lang: form.lang }]);
    setForm({ name: "", phone: "", relation: "", lang: "Marathi" });
    setAdding(false);
    toast("Saved");
  };
  return (
    <Screen bottom={<Call108 compact />}>
      <TopBar title="Emergency contacts" back />
      <div className="pad">
        <p className="help">They'll get an SMS with a live tracking link. No app needed.</p>
        {items.length === 0 ? <Empty icon="users" text="Add people who should be told if you have an emergency." /> : (
          <Reorder.Group axis="y" values={items} onReorder={setItems} className="list">
            {items.map((c, i) => (
              <Reorder.Item key={c.id} value={c} className="list-row drag">
                <span className="order">{i + 1}</span>
                <span className="list-main"><b>{c.name}</b><small>{c.relation} · {c.phone} · {c.lang}</small></span>
                <span className="grip" aria-label="Drag to reorder"><Icon name="list" size={18} /></span>
              </Reorder.Item>
            ))}
          </Reorder.Group>
        )}
        {adding ? (
          <div className="card form">
            <label className="lbl">Name<input className="field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
            <label className="lbl">Phone<input className="field" inputMode="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="10-digit number" /></label>
            <div className="row-2">
              <label className="lbl">Relation<input className="field" value={form.relation} onChange={(e) => setForm({ ...form, relation: e.target.value })} /></label>
              <label className="lbl">SMS language<select className="field" value={form.lang} onChange={(e) => setForm({ ...form, lang: e.target.value })}><option>English</option><option>Hindi</option><option>Marathi</option></select></label>
            </div>
            <div className="row-2"><button className="btn2 btn2-light" onClick={() => setAdding(false)}>Cancel</button><button className="btn2 btn2-dark" onClick={add}>Save</button></div>
          </div>
        ) : (
          <button className="btn2 btn2-light btn2-full" onClick={() => setAdding(true)}><Icon name="plus" size={18} />Add contact</button>
        )}
      </div>
    </Screen>
  );
}

/* P24 · History */
export function History() {
  const { s, d } = useDemoActions();
  const [open, setOpen] = useState<null | "current" | "past">(null);
  const cur = d.stage === "handedOver" || (s.closedAt !== null && s.sosAt !== null);
  const info = hospitalInfo(d.hospitalId, s.room);
  return (
    <Screen tabs bottom={<Call108 compact />}>
      <TopBar title="History" />
      <div className="pad">
        <div className="list">
          {cur && s.sosAt && (
            <button className="list-row" onClick={() => setOpen("current")}>
              <span className="cat-dot"><CategoryIcon c="cardiac" size={18} /></span>
              <span className="list-main"><b>Today, {clock(s.sosAt)} · for {whoLabel(s.forWhom)}</b><small>{info.h.name}</small></span>
              <span className="tag-soft ok">Handed over</span>
            </button>
          )}
          <button className="list-row" onClick={() => setOpen("past")}>
            <span className="cat-dot"><CategoryIcon c="respiratory" size={18} /></span>
            <span className="list-main"><b>12 Mar, 6:40 AM · for Aaji</b><small>Hillview Medical College Hospital</small></span>
            <span className="tag-soft ok">Handed over</span>
          </button>
          <button className="list-row">
            <span className="cat-dot"><CategoryIcon c="trauma" size={18} /></span>
            <span className="list-main"><b>2 Jan, 9:15 PM · for someone else</b><small>Reported by mistake</small></span>
            <span className="tag-soft">Cancelled</span>
          </button>
        </div>
      </div>
      <Dialog open={open !== null} title={open === "current" ? `Today · ${info.h.name}` : "12 Mar · Hillview Medical College Hospital"} onClose={() => setOpen(null)}
        actions={<button className="btn2 btn2-dark" onClick={() => setOpen(null)}>Close</button>}>
        {open === "current" ? (
          <ul className="timeline">
            <li><span>Requested</span><b>{clock(s.sosAt)}</b></li><li><span>Ambulance</span><b>{clock(d.accepted)}</b></li>
            <li><span>Picked up</span><b>{clock(d.confirmed)}</b></li><li><span>Arrived</span><b>{clock(d.doorAt)}</b></li>
            <li><span>Handed over</span><b>{clock(d.received)}</b></li>
          </ul>
        ) : (
          <ul className="timeline">
            <li><span>Requested</span><b>6:40 AM</b></li><li><span>Ambulance</span><b>6:41 AM</b></li><li><span>Picked up</span><b>6:52 AM</b></li>
            <li><span>Arrived</span><b>7:05 AM</b></li><li><span>Handed over</span><b>7:08 AM</b></li>
          </ul>
        )}
      </Dialog>
    </Screen>
  );
}

/* P25 · Notifications */
export function Notifications() {
  const nav = useNavigate();
  const { s, d, now } = useDemoActions();
  const items: { t: number; title: string; body: string; to: string }[] = [];
  const hosp = hospitalInfo(d.hospitalId, s.room);
  if (d.accepted && d.accepted <= now) items.push({ t: d.accepted, title: "Ambulance on the way", body: `MH14 AB 1234 (ALS) · 9 min`, to: "/app/live" });
  if (d.arrivedAt && d.arrivedAt <= now) items.push({ t: d.arrivedAt, title: "Ambulance has arrived", body: "The crew is with you", to: "/app/live" });
  if (d.hospitalAcceptedAt && d.hospitalAcceptedAt <= now) items.push({ t: d.hospitalAcceptedAt, title: d.reroute ? "Hospital changed" : "Hospital ready", body: d.reroute ? `Now going to ${hosp.h.name}` : `${hosp.h.name} · ${hosp.room} · ${hosp.gate}`, to: "/app/live" });
  if (d.received && d.received <= now) items.push({ t: d.received, title: "With the doctors", body: `Handed over at ${clock(d.received)}`, to: "/app/live" });
  items.sort((a, b) => b.t - a.t);
  return (
    <Screen bottom={<Call108 compact />}>
      <TopBar title="Notifications" back />
      <div className="pad">
        {items.length === 0 && <Empty icon="bell" text="No new notifications." />}
        <div className="list">
          {items.map((n) => (
            <button key={n.title + n.t} className="list-row" onClick={() => nav(n.to)}>
              <span className="unread" aria-label="Unread" />
              <span className="list-main"><b>{n.title}</b><small>{n.body}</small></span>
              <span className="muted-s">{ago(n.t, now)}</span>
            </button>
          ))}
          <button className="list-row read" onClick={() => nav("/app/family")}>
            <span className="list-main"><b>Riya joined Kulkarni Family</b><small>She can now call help for anyone in the family</small></span>
            <span className="muted-s">2 d ago</span>
          </button>
        </div>
      </div>
    </Screen>
  );
}

/* P26 · Settings */
export function Settings() {
  const nav = useNavigate();
  const toast = useToast();
  const [famAlerts, setFamAlerts] = useState(true);
  const [sounds, setSounds] = useState(true);
  const [famSee, setFamSee] = useState(true);
  const [dlg, setDlg] = useState<null | "leave" | "logout">(null);
  return (
    <Screen bottom={<Call108 compact />}>
      <TopBar title="Settings" back />
      <div className="pad">
        <div className="card">
          <p className="card-k">Language</p>
          <p className="muted-s">The app screens are in English for now. The website already speaks English, Hindi, Marathi, Telugu, Tamil and Gujarati; app translations come next.</p>
        </div>
        <div className="card">
          <p className="card-k">Notifications</p>
          <label className="switch-row"><span>Family emergencies</span><input type="checkbox" className="switch" checked={famAlerts} onChange={(e) => setFamAlerts(e.target.checked)} /></label>
          <label className="switch-row"><span>Sounds</span><input type="checkbox" className="switch" checked={sounds} onChange={(e) => setSounds(e.target.checked)} /></label>
        </div>
        <div className="card">
          <p className="card-k">Privacy</p>
          <label className="switch-row"><span>Family can see my profile</span><input type="checkbox" className="switch" checked={famSee} onChange={(e) => setFamSee(e.target.checked)} /></label>
        </div>
        <div className="list">
          <button className="list-row" onClick={() => setDlg("leave")}><span className="list-main"><b>Leave family</b></span><Icon name="chevron" size={18} /></button>
          <button className="list-row" onClick={() => toast("GoldenHour demo v0.1 · HackMatrix 5.0")}><span className="list-main"><b>About</b><small>Version, terms, privacy</small></span><Icon name="chevron" size={18} /></button>
          <button className="list-row" onClick={() => setDlg("logout")}><span className="list-main"><b className="danger-text">Log out</b></span><Icon name="logout" size={18} /></button>
        </div>
      </div>
      <Dialog open={dlg === "leave"} title="Leave Kulkarni Family?" onClose={() => setDlg(null)}
        actions={<><button className="btn2 btn2-light" onClick={() => setDlg(null)}>Stay</button><button className="btn2 btn2-danger" onClick={() => { setDlg(null); toast("Demo: you are still in the family"); }}>Leave</button></>}>
        You won't be told about family emergencies anymore.
      </Dialog>
      <Dialog open={dlg === "logout"} title="Log out?" onClose={() => setDlg(null)}
        actions={<><button className="btn2 btn2-light" onClick={() => setDlg(null)}>Cancel</button><button className="btn2 btn2-dark" onClick={() => { setSession(null); nav("/app/splash", { replace: true }); }}>Log out</button></>}>
        You can still call 108 without logging in.
      </Dialog>
    </Screen>
  );
}
