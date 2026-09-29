import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import Icon, { CategoryIcon } from "../../ui/Icon";
import { Banner, CallButton, Confidence, Eta, SeverityBadge, SimTag, Stepper, WhyChips, AmbType } from "../../ui/Bits";
import DemoMap from "../../ui/DemoMap";
import { ReasonDialog } from "../../ui/Dialog";
import { useToast } from "../../ui/toast";
import { CASE_ID, CATEGORY_LABEL, FIRST_AID_CHEST, QUESTIONS, REASONS } from "../../demo/data";
import { useDemoActions } from "../../demo/actions";
import { hospitalInfo } from "../../demo/hospitalInfo";
import { clock } from "../../demo/format";
import { patientSteps } from "../../demo/steps";
import type { Derived } from "../../demo/engine";
import { Call108, Screen, TopBar } from "./layout";
import { whoLabel, whoPerson } from "./people";
import { canListen, listenYesNo, speak } from "./speech";

function useOnline() {
  const [on, setOn] = useState(() => navigator.onLine);
  useEffect(() => {
    const up = () => setOn(true);
    const down = () => setOn(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => { window.removeEventListener("online", up); window.removeEventListener("offline", down); };
  }, []);
  return on;
}

/* P11 · Sending */
function Sending() {
  return (
    <div className="center-stage">
      <motion.span className="send-pulse" animate={{ scale: [1, 1.25, 1], opacity: [1, 0.6, 1] }} transition={{ duration: 1.2, repeat: Infinity }} />
      <h1 className="ptitle">Sending your request…</h1>
      <p className="help">Keep this screen open.</p>
      <Call108 compact />
    </div>
  );
}

/* P12 · Help requested */
function Requested({ who }: { who: string }) {
  return (
    <div className="center-stage">
      <motion.span className="big-check" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 260, damping: 18 }}>
        <Icon name="check" size={46} stroke={2.6} />
      </motion.span>
      <h1 className="ptitle">Help is on the way</h1>
      <p className="help">Finding the nearest ambulance for {who}…</p>
      <p className="lbl-t">We understood</p>
      <div className="chips-wrap center">
        {["Chest pain", "Breathing difficulty", "Sweating", "Male ~60"].map((c) => <span key={c} className="pick on-soft">{c}</span>)}
      </div>
      <div className="row-c"><SeverityBadge level="critical" ai /><span className="chip"><CategoryIcon c="cardiac" size={15} />Heart</span><Confidence value={0.91} /></div>
      <p className="ok-text">{who === "you" ? "Your" : `${who}'s`} health profile shared <Icon name="check" size={14} stroke={2.6} /></p>
    </div>
  );
}

/* Question card (AI assistant) */
function QuestionCard({ family }: { family?: boolean }) {
  const { s, actions } = useDemoActions();
  const [sent, setSent] = useState(false);
  const [listening, setListening] = useState(false);
  const [heard, setHeard] = useState("");
  const answered = new Set(s.answers.map((a) => a.id));
  const q = QUESTIONS.find((x) => !answered.has(x.id));
  const idx = QUESTIONS.findIndex((x) => x.id === q?.id) + 1;

  if (family) return <div className="card"><p className="card-k">Questions from the doctors</p><p>Rahul is answering the doctor's questions.</p></div>;

  const answer = (a: string) => {
    if (!q) return;
    actions.answer(q.id, a);
    setSent(true);
    setHeard("");
    setTimeout(() => setSent(false), 1400);
  };
  const byVoice = () => {
    setListening(true);
    listenYesNo((a, h) => {
      setListening(false);
      setHeard(h ? `Heard "${h}"` : "Didn't catch that, please tap an answer.");
      if (a) answer(a);
    });
  };

  return (
    <div className="card q-card">
      <AnimatePresence mode="wait">
        {q ? (
          <motion.div key={q.id} initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -30 }} transition={{ duration: 0.25 }}>
            <div className="q-head">
              <p className="card-k">The doctors want to know ({idx} of {QUESTIONS.length})</p>
              <button className="icon-btn sm" aria-label="Play question aloud" onClick={() => speak(q.text)}><Icon name="speaker" size={18} /></button>
            </div>
            <p className="q-text">{q.text}</p>
            {q.kind === "yesno" ? (
              <div className="row-2">
                <button className="btn2 btn2-dark btn2-lg" onClick={() => answer("Yes")}>Yes</button>
                <button className="btn2 btn2-light btn2-lg" onClick={() => answer("No")}>No</button>
              </div>
            ) : (
              <div className="chips-wrap">{q.choices!.map((c) => <button key={c} className="pick" onClick={() => answer(c)}>{c}</button>)}</div>
            )}
            <div className="q-foot">
              {q.kind === "yesno" && canListen() && (
                <button className="link-btn" onClick={byVoice} disabled={listening}><Icon name="mic" size={16} />{listening ? "Listening…" : "Answer by voice"}</button>
              )}
              <button className="link-btn" onClick={() => answer("Skipped")}>Skip</button>
            </div>
            {heard && <p className="help small">{heard}</p>}
          </motion.div>
        ) : (
          <motion.p key="done" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="ok-text"><Icon name="check" size={16} stroke={2.6} />Thank you, the doctors have this information.</motion.p>
        )}
      </AnimatePresence>
      {sent && <p className="ok-text small"><Icon name="check" size={14} stroke={2.6} />Sent to the ambulance and hospital</p>}
    </div>
  );
}

/* First-aid card */
function FirstAid() {
  const nav = useNavigate();
  const fa = FIRST_AID_CHEST;
  return (
    <div className="card">
      <div className="q-head">
        <p className="card-k">{fa.title}</p>
        <button className="link-btn" onClick={() => speak([...fa.steps, "Do not:", ...fa.donts].join(". "))}><Icon name="speaker" size={16} />Read aloud</button>
      </div>
      <ol className="fa-steps">{fa.steps.map((s) => <li key={s}>{s}</li>)}</ol>
      <ul className="fa-donts">{fa.donts.map((s) => <li key={s}><Icon name="x" size={14} stroke={2.4} />{s}</li>)}</ul>
      <button className="btn2 btn2-red btn2-full" onClick={() => nav("/app/cpr")}>He stopped breathing: start CPR guide</button>
    </div>
  );
}

/* Hospital card */
function HospitalCard({ d, room }: { d: Derived; room: string }) {
  if (d.confirmed === null) return null;
  const info = hospitalInfo(d.hospitalId, room);
  return (
    <div className="card">
      <p className="card-k">Hospital</p>
      {d.stage === "choosing" && <p className="loading-line"><span className="spin" />Choosing the best hospital…</p>}
      {d.stage === "asking" && <p className="loading-line"><span className="spin" /><b>{info.h.name}</b>&nbsp;· asking the hospital to confirm…</p>}
      {d.hospitalAcceptedAt !== null && (
        <>
          <h3 className="h-name">{info.h.name}</h3>
          <p className="muted-s">{info.h.address}</p>
          <WhyChips items={info.why} />
          <div className="kv">
            <div><span>Room</span><b>{info.room}</b></div>
            <div><span>Enter</span><b>{info.gate}</b></div>
            <div><span>Receiving</span><b>{info.team}</b></div>
          </div>
          <div className="row-2">
            <a className="btn2 btn2-light" href={`https://www.google.com/maps/search/${encodeURIComponent(info.h.name + " " + info.h.area)}`} target="_blank" rel="noreferrer"><Icon name="compass" size={18} />Directions</a>
            <CallButton label="Call ER" number={info.er} />
          </div>
        </>
      )}
    </div>
  );
}

/* P13 / P15 · Live emergency */
function LiveBody({ family }: { family?: boolean }) {
  const nav = useNavigate();
  const toast = useToast();
  const online = useOnline();
  const { s, d, now, actions } = useDemoActions();
  const [menu, setMenu] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const who = whoLabel(s.forWhom);
  const person = whoPerson(s.forWhom);
  const title = family ? `${person?.short ?? "Papa"}'s emergency` : s.forWhom === "rahul" ? "Emergency for you" : s.forWhom === "someone" ? "Emergency for someone else" : `Emergency for ${who}`;
  const sev = s.confirm.severity;
  const cat = s.confirm.category;
  const confirmed = d.confirmed !== null;
  const searchingFor = d.offeredAt ? now - d.offeredAt : 0;
  const noAmbulance = d.accepted === null && searchingFor > 90000;
  const lost = s.signal === "lost";
  const kmLeft = d.leg === "patient" ? 2.4 * (1 - d.progress) : 0;

  const copyCase = async () => { try { await navigator.clipboard.writeText(`#${CASE_ID}`); toast("Case number copied"); } catch { toast(`Case #${CASE_ID}`); } };
  const shareLink = async () => {
    const url = `${location.origin}${location.pathname}#/track/8Kq2`;
    try { await navigator.clipboard.writeText(url); toast("Tracking link copied"); } catch { toast(url); }
    setMenu(false);
  };

  return (
    <>
      <TopBar
        title={title}
        back="/app"
        sub={family ? `Reported by Rahul at ${clock(s.sosAt)}` : <button className="case" onClick={copyCase}>Case #{CASE_ID}<Icon name="copy" size={13} /></button>}
        right={
          <div className="menu-wrap">
            <button className="icon-btn" aria-label="More" aria-expanded={menu} onClick={() => setMenu((m) => !m)}><Icon name="dots" /></button>
            {menu && (
              <div className="menu">
                {!family && <button onClick={() => { setMenu(false); setCancelOpen(true); }}>Cancel emergency</button>}
                <button onClick={shareLink}>Share tracking link</button>
                <button onClick={() => { setMenu(false); nav("/app/settings"); }}>Help</button>
              </div>
            )}
          </div>
        }
      />
      <div className="pad live">
        {!online && <Banner type="offline">No internet. Map frozen. Call 108 if urgent.</Banner>}
        {d.reroute && d.hospitalAcceptedAt !== null && (
          <Banner type="warning">New hospital: {hospitalInfo(d.hospitalId).h.name}, reason: {d.reroute.reason}</Banner>
        )}
        {noAmbulance && <Banner type="danger" action={<a className="banner-act" href="tel:108">Call 108</a>}>All nearby ambulances are busy. We've alerted our emergency team.</Banner>}

        <Stepper steps={patientSteps(d, s.sosAt, now)} />

        <DemoMap d={d} now={now} severity={sev} height={230} signal={s.signal} />

        {/* Ambulance card */}
        <div className="card">
          {d.accepted === null ? (
            <p className="loading-line"><span className="spin" />{searchingFor > 30000 ? "Looking a little further…" : "Finding the nearest ambulance… (checked 4 nearby)"}</p>
          ) : (
            <>
              <div className="amb-head">
                <span className="amb-reg">MH14 AB 1234</span><AmbType type="ALS" /><span className="muted-s">Paramedic: S. Patil</span>
              </div>
              {d.stage === "going" ? (
                <p className="eta-line"><Eta min={d.etaMin} lost={lost} big /> <span className="muted-s">Arrives around {clock(d.accepted + 9 * 60000)} · {kmLeft.toFixed(1)} km away</span></p>
              ) : d.leg === "hospital" && d.hospitalAcceptedAt !== null && d.stage === "transporting" ? (
                <p className="eta-line"><span className="muted-s">To hospital ·</span> <Eta min={d.etaMin} lost={lost} big /></p>
              ) : (
                <p className="eta-line"><Eta min={0} arrived arrivedAt={clock(d.arrivedAt)} big /></p>
              )}
              <CallButton label="Call ambulance" number="+919800000000" full />
            </>
          )}
        </div>

        {/* Assessment card (privacy 2.25: family members don't see AI confidence) */}
        <div className="card">
          <p className="card-k">Assessment</p>
          <div className="row-c left">
            <SeverityBadge level={sev} size="lg" ai={!confirmed} confirmed={confirmed} />
            <span className="chip"><CategoryIcon c={cat} size={15} />{CATEGORY_LABEL[cat]}</span>
            {!family && !confirmed && <Confidence value={0.91} />}
          </div>
          <p className="muted-s">Understood: chest pain · breathing difficulty · sweating</p>
        </div>

        {d.stage !== "atDoor" && <QuestionCard family={family} />}
        {(d.stage === "going" || d.stage === "offered" || d.stage === "arrived") && <FirstAid />}
        <HospitalCard d={d} room={s.room} />

        {d.hospitalAcceptedAt !== null && (
          <p className="family-line"><Icon name="users" size={16} />Family notified: Aai, Riya (app) · Uncle (SMS link)</p>
        )}

        {family && d.hospitalAcceptedAt !== null && (
          <a className="btn2 btn2-light btn2-full" href={`https://www.google.com/maps/search/${encodeURIComponent(hospitalInfo(d.hospitalId).h.name)}`} target="_blank" rel="noreferrer">
            <Icon name="compass" size={18} />I'm going to the hospital
          </a>
        )}
        {!family && <button className="link-btn danger center-block" onClick={() => setCancelOpen(true)}>Cancel emergency</button>}
        <div className="row-c"><SimTag /></div>
      </div>

      <ReasonDialog
        open={cancelOpen} title="Cancel this emergency?" reasons={REASONS.cancel} confirmLabel="Cancel emergency" danger
        onClose={() => setCancelOpen(false)}
        onConfirm={(r) => { actions.cancel(r); setCancelOpen(false); toast("Emergency cancelled"); }}
      />
    </>
  );
}

/* P16 · Handed over / summary */
function Summary({ family }: { family?: boolean }) {
  const nav = useNavigate();
  const { s, d, actions } = useDemoActions();
  const [stars, setStars] = useState(0);
  const info = hospitalInfo(d.hospitalId, s.room);
  const who = whoLabel(s.forWhom);
  return (
    <>
      <TopBar title="Summary" back="/app" />
      <div className="pad">
        <motion.span className="big-check" initial={{ scale: 0 }} animate={{ scale: 1 }}><Icon name="check" size={42} stroke={2.6} /></motion.span>
        <h1 className="ptitle center">{who === "you" ? "You are" : `${who.charAt(0).toUpperCase() + who.slice(1)} is`} with the doctors</h1>
        <div className="card">
          <div className="kv">
            <div><span>Hospital</span><b>{info.h.name}</b></div>
            <div><span>Room</span><b>{info.room}</b></div>
            <div><span>Receiving team</span><b>{info.team}</b></div>
            <div><span>Handed over</span><b>{clock(d.received)}</b></div>
          </div>
        </div>
        <div className="card">
          <p className="card-k">Timeline</p>
          <ul className="timeline">
            <li><span>Requested</span><b>{clock(s.sosAt)}</b></li>
            <li><span>Ambulance</span><b>{clock(d.accepted)}</b></li>
            <li><span>Picked up</span><b>{clock(d.confirmed)}</b></li>
            <li><span>Arrived</span><b>{clock(d.doorAt)}</b></li>
            <li><span>Handed over</span><b>{clock(d.received)}</b></li>
          </ul>
        </div>
        <div className="row-2">
          <a className="btn2 btn2-light" href={`https://www.google.com/maps/search/${encodeURIComponent(info.h.name)}`} target="_blank" rel="noreferrer"><Icon name="compass" size={18} />Directions</a>
          <CallButton label="Call ER" number={info.er} />
        </div>
        {!family && (
          <div className="card center">
            <p className="card-k">How was the help? (optional)</p>
            <div className="stars">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} aria-label={`${n} stars`} className={n <= stars ? "on" : ""} onClick={() => setStars(n)}><Icon name="star" size={28} /></button>
              ))}
            </div>
          </div>
        )}
        <button className="btn2 btn2-dark btn2-full btn2-lg" onClick={() => { if (!family) actions.close(); nav("/app"); }}>Done</button>
      </div>
    </>
  );
}

export default function Live({ family }: { family?: boolean }) {
  const nav = useNavigate();
  const { s, d } = useDemoActions();

  if (!d.active && d.stage !== "cancelled") {
    return (
      <Screen bottom={<Call108 />}>
        <TopBar title="Emergency" back="/app" />
        <div className="pad"><div className="empty"><p>There's no active emergency right now.</p><button className="btn2 btn2-dark" onClick={() => nav("/app")}>Go to Home</button></div></div>
      </Screen>
    );
  }
  if (d.stage === "cancelled") {
    return (
      <Screen bottom={<Call108 />}>
        <TopBar title="Emergency cancelled" back="/app" />
        <div className="pad"><div className="empty"><p>Cancelled: {s.cancelReason.toLowerCase()}. The ambulance and hospital were told.</p><button className="btn2 btn2-dark" onClick={() => nav("/app")}>Go to Home</button></div></div>
      </Screen>
    );
  }
  if (d.stage === "sending") return <Screen><Sending /></Screen>;
  if (d.stage === "requested") return <Screen><Requested who={whoLabel(s.forWhom)} /></Screen>;
  if (d.stage === "handedOver") return <Screen><Summary family={family} /></Screen>;

  return (
    <Screen bottom={<Call108 />}>
      <LiveBody family={family} />
    </Screen>
  );
}
