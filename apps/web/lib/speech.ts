"use client";

// Read-aloud for follow-up questions and first-aid steps. The ML service's TTS audio
// (§9.18) is used when the server sends an audio_url; otherwise the phone's own voice.

let current: HTMLAudioElement | null = null;

const LANG_TAG: Record<string, string> = { en: "en-IN", hi: "hi-IN", mr: "mr-IN" };

export function stopSpeaking() {
  current?.pause();
  current = null;
  if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
}

export function speak(text: string | string[], lang = "en", audioUrl?: string | null): Promise<void> {
  stopSpeaking();
  if (audioUrl) {
    return new Promise((resolve) => {
      const a = new Audio(audioUrl);
      current = a;
      a.onended = () => resolve();
      a.onerror = () => void speakSynth(text, lang).then(resolve);
      a.play().catch(() => void speakSynth(text, lang).then(resolve));
    });
  }
  return speakSynth(text, lang);
}

function speakSynth(text: string | string[], lang: string): Promise<void> {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return Promise.resolve();
  const parts = Array.isArray(text) ? text : [text];
  const tag = LANG_TAG[lang] ?? "en-IN";
  const voices = window.speechSynthesis.getVoices();
  const voice = voices.find((v) => v.lang === tag) ?? voices.find((v) => v.lang.startsWith(tag.slice(0, 2))) ?? null;
  return new Promise((resolve) => {
    parts.forEach((p, i) => {
      const u = new SpeechSynthesisUtterance(p);
      u.lang = tag;
      if (voice) u.voice = voice;
      u.rate = 0.92;
      if (i === parts.length - 1) u.onend = () => resolve();
      window.speechSynthesis.speak(u);
    });
  });
}

type Recognition = {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: (() => void) | null; onend: (() => void) | null; start: () => void; stop: () => void;
};

/** Live transcript while recording, where the browser supports it (sent as `text` alongside the audio). */
export function startTranscript(lang: string, onText: (t: string) => void): (() => void) | null {
  const W = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
  const Ctor = W.SpeechRecognition ?? W.webkitSpeechRecognition;
  if (!Ctor) return null;
  const r = new Ctor();
  r.lang = LANG_TAG[lang] ?? "en-IN";
  r.continuous = true;
  r.interimResults = true;
  r.onresult = (e) => {
    let s = "";
    for (let i = 0; i < e.results.length; i++) s += e.results[i][0].transcript + " ";
    onText(s.trim());
  };
  r.onerror = () => {};
  try {
    r.start();
  } catch {
    return null;
  }
  return () => {
    try {
      r.stop();
    } catch {
      /* already stopped */
    }
  };
}
