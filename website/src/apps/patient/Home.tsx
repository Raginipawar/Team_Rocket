import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import Icon from "../../ui/Icon";
import { Avatar } from "../../ui/Bits";
import { PEOPLE } from "../../demo/data";
import { useDemoActions } from "../../demo/actions";
import { Call108, Screen, TopBar } from "./layout";
import { getLocation, saveLocation, whoLabel } from "./people";
import { getSession } from "./session";

const vibrate = (ms: number | number[]) => { try { navigator.vibrate?.(ms); } catch { /* not supported */ } };

/* ---------------- P7 · Home (SOS) ---------------- */
export function Home() {
  const nav = useNavigate();
  const loc = useLocation();
  const { s, d, actions } = useDemoActions();
  const pre = (loc.state as { forWhom?: string } | null)?.forWhom;
  const [who, setWho] = useState<string>(pre ?? "rahul");
  const [hold, setHold] = useState(0);
  const [hint, setHint] = useState("");
  const raf = useRef<number>(0);
  const started = useRef(0);
  const name = getSession()?.name ?? "Rahul";
  const liveBanner = d.active && d.stage !== "handedOver" && d.stage !== "cancelled";

  const stop = () => cancelAnimationFrame(raf.current);
  const begin = () => {
    setHint("");
    started.current = performance.now();
    vibrate(20);
    const tick = (t: number) => {
      const p = Math.min(1, (t - started.current) / 1000);
      setHold(p);
      if (p >= 1) {
        vibrate([60, 40, 60]);
        actions.sos(who, "button");
        nav("/app/live");
        return;
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
  };
  const end = () => {
    stop();
    if (hold < 1 && hold > 0) setHint("Hold for 1 second");
    setHold(0);
  };
  useEffect(() => stop, []);

  const chips = [
    { id: "rahul", label: "Me", name: "Rahul Kulkarni" },
    ...PEOPLE.filter((p) => p.id !== "rahul").map((p) => ({ id: p.id, label: p.short, name: p.name })),
    { id: "someone", label: "Someone else", name: "" },
  ];

  return (
    <Screen tabs bottom={<Call108 />}>
      <TopBar
        title={`Hi ${name}`}
        right={
          <>
            <button className="icon-btn" aria-label="Language" onClick={() => nav("/app/settings")}><Icon name="globe" /></button>
            <button className="icon-btn has-dot" aria-label="Notifications" onClick={() => nav("/app/notifications")}><Icon name="bell" /></button>
          </>
        }
      />
      <div className="pad">
        {liveBanner && (
          <button className="live-banner" onClick={() => nav("/app/live")}>
            <span className="pulse-dot red" />
            <span><b>{whoLabel(s.forWhom) === "you" ? "Your" : `${whoLabel(s.forWhom)}'s`} emergency is live</b> · {d.accepted ? `Ambulance arriving in ${d.etaMin || 1} min` : "Finding an ambulance"}</span>
            <Icon name="chevron" size={18} />
          </button>
        )}

        <p className="lbl-t">Who needs help?</p>
        <div className="who" role="radiogroup">
          {chips.map((c) => (
            <button key={c.id} role="radio" aria-checked={who === c.id} className={`who-chip${who === c.id ? " on" : ""}`} onClick={() => setWho(c.id)}>
              {c.id === "someone" ? <span className="avatar-c who-plus"><Icon name="userPlus" size={16} /></span> : <Avatar name={PEOPLE.find((p) => p.id === c.id)?.short ?? c.label} size={30} managed={c.id === "aaji"} />}
              {c.label}
            </button>
          ))}
        </div>
        <p className="help small">{who === "someone" ? "No profile will be attached. Good for strangers and road accidents." : "Their health profile will be shared with the ambulance and hospital."}</p>

        <div className="sos-wrap">
          <button
            className="sos-big" aria-label="SOS, press and hold for one second"
            onPointerDown={begin} onPointerUp={end} onPointerLeave={end} onPointerCancel={end}
            onKeyDown={(e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) begin(); }}
            onKeyUp={end}
          >
            <svg className="sos-ring" viewBox="0 0 220 220" aria-hidden="true">
              <circle cx="110" cy="110" r="104" fill="none" stroke="rgba(239,68,68,.18)" strokeWidth="8" />
              <circle cx="110" cy="110" r="104" fill="none" stroke="#ef4444" strokeWidth="8" strokeLinecap="round"
                strokeDasharray={653} strokeDashoffset={653 * (1 - hold)} transform="rotate(-90 110 110)" />
            </svg>
            <motion.span className="sos-core" animate={hold > 0 ? { scale: 0.96 } : { scale: [1, 1.03, 1] }} transition={hold > 0 ? { duration: 0.1 } : { duration: 1.8, repeat: Infinity }}>
              <b>SOS</b><small>Press and hold</small>
            </motion.span>
          </button>
          <p className="sos-hint" aria-live="polite">{hint}</p>
        </div>

        <div className="row-2">
          <button className="way" onClick={() => nav("/app/speak", { state: { forWhom: who } })}><Icon name="mic" size={22} /><span><b>Speak</b><small>Tell us what happened</small></span></button>
          <button className="way" onClick={() => nav("/app/type", { state: { forWhom: who } })}><Icon name="keyboard" size={22} /><span><b>Type</b><small>Write what happened</small></span></button>
        </div>

        <div className="loc-strip">
          <Icon name="pin" size={20} />
          <span><b>{getLocation()}</b><small className="ok-text">Accurate to 20 m</small></span>
          <button className="link-btn" onClick={() => nav("/app/location")}>Change</button>
        </div>
      </div>
    </Screen>
  );
}

/* ---------------- P8 · Speak ---------------- */
export function Speak() {
  const nav = useNavigate();
  const loc = useLocation();
  const forWhom = (loc.state as { forWhom?: string } | null)?.forWhom ?? "papa";
  const { actions } = useDemoActions();
  const [state, setState] = useState<"idle" | "rec" | "denied">("idle");
  const [secs, setSecs] = useState(0);
  const [levels, setLevels] = useState<number[]>(Array(28).fill(0.08));
  const rec = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<number>(0);
  const anim = useRef<number>(0);

  const cleanup = () => {
    clearInterval(timer.current);
    cancelAnimationFrame(anim.current);
    stream.current?.getTracks().forEach((t) => t.stop());
  };
  useEffect(() => cleanup, []);

  const send = () => {
    if (rec.current?.state === "recording") rec.current.stop();
    cleanup();
    vibrate([60, 40, 60]);
    actions.sos(forWhom, "voice");
    nav("/app/live");
  };

  const start = async () => {
    try {
      const st = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = st;
      const mr = new MediaRecorder(st);
      rec.current = mr;
      mr.start();
      const ctx = new AudioContext();
      const an = ctx.createAnalyser();
      an.fftSize = 64;
      ctx.createMediaStreamSource(st).connect(an);
      const buf = new Uint8Array(an.frequencyBinCount);
      const draw = () => {
        an.getByteFrequencyData(buf);
        const avg = buf.reduce((a, b) => a + b, 0) / buf.length / 255;
        setLevels((l) => [...l.slice(1), Math.max(0.08, Math.min(1, avg * 2.2))]);
        anim.current = requestAnimationFrame(draw);
      };
      draw();
      setSecs(0);
      setState("rec");
      timer.current = window.setInterval(() => setSecs((x) => x + 1), 1000);
    } catch {
      setState("denied");
    }
  };

  useEffect(() => { if (secs >= 60) send(); }); // auto-stop at 60 s

  return (
    <Screen bottom={<Call108 compact />}>
      <TopBar title="Tell us what happened" back />
      <div className="pad">
        <div className="hint-box">Say: what happened · who it is · a nearby landmark. Any language is fine.</div>
        <div className="chips-wrap">
          <span className="pick ghost">"Papa has chest pain…"</span>
          <span className="pick ghost">"Accident near…"</span>
        </div>

        {state === "denied" ? (
          <div className="denied">
            <Icon name="mic" size={28} />
            <p>Microphone is off. Type instead or allow microphone.</p>
            <div className="row-2">
              <button className="btn2 btn2-dark" onClick={() => nav("/app/type", { state: { forWhom } })}>Type instead</button>
              <button className="btn2 btn2-light" onClick={start}>Allow microphone</button>
            </div>
          </div>
        ) : (
          <div className="recorder">
            <div className="wave" aria-hidden="true">
              {levels.map((l, i) => <span key={i} style={{ height: `${l * 100}%` }} />)}
            </div>
            <p className={`rec-time${secs >= 50 ? " warn" : ""}`}>
              {state === "rec" ? `0:${String(secs).padStart(2, "0")} / 1:00` : "0:00 / 1:00"}
              {secs >= 50 && " · 10 seconds left"}
            </p>
            {state === "idle" ? (
              <button className="mic-big" onClick={start} aria-label="Start recording"><Icon name="mic" size={40} /></button>
            ) : (
              <div className="row-2">
                <button className="btn2 btn2-light" onClick={() => { cleanup(); nav(-1); }}><Icon name="x" size={18} />Cancel</button>
                <button className="btn2 btn2-red" onClick={send}><Icon name="stop" size={18} />Stop &amp; send</button>
              </div>
            )}
          </div>
        )}
      </div>
    </Screen>
  );
}

/* ---------------- P9 · Type ---------------- */
export function TypeReport() {
  const nav = useNavigate();
  const loc = useLocation();
  const forWhom = (loc.state as { forWhom?: string } | null)?.forWhom ?? "papa";
  const { actions } = useDemoActions();
  const [text, setText] = useState("");
  return (
    <Screen bottom={<Call108 compact />}>
      <TopBar title="Tell us what happened" back />
      <div className="pad">
        <textarea
          className="field big-text" rows={7} maxLength={1000} autoFocus value={text} onChange={(e) => setText(e.target.value)}
          placeholder="e.g. My father has chest pain and is sweating, near Ganesh temple Akurdi"
        />
        <p className="counter">{text.length} / 1000</p>
        <button className="btn2 btn2-red btn2-full btn2-lg" disabled={!text.trim()} onClick={() => { actions.sos(forWhom, "text", text); nav("/app/live"); }}>
          Send for help
        </button>
      </div>
    </Screen>
  );
}

/* ---------------- P10 · Adjust location ---------------- */
const LANDMARKS = [
  "Ganesh Temple, Sector 26, Akurdi", "Akurdi Railway Station", "Pradhikaran Main Road, Nigdi", "Bhakti Shakti Chowk, Nigdi",
  "Chinchwad Station Road", "Pimpri Chowk", "Dange Chowk, Wakad", "Ravet BRTS Stop", "Bhosari MIDC Gate", "Dehu Road Market",
];

export function AdjustLocation() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [pin, setPin] = useState({ x: 50, y: 48 });
  const [label, setLabel] = useState(getLocation());
  const [locating, setLocating] = useState(false);
  const dragging = useRef(false);
  const box = useRef<HTMLDivElement>(null);
  const sugg = q.trim() ? LANDMARKS.filter((l) => l.toLowerCase().includes(q.toLowerCase())).slice(0, 5) : [];

  const move = (e: React.PointerEvent) => {
    if (!dragging.current || !box.current) return;
    const r = box.current.getBoundingClientRect();
    setPin({ x: Math.min(95, Math.max(5, ((e.clientX - r.left) / r.width) * 100)), y: Math.min(92, Math.max(8, ((e.clientY - r.top) / r.height) * 100)) });
    setLabel("Dropped pin near Akurdi");
  };
  const useCurrent = () => {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (p) => { setLocating(false); setLabel(`Your location (${p.coords.latitude.toFixed(4)}, ${p.coords.longitude.toFixed(4)})`); setPin({ x: 50, y: 48 }); },
      () => setLocating(false),
      { timeout: 8000 }
    );
  };

  return (
    <Screen bottom={
      <div className="pad-x row-2">
        <button className="btn2 btn2-light" onClick={useCurrent}>{locating ? "Finding you…" : "Use my current location"}</button>
        <button className="btn2 btn2-dark" onClick={() => { saveLocation(label); nav(-1); }}>Use this location</button>
      </div>
    }>
      <TopBar title="Adjust location" back />
      <div className="pad">
        <div className="search">
          <Icon name="search" size={18} />
          <input placeholder="Type a landmark, road or area" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search landmark" />
        </div>
        {sugg.length > 0 && (
          <div className="sugg">
            {sugg.map((s) => <button key={s} onClick={() => { setLabel(s); setQ(""); setPin({ x: 30 + Math.random() * 40, y: 30 + Math.random() * 40 }); }}><Icon name="pin" size={16} />{s}</button>)}
          </div>
        )}
        <div className="drag-map" ref={box} onPointerMove={move} onPointerUp={() => (dragging.current = false)} onPointerLeave={() => (dragging.current = false)}>
          <svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            <rect width="400" height="300" fill="#f4f4f2" />
            <path d="M0 80 H400 M0 200 H400 M90 0 V300 M260 0 V300 M0 280 L400 30" stroke="#e4e4e0" strokeWidth="12" fill="none" />
            <text x="100" y="70" fontSize="12" fill="#9a9a95">Pradhikaran</text>
            <text x="270" y="190" fontSize="12" fill="#9a9a95">Akurdi</text>
          </svg>
          <div className="drag-pin" style={{ left: `${pin.x}%`, top: `${pin.y}%` }} onPointerDown={(e) => { dragging.current = true; (e.target as Element).setPointerCapture?.(e.pointerId); }}>
            <span className="acc" />
            <Icon name="pin" size={34} stroke={2} />
          </div>
          <span className="map-sim">Simulated</span>
        </div>
        <div className="loc-strip"><Icon name="pin" size={20} /><span><b>{label}</b><small>Drag the pin to the exact spot</small></span></div>
      </div>
    </Screen>
  );
}

