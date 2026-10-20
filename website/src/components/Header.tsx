import LanguageMenu from "./LanguageMenu";
import { useI18n } from "../i18n/context";

// Was an external vercel.app URL opened in a new tab -- once this site is
// served from the same domain as the real app (via a reverse-proxy
// rewrite on the app's own Next.js config), the real app's own routes
// live on THIS domain too, so this is just a same-origin relative link now.
// /login alone defaults to role=patient (no role picker), skipping
// straight to a patient phone-number screen with no way to say "I'm an
// ambulance crew" or "I'm hospital staff" -- /apps is the real role
// picker (patient/ambulance/hospital cards), each card's own route then
// bounces to the correctly-roled /login itself if not signed in.
const LIVE_APP_URL = "/apps";

export default function Header() {
  const { t } = useI18n();
  return (
    <header className="header">
      <div className="page header-inner">
        <a href="#top" className="logo" aria-label="GoldenHour">
          <span className="logo-dot" aria-hidden="true">+</span>
          GoldenHour
        </a>
        <nav className="nav" aria-label="Primary">
          <a href="#how">{t.nav.how}</a>
          <a href="#features">{t.nav.features}</a>
          <a href="#faq">{t.nav.faq}</a>
          <a href="#/demo" className="nav-demo">{t.nav.demo}</a>
        </nav>
        <div className="header-right">
          <LanguageMenu />
          <a href={LIVE_APP_URL} className="btn btn-red btn-sm" style={{ textTransform: "uppercase", letterSpacing: "0.02em" }}>{t.nav.liveApp}</a>
          <a href="#/demo" className="btn btn-light btn-sm demo-mobile">{t.nav.demo}</a>
          <a href="#top" className="btn btn-dark btn-sm">{t.nav.getHelp}</a>
        </div>
      </div>
    </header>
  );
}
