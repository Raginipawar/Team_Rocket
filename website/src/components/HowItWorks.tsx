import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import PhoneFrame from "./PhoneFrame";
import Reveal from "./Reveal";
import { AskScreen, HospitalReadyScreen, OnTheWayScreen, UnderstandScreen } from "./Screens";
import { EASE } from "./motion";
import { useI18n } from "../i18n/context";

const SCREENS = [<AskScreen key="a" />, <UnderstandScreen key="u" />, <OnTheWayScreen key="w" />, <HospitalReadyScreen key="h" />];
const STEP_MS = 4500;

export default function HowItWorks() {
  const { t } = useI18n();
  const [active, setActive] = useState(0);

  useEffect(() => {
    const id = setTimeout(() => setActive((a) => (a + 1) % SCREENS.length), STEP_MS);
    return () => clearTimeout(id);
  }, [active]);

  return (
    <section className="section" id="how">
      <div className="page">
        <Reveal className="section-head">
          <h2>{t.how.title}</h2>
          <p className="lead">{t.how.lead}</p>
        </Reveal>

        <div className="how">
          <div className="steps">
            {t.how.steps.map((s, i) => (
              <button key={i} className={`step${i === active ? " active" : ""}`} onClick={() => setActive(i)}>
                <span className="step-num">{i + 1}</span>
                <span>
                  <span className="step-title">{s.title}</span>
                  <span className="step-desc">{s.desc}</span>
                  {i === active && (
                    <span className="step-bar" style={{ display: "block" }}>
                      <motion.span
                        key={active}
                        initial={{ width: "0%" }}
                        animate={{ width: "100%" }}
                        transition={{ duration: STEP_MS / 1000, ease: "linear" }}
                      />
                    </span>
                  )}
                </span>
              </button>
            ))}
          </div>

          <div className="how-phone">
            <PhoneFrame label={t.how.steps[active].title}>
              <AnimatePresence mode="wait">
                <motion.div
                  key={active}
                  className="scr-wrap"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.35, ease: EASE }}
                >
                  {SCREENS[active]}
                </motion.div>
              </AnimatePresence>
            </PhoneFrame>
          </div>
        </div>
      </div>
    </section>
  );
}
