import LanguageMenu from "./LanguageMenu";
import { useI18n } from "../i18n/context";

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
          <a href="#/demo" className="btn btn-light btn-sm demo-mobile">{t.nav.demo}</a>
          <a href="#top" className="btn btn-dark btn-sm">{t.nav.getHelp}</a>
        </div>
      </div>
    </header>
  );
}
