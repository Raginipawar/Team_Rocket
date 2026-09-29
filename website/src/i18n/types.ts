// Every language file must fill this shape exactly; TypeScript fails the build if a line is missing.

export type Lang = "en" | "hi" | "mr" | "te" | "ta" | "gu";

interface TitleDesc {
  title: string;
  desc: string;
}

export interface Dict {
  langName: string;
  metaTitle: string;
  nav: { how: string; features: string; faq: string; getHelp: string; language: string; demo: string };
  hero: { title1: string; title2: string; lead: string; ctaHow: string; ctaCall: string; note: string };
  screens: {
    ask: { place: string; title: string; hold: string; speak: string; type: string; call: string };
    understand: { small: string; title: string; age: string; ageVal: string; pain: string; painVal: string; blood: string; finding: string };
    way: { small: string; title: string };
    ready: { small: string; title: string; goTo: string; gate: string; room: string; roomVal: string; doctor: string; doctorVal: string; family: string };
    crew: { small: string; title: string; case: string; where: string; accept: string; skip: string };
    hosp: { small: string; title: string; man: string; note: string; heartDoc: string; cathLab: string; accept: string; decline: string };
  };
  how: { title: string; lead: string; steps: [TitleDesc, TitleDesc, TitleDesc, TitleDesc] };
  duo: { title: string; lead: string; crewTitle: string; crewDesc: string; hospTitle: string; hospDesc: string };
  why: { title: string; lead: string; showAll: string; hide: string };
  highlights: TitleDesc[];
  features: TitleDesc[];
  safe: { title: string; lead: string; items: [TitleDesc, TitleDesc, TitleDesc, TitleDesc] };
  coverage: { title: string; lead: string };
  localities: string[];
  faqTitle: string;
  faq: { q: string; a: string }[];
  closing: { title: string; lead: string; cta: string; call: string };
  footer: string;
  track: {
    title: string; ambulanceFor: string; steps: string[]; min: string; to: string; arrived: string; ambulance: string;
    hospital: string; gate: string; room: string; team: string; directions: string; callEr: string; choosing: string;
    finding: string; changed: string; final: string; call108: string; getApp: string; expired: string; noMedical: string;
  };
}
