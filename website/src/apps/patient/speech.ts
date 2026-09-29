// Real browser speech: read text aloud, and (where supported) listen for a yes / no answer.

export function speak(text: string) {
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-IN";
    u.rate = 0.95;
    window.speechSynthesis.speak(u);
  } catch {
    /* speech not available */
  }
}

interface MiniRecognition {
  lang: string;
  interimResults: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
}

export function canListen() {
  const w = window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown };
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

/** Listens once and maps the reply (English, Hindi or Marathi words) to Yes / No. */
export function listenYesNo(onAnswer: (a: "Yes" | "No" | null, heard: string) => void) {
  const w = window as unknown as { SpeechRecognition?: new () => MiniRecognition; webkitSpeechRecognition?: new () => MiniRecognition };
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  if (!Ctor) return onAnswer(null, "");
  const r = new Ctor();
  r.lang = "en-IN";
  r.interimResults = false;
  let done = false;
  r.onresult = (e) => {
    const heard = (e.results[0]?.[0]?.transcript ?? "").toLowerCase();
    done = true;
    const yes = /\b(yes|yeah|haan|ha|ho|hoy|हाँ|हां|होय|हो)\b/.test(heard);
    const no = /\b(no|nahi|nahin|nako|नहीं|नाही)\b/.test(heard);
    onAnswer(yes && !no ? "Yes" : no ? "No" : null, heard);
  };
  r.onerror = () => { if (!done) { done = true; onAnswer(null, ""); } };
  r.onend = () => { if (!done) onAnswer(null, ""); };
  r.start();
}
