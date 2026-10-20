import { motion } from "framer-motion";
import PhoneFrame from "./PhoneFrame";
import { AskScreen, HospitalReadyScreen, OnTheWayScreen } from "./Screens";
import { EASE } from "./motion";
import { useI18n } from "../i18n/context";

export default function Hero() {
  const { t } = useI18n();
  return (
    <section className="hero" id="top">
      <div className="page">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: EASE }}
        >
          <h1>{t.hero.title1}<br />{t.hero.title2}</h1>
          <p className="lead">{t.hero.lead}</p>
          <div className="hero-ctas hero-ctas-stack">
            <a href="/apps" className="btn btn-red">{t.nav.liveApp}</a>
            <a href="#how" className="btn btn-light">{t.hero.ctaHow}</a>
          </div>
          <a href="tel:108" className="hero-note hero-note-link">{t.hero.ctaCall}</a>
        </motion.div>

        <div className="hero-phones">
          <div className="side"><PhoneFrame label={t.how.steps[0].title} delay={0.15}><AskScreen /></PhoneFrame></div>
          <PhoneFrame label={t.screens.way.small}><OnTheWayScreen /></PhoneFrame>
          <div className="side"><PhoneFrame label={t.screens.ready.small} delay={0.3}><HospitalReadyScreen /></PhoneFrame></div>
        </div>
      </div>
    </section>
  );
}
