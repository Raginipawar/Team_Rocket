import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import PhoneFrame from "./PhoneFrame";
import Reveal from "./Reveal";
import { CrewScreen, HospitalScreen } from "./Screens";
import { EASE } from "./motion";
import { useI18n } from "../i18n/context";

export function TwoApps() {
  const { t } = useI18n();
  return (
    <section className="section">
      <div className="page">
        <Reveal className="section-head">
          <h2>{t.duo.title}</h2>
          <p className="lead">{t.duo.lead}</p>
        </Reveal>
        <div className="duo">
          <Reveal className="duo-card">
            <h3>{t.duo.crewTitle}</h3>
            <p>{t.duo.crewDesc}</p>
            <div className="phone-holder"><PhoneFrame label={t.duo.crewTitle}><CrewScreen /></PhoneFrame></div>
          </Reveal>
          <Reveal className="duo-card" delay={0.08}>
            <h3>{t.duo.hospTitle}</h3>
            <p>{t.duo.hospDesc}</p>
            <div className="phone-holder"><PhoneFrame label={t.duo.hospTitle} delay={0.1}><HospitalScreen /></PhoneFrame></div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

export function Highlights() {
  const { t } = useI18n();
  const [showAll, setShowAll] = useState(false);
  return (
    <section className="section" id="features">
      <div className="page">
        <Reveal className="section-head">
          <h2>{t.why.title}</h2>
          <p className="lead">{t.why.lead}</p>
        </Reveal>
        <div className="cards">
          {t.highlights.map((h, i) => (
            <Reveal key={i} className="card" delay={(i % 3) * 0.06}>
              <div className="card-num">{i + 1}</div>
              <h3>{h.title}</h3>
              <p>{h.desc}</p>
            </Reveal>
          ))}
        </div>
        <div className="all-toggle">
          <button className="btn btn-light" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}>
            {showAll ? t.why.hide : t.why.showAll}
          </button>
        </div>
        <AnimatePresence initial={false}>
          {showAll && (
            <motion.div
              className="all-list"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.45, ease: EASE }}
            >
              <div className="all-grid">
                {t.features.map((f, i) => (
                  <div key={i} className="all-item">
                    <span>{i + 1}</span>
                    <div><b>{f.title}</b>{f.desc}</div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}

export function Safety() {
  const { t } = useI18n();
  return (
    <section className="section">
      <div className="page">
        <Reveal className="section-head">
          <h2>{t.safe.title}</h2>
          <p className="lead">{t.safe.lead}</p>
        </Reveal>
        <div className="safe-grid">
          {t.safe.items.map((s, i) => (
            <Reveal key={i} className="safe" delay={(i % 2) * 0.06}>
              <div><b>{s.title}</b><p>{s.desc}</p></div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Coverage() {
  const { t } = useI18n();
  return (
    <section className="section">
      <div className="page">
        <Reveal className="section-head">
          <h2>{t.coverage.title}</h2>
          <p className="lead">{t.coverage.lead}</p>
        </Reveal>
        <div className="pills">
          {t.localities.map((l, i) => (
            <motion.span
              key={i}
              className="pill"
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.03, ease: EASE }}
            >
              {l}
            </motion.span>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Faq() {
  const { t } = useI18n();
  const [open, setOpen] = useState<number | null>(null);
  return (
    <section className="section" id="faq">
      <div className="page">
        <Reveal className="section-head"><h2>{t.faqTitle}</h2></Reveal>
        <div className="faq">
          {t.faq.map((f, i) => {
            const isOpen = open === i;
            return (
              <div className="faq-item" key={i}>
                <button className="faq-q" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : i)}>
                  {f.q}
                  <span className="faq-icon" aria-hidden="true">+</span>
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      className="faq-a"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3, ease: EASE }}
                    >
                      <p>{f.a}</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function Closing() {
  const { t } = useI18n();
  return (
    <div className="page">
      <Reveal className="closing">
        <h2>{t.closing.title}</h2>
        <p>{t.closing.lead}</p>
        <div className="hero-ctas">
          <a href="#how" className="btn btn-red">{t.closing.cta}</a>
          <a href="tel:108" className="btn btn-light">{t.closing.call}</a>
        </div>
      </Reveal>
    </div>
  );
}

export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="footer">
      <div className="page footer-inner">
        <a href="#top" className="logo"><span className="logo-dot" aria-hidden="true">+</span>GoldenHour</a>
        <nav className="footer-links" aria-label="Footer">
          <a href="#how">{t.nav.how}</a>
          <a href="#features">{t.nav.features}</a>
          <a href="#faq">{t.nav.faq}</a>
        </nav>
        <span>{t.footer}</span>
      </div>
    </footer>
  );
}
