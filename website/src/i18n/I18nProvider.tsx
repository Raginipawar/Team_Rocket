import { useEffect, useMemo, useState, type ReactNode } from "react";
import { DICTS, I18nContext, readInitialLang, saveLang } from "./context";
import type { Lang } from "./types";

export default function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readInitialLang);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = DICTS[lang].metaTitle;
  }, [lang]);

  const value = useMemo(
    () => ({
      lang,
      t: DICTS[lang],
      setLang: (l: Lang) => {
        setLangState(l);
        saveLang(l);
      },
    }),
    [lang]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
