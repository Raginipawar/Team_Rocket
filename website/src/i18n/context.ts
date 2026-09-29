import { createContext, useContext } from "react";
import type { Dict, Lang } from "./types";
import en from "./en";
import hi from "./hi";
import mr from "./mr";
import te from "./te";
import ta from "./ta";
import gu from "./gu";

export const DICTS: Record<Lang, Dict> = { en, hi, mr, te, ta, gu };
export const LANGS: Lang[] = ["en", "hi", "mr", "te", "ta", "gu"];

export interface I18nValue {
  lang: Lang;
  t: Dict;
  setLang: (l: Lang) => void;
}

export const I18nContext = createContext<I18nValue>({ lang: "en", t: en, setLang: () => {} });

export const useI18n = () => useContext(I18nContext);

const STORAGE_KEY = "gh-lang";

export function readInitialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && (LANGS as string[]).includes(saved)) return saved as Lang;
  } catch {
    /* storage can be blocked; fall through */
  }
  const browser = (navigator.language || "en").slice(0, 2).toLowerCase();
  return (LANGS as string[]).includes(browser) ? (browser as Lang) : "en";
}

export function saveLang(l: Lang) {
  try {
    localStorage.setItem(STORAGE_KEY, l);
  } catch {
    /* ignore */
  }
}
