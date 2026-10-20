"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import { startTranscript } from "@/lib/speech";
import { mmss } from "@/lib/format";

/** MediaRecorder, max 60 s, with a live waveform (§16.2). Also keeps a browser transcript when available. */
export default function VoiceRecorder({ onDone, busy }: { onDone: (audio: Blob, transcript: string) => void; busy?: boolean }) {
  const t = useTranslations("patient");
  const locale = useLocale();
  const [state, setState] = useState<"idle" | "rec" | "blocked">("idle");
  const [secs, setSecs] = useState(0);
  const [text, setText] = useState("");
  const [liveCaptionsSupported, setLiveCaptionsSupported] = useState(true);
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const canvas = useRef<HTMLCanvasElement>(null);
  const stopAll = useRef<() => void>(() => {});

  useEffect(() => () => stopAll.current(), []);

  const start = async () => {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setState("blocked");
      return;
    }
    chunks.current = [];
    const type = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg", "audio/mp4"].find((m) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(m));
    const r = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
    r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
    r.start(250);
    rec.current = r;
    setState("rec");
    setSecs(0);
    setText("");
    const stopTx = startTranscript(locale, setText);
    setLiveCaptionsSupported(stopTx !== null);
    // waveform
    const ctx = new AudioContext();
    const src = ctx.createMediaStreamSource(stream);
    const an = ctx.createAnalyser();
    an.fftSize = 512;
    src.connect(an);
    const data = new Uint8Array(an.frequencyBinCount);
    let raf = 0;
    const draw = () => {
      const c = canvas.current;
      if (c) {
        const g = c.getContext("2d")!;
        an.getByteTimeDomainData(data);
        g.clearRect(0, 0, c.width, c.height);
        g.lineWidth = 4;
        g.strokeStyle = "#dc2626";
        g.lineCap = "round";
        g.beginPath();
        for (let i = 0; i < data.length; i++) {
          const x = (i / (data.length - 1)) * c.width;
          const y = (data[i] / 255) * c.height;
          if (i === 0) g.moveTo(x, y);
          else g.lineTo(x, y);
        }
        g.stroke();
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    const began = Date.now();
    const timer = setInterval(() => {
      const s = Math.floor((Date.now() - began) / 1000);
      setSecs(s);
      if (s >= 60) finish();
    }, 250);
    stopAll.current = () => {
      // finish()'s r.onstop and the unmount cleanup below both call this --
      // not resetting to a no-op after the first call meant ctx.close() ran
      // twice, throwing "Cannot close a closed AudioContext" on navigation
      // away right after sending.
      stopAll.current = () => {};
      clearInterval(timer);
      cancelAnimationFrame(raf);
      stopTx?.();
      stream.getTracks().forEach((tr) => tr.stop());
      if (ctx.state !== "closed") void ctx.close();
    };
  };

  const finish = () => {
    const r = rec.current;
    if (!r || r.state === "inactive") return;
    r.onstop = () => {
      stopAll.current();
      const blob = new Blob(chunks.current, { type: r.mimeType || "audio/webm" });
      setState("idle");
      onDone(blob, text);
    };
    r.stop();
  };

  if (state === "blocked") {
    return <p className="rounded-2xl bg-amber-soft px-4 py-3 text-[17px] font-semibold text-amber">{t("micBlocked")}</p>;
  }

  return (
    <div className="flex flex-col items-center gap-4">
      <p className="text-center text-[17px] text-muted">{t("speakHelp")}</p>
      <div className="flex h-24 w-full items-center justify-center rounded-2xl bg-soft">
        {state === "rec" ? <canvas ref={canvas} width={600} height={96} className="h-24 w-full" /> : <Icon name="mic" size={40} className="text-muted" />}
      </div>
      {state === "rec" && (
        <p className="flex items-center gap-2 text-[18px] font-bold text-red-ink" aria-live="polite">
          <span className="h-3 w-3 animate-pulse rounded-full bg-red" />
          {t("recording")} · {mmss(secs)} / 1:00
        </p>
      )}
      {text && <p className="w-full rounded-2xl border border-line px-4 py-3 text-[17px]">&ldquo;{text}&rdquo;</p>}
      {state === "rec" && !text && !liveCaptionsSupported && (
        <p className="text-[14px] text-muted">Live captions aren&apos;t available on this device -- your recording is still being sent and transcribed normally.</p>
      )}
      {state === "idle" ? (
        <Button size="xl" variant="danger" block onClick={start} loading={busy}><Icon name="mic" size={26} />{t("startRecording")}</Button>
      ) : (
        <Button size="xl" variant="primary" block onClick={finish}><Icon name="stop" size={24} />{t("stopAndSend")}</Button>
      )}
      <p className="text-[15px] text-muted">{t("maxSeconds")}</p>
    </div>
  );
}
