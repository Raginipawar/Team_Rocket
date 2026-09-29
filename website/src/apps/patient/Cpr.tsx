import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import Icon from "../../ui/Icon";
import { CPR } from "../../demo/data";
import { useDemoActions } from "../../demo/actions";
import { speak } from "./speech";

const BPM = 110;

/* P14 · Hands-only CPR guide (full screen) */
export default function Cpr() {
  const nav = useNavigate();
  const { d } = useDemoActions();
  const [running, setRunning] = useState(false);
  const [count, setCount] = useState(0);
  const [voice, setVoice] = useState(true);
  const ctx = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (!running) return;
    if (!ctx.current) ctx.current = new AudioContext();
    const ac = ctx.current;
    const beat = () => {
      setCount((c) => c + 1);
      const o = ac.createOscillator();
      const g = ac.createGain();
      o.frequency.value = 880;
      g.gain.setValueAtTime(0.25, ac.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.08);
      o.connect(g).connect(ac.destination);
      o.start();
      o.stop(ac.currentTime + 0.09);
    };
    beat();
    const id = setInterval(beat, 60000 / BPM);
    return () => clearInterval(id);
  }, [running]);

  useEffect(() => {
    if (!running || !voice) return;
    speak("Push hard and fast in the centre of the chest.");
    const id = setInterval(() => speak("Push. Push. Keep going."), 12000);
    return () => clearInterval(id);
  }, [running, voice]);

  useEffect(() => () => { ctx.current?.close(); window.speechSynthesis?.cancel(); }, []);

  return (
    <div className="cpr">
      <header className="cpr-top">
        <h1>{CPR.title}</h1>
        <button className="icon-btn light" aria-label="Close" onClick={() => nav(-1)}><Icon name="x" /></button>
      </header>
      <div className="cpr-eta">Ambulance: {d.accepted && d.stage === "going" ? `${d.etaMin} min` : d.arrivedAt ? "arrived" : "on the way"}</div>

      <button className="cpr-circle" onClick={() => setRunning((r) => !r)} aria-label={running ? "Pause metronome" : "Start metronome"}>
        <motion.span
          key={count}
          initial={{ scale: 1 }}
          animate={running ? { scale: [1.12, 1] } : { scale: 1 }}
          transition={{ duration: 0.35 }}
        />
        <b>{running ? "Push… push…" : "Tap to start"}</b>
        <small>{running ? `${BPM} per minute` : "Beats at 110 per minute"}</small>
      </button>
      <p className="cpr-count">{count} compressions</p>

      <ol className="cpr-steps">{CPR.steps.map((s) => <li key={s}>{s}</li>)}</ol>

      <div className="cpr-actions">
        <button className="btn2 btn2-ghost-light" onClick={() => setVoice((v) => !v)}><Icon name="speaker" size={18} />Voice guidance {voice ? "on" : "off"}</button>
        <a className="btn2 btn2-red" href="tel:108"><Icon name="phone" size={18} />Call 108</a>
      </div>
    </div>
  );
}
