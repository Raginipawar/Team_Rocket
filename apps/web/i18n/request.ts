import { getRequestConfig } from "next-intl/server";
import { cookies, headers } from "next/headers";

// i18n (technical.md §16.1): en / hi / mr with next-intl, no locale in the URL.
// The choice lives in the NEXT_LOCALE cookie; the first visit follows the phone's language.
// Missing keys fall back to English (hospital and ops screens are English-first, rule 8).

export const LOCALES = ["en", "hi", "mr"] as const;
export type Locale = (typeof LOCALES)[number];

function merge(base: Record<string, unknown>, over: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = { ...base };
  for (const [k, v] of Object.entries(over)) {
    out[k] = v && typeof v === "object" && !Array.isArray(v) && base[k] && typeof base[k] === "object" ? merge(base[k] as Record<string, unknown>, v as Record<string, unknown>) : v;
  }
  return out;
}

export default getRequestConfig(async () => {
  const store = await cookies();
  let locale = store.get("NEXT_LOCALE")?.value as Locale | undefined;
  if (!locale || !LOCALES.includes(locale)) {
    const accept = (await headers()).get("accept-language") ?? "";
    locale = LOCALES.find((l) => accept.toLowerCase().startsWith(l)) ?? "en";
  }
  const en = (await import("../lib/i18n/en.json")).default;
  const own = locale === "en" ? en : (await import(`../lib/i18n/${locale}.json`)).default;
  return { locale, messages: merge(en, own) as typeof en };
});
