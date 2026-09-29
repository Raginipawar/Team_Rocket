import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import QRCode from "qrcode";
import Icon from "../../ui/Icon";
import { Avatar } from "../../ui/Bits";
import { Dialog } from "../../ui/Dialog";
import { useToast } from "../../ui/toast";
import { PEOPLE } from "../../demo/data";
import { useDemoActions } from "../../demo/actions";
import { Call108, Screen, TopBar } from "./layout";

const INVITE_CODE = "482913";
const inviteUrl = () => `${location.origin}${location.pathname}#/app/family/join?code=${INVITE_CODE}`;

/* P17 · Family Space home */
export function FamilyHome() {
  const nav = useNavigate();
  const { s, d } = useDemoActions();
  const liveFor = d.active && d.stage !== "handedOver" && d.stage !== "cancelled" ? s.forWhom : null;
  return (
    <Screen tabs bottom={<Call108 compact />}>
      <TopBar title="Kulkarni Family" sub="5 members · you are admin" />
      <div className="pad">
        <div className="list">
          {PEOPLE.map((p) => {
            const live = liveFor === p.id;
            return (
              <button key={p.id} className={`list-row${live ? " live" : ""}`} onClick={() => nav(live ? "/app/follow" : `/app/family/${p.id}`)}>
                <Avatar name={p.short} size={44} managed={p.role === "Dependent"} />
                <span className="list-main">
                  <b>{p.id === "rahul" ? "You" : p.short}</b>
                  <small>{p.id === "rahul" ? "Rahul · Admin" : `${p.short} · ${p.relation}`}</small>
                </span>
                {p.role === "Dependent" && <span className="tag-soft">Managed</span>}
                {live ? <span className="live-pill"><span className="pulse-dot red" />Live now</span> : <span className="status-dot ok" aria-label="Normal" />}
                <Icon name="chevron" size={18} />
              </button>
            );
          })}
        </div>
        <div className="row-2">
          <button className="btn2 btn2-dark" onClick={() => nav("/app/family/invite")}><Icon name="userPlus" size={18} />Invite member</button>
          <button className="btn2 btn2-light" onClick={() => nav("/app/family/add")}><Icon name="plus" size={18} />Add dependent</button>
        </div>
        <button className="link-btn center-block" onClick={() => nav("/app/family/join")}>Join another family with a code</button>
      </div>
    </Screen>
  );
}

/* P18 · Member card */
export function MemberCard() {
  const nav = useNavigate();
  const toast = useToast();
  const { id } = useParams();
  const p = PEOPLE.find((x) => x.id === id) ?? PEOPLE[1];
  const [notify, setNotify] = useState(true);
  const [removeOpen, setRemoveOpen] = useState(false);
  const priv = p.id === "riya";
  return (
    <Screen bottom={<Call108 compact />}>
      <TopBar title={p.short} back="/app/family" />
      <div className="pad">
        <div className="member-head">
          <Avatar name={p.short} size={64} managed={p.role === "Dependent"} />
          <div><h2>{p.name}</h2><p className="muted-s">{p.age} · {p.relation} · {p.role}</p></div>
        </div>
        <button className="btn2 btn2-red btn2-full btn2-hero" onClick={() => nav("/app", { state: { forWhom: p.id } })}>
          <span className="sos-mini">SOS</span>Call help for {p.short}
        </button>

        <div className="card">
          <p className="card-k">Health profile</p>
          {priv ? <p className="muted-s">{p.short} has kept her profile private.</p> : (
            <>
              <div className="kv">
                <div><span>Blood group</span><b>{p.blood}</b></div>
                <div><span>Conditions</span><b>{p.conditions.join(", ") || "None"}</b></div>
                <div><span>Medicines</span><b>{p.medicines.join(", ") || "None"}</b></div>
              </div>
              {p.allergies.length > 0 && <div className="allergy">Allergy: {p.allergies.join(", ")}</div>}
            </>
          )}
        </div>

        <label className="switch-row card">
          <span>Notify me about {p.short}'s emergencies</span>
          <input type="checkbox" className="switch" checked={notify} onChange={(e) => setNotify(e.target.checked)} />
        </label>

        <div className="card">
          <p className="card-k">Past emergencies</p>
          {p.id === "aaji" ? <div className="kv"><div><span>12 Mar, 6:40 AM</span><b>Hillview Medical College Hospital</b></div></div> : <p className="muted-s">None.</p>}
        </div>

        {p.role !== "Admin" && (
          <div className="row-2">
            {p.role === "Dependent" && <button className="btn2 btn2-light" onClick={() => nav("/app/family/add")}>Edit profile</button>}
            <button className="btn2 btn2-danger-o" onClick={() => setRemoveOpen(true)}>Remove from family</button>
          </div>
        )}
      </div>
      <Dialog open={removeOpen} title={`Remove ${p.short} from the family?`} onClose={() => setRemoveOpen(false)}
        actions={<><button className="btn2 btn2-light" onClick={() => setRemoveOpen(false)}>Keep</button><button className="btn2 btn2-danger" onClick={() => { setRemoveOpen(false); toast("Demo: nothing was removed"); }}>Remove</button></>}>
        They will no longer see family emergencies.
      </Dialog>
    </Screen>
  );
}

/* P19 · Invite member */
export function Invite() {
  const toast = useToast();
  const [qr, setQr] = useState("");
  useEffect(() => {
    QRCode.toDataURL(inviteUrl(), { margin: 1, width: 360, color: { dark: "#0a0a0a", light: "#ffffff" } }).then(setQr).catch(() => setQr(""));
  }, []);
  const copy = async () => { try { await navigator.clipboard.writeText(inviteUrl()); toast("Invite link copied"); } catch { toast(inviteUrl()); } };
  const msg = encodeURIComponent(`Join the Kulkarni Family on GoldenHour so we can call help for each other. Code ${INVITE_CODE}: ${inviteUrl()}`);
  return (
    <Screen bottom={<Call108 compact />}>
      <TopBar title="Invite to Kulkarni Family" back="/app/family" />
      <div className="pad center">
        <p className="lbl-t">Family code</p>
        <p className="big-code">482 913</p>
        <p className="muted-s">Valid for 24 hours</p>
        {qr && <img className="qr" src={qr} alt="QR code for the invite link" width={200} height={200} />}
        <div className="stack">
          <a className="btn2 btn2-dark btn2-full" href={`https://wa.me/?text=${msg}`} target="_blank" rel="noreferrer"><Icon name="share" size={18} />Share on WhatsApp</a>
          <button className="btn2 btn2-light btn2-full" onClick={copy}><Icon name="copy" size={18} />Copy link</button>
          <a className="btn2 btn2-light btn2-full" href={`sms:?body=${msg}`}><Icon name="mail" size={18} />Share by SMS</a>
        </div>
      </div>
    </Screen>
  );
}

/* P20 · Join family */
export function JoinFamily() {
  const nav = useNavigate();
  const toast = useToast();
  const [digits, setDigits] = useState(["", "", "", "", "", ""]);
  const [err, setErr] = useState("");
  const [found, setFound] = useState(false);
  const [share, setShare] = useState(true);
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const set = (i: number, v: string) => {
    const c = v.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[i] = c;
    setDigits(next);
    setErr("");
    if (c && i < 5) refs.current[i + 1]?.focus();
    if (next.every(Boolean)) {
      const code = next.join("");
      if (code === INVITE_CODE) setFound(true);
      else setErr(code === "000000" ? "Code expired" : "Code not found");
    }
  };
  return (
    <Screen bottom={<Call108 compact />}>
      <TopBar title="Join a family" back="/app/family" />
      <div className="pad">
        {!found ? (
          <>
            <h1 className="ptitle">Enter family code</h1>
            <div className="otp">
              {digits.map((v, i) => (
                <input key={i} ref={(el) => { refs.current[i] = el; }} inputMode="numeric" maxLength={1} value={v} aria-label={`Digit ${i + 1}`} autoFocus={i === 0}
                  onChange={(e) => set(i, e.target.value)} onKeyDown={(e) => { if (e.key === "Backspace" && !v && i > 0) refs.current[i - 1]?.focus(); }} />
              ))}
            </div>
            {err ? <p className="err-text">{err}</p> : <p className="help">Or open the invite link. Demo code: <b>482913</b></p>}
          </>
        ) : (
          <>
            <h1 className="ptitle">Join Kulkarni Family?</h1>
            <p className="help">Members: Rahul, Aai, Riya</p>
            <label className="lbl">How are you related to this family? (optional)<input className="field" placeholder="e.g. Cousin" /></label>
            <label className="switch-row card">
              <span>Let family see my health profile</span>
              <input type="checkbox" className="switch" checked={share} onChange={(e) => setShare(e.target.checked)} />
            </label>
            <div className="row-2">
              <button className="btn2 btn2-light" onClick={() => nav("/app/family")}>Cancel</button>
              <button className="btn2 btn2-dark" onClick={() => { toast("Joined Kulkarni Family"); nav("/app/family"); }}>Join</button>
            </div>
          </>
        )}
      </div>
    </Screen>
  );
}

/* P21 · Add dependent */
export function AddDependent() {
  const nav = useNavigate();
  const toast = useToast();
  return (
    <Screen bottom={<div className="pad-x"><button className="btn2 btn2-dark btn2-full" onClick={() => { toast("Saved"); nav("/app/family"); }}>Save</button></div>}>
      <TopBar title="Add dependent" back="/app/family" sub="For a family member without a phone" />
      <div className="pad form">
        <label className="lbl">Name<input className="field" defaultValue="Aaji" /></label>
        <div className="row-2">
          <label className="lbl">Relation<input className="field" defaultValue="Grandmother" /></label>
          <label className="lbl">Age<input className="field" inputMode="numeric" defaultValue="84" /></label>
        </div>
        <div className="row-2">
          <label className="lbl">Sex<select className="field" defaultValue="F"><option value="F">Female</option><option value="M">Male</option><option value="O">Other</option></select></label>
          <label className="lbl">Blood group<select className="field" defaultValue="B+">{["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-", "Don't know"].map((b) => <option key={b}>{b}</option>)}</select></label>
        </div>
        <label className="lbl">Allergies<input className="field" placeholder="e.g. Penicillin" /></label>
        <label className="lbl">Conditions<input className="field" defaultValue="Heart disease" /></label>
        <label className="lbl">Medicines<input className="field" placeholder="Name and dose" /></label>
        <label className="lbl">Home address<input className="field" defaultValue="Sector 26, Pradhikaran, Akurdi" /></label>
        <label className="lbl">Notes<textarea className="field" rows={2} defaultValue="Uses walker" /></label>
        <p className="help">You and other family admins can manage this profile.</p>
      </div>
    </Screen>
  );
}
