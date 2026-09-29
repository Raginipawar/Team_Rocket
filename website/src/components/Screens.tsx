import { motion } from "framer-motion";
import { useI18n } from "../i18n/context";

/* Plain language app screens shown inside the phone frames, in the chosen language. */

export function AskScreen() {
  const s = useI18n().t.screens.ask;
  return (
    <div className="scr">
      <p className="scr-small">{s.place}</p>
      <h4 className="scr-title">{s.title}</h4>
      <div className="sos">
        <motion.div
          className="sos-btn"
          animate={{ scale: [1, 1.05, 1] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
        >
          SOS
        </motion.div>
      </div>
      <p className="scr-center">{s.hold}</p>
      <div className="scr-pills">
        <span className="pill-btn">{s.speak}</span>
        <span className="pill-btn">{s.type}</span>
      </div>
      <p className="scr-foot">{s.call}</p>
    </div>
  );
}

export function UnderstandScreen() {
  const s = useI18n().t.screens.understand;
  return (
    <div className="scr">
      <p className="scr-small">{s.small}</p>
      <h4 className="scr-title">{s.title}</h4>
      <div className="scr-card">
        <p>"Papa ko chest mein dard hai..."</p>
      </div>
      <div className="scr-list">
        <div><span>{s.age}</span><b>{s.ageVal}</b></div>
        <div><span>{s.pain}</span><b>{s.painVal}</b></div>
        <div><span>{s.blood}</span><b>B+</b></div>
      </div>
      <div className="scr-status">{s.finding}</div>
    </div>
  );
}

export function OnTheWayScreen() {
  const s = useI18n().t.screens.way;
  return (
    <div className="scr">
      <p className="scr-small">{s.small}</p>
      <h4 className="scr-title">{s.title}</h4>
      <div className="scr-map">
        <svg viewBox="0 0 200 170" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <path d="M0 45 H200 M0 115 H200 M55 0 V170 M150 0 V170" stroke="#e5e5e5" strokeWidth="7" fill="none" />
          <path d="M25 150 L55 140 L55 115 L150 115 L150 45 L175 45" stroke="#171717" strokeWidth="2.5" strokeDasharray="5 5" fill="none" />
          <circle cx="175" cy="45" r="8" fill="#ef4444" />
          <motion.circle
            r="7"
            fill="#171717"
            animate={{ cx: [25, 55, 55, 150, 150], cy: [150, 140, 115, 115, 45] }}
            transition={{ duration: 4, repeat: Infinity, ease: "linear", repeatDelay: 0.5 }}
          />
        </svg>
      </div>
      <div className="scr-card row"><span>MH12 AB 1234</span><span className="scr-muted">2.4 km</span></div>
    </div>
  );
}

export function HospitalReadyScreen() {
  const s = useI18n().t.screens.ready;
  return (
    <div className="scr">
      <p className="scr-small">{s.small}</p>
      <h4 className="scr-title">{s.title}</h4>
      <div className="scr-list">
        <div><span>{s.goTo}</span><b>{s.gate}</b></div>
        <div><span>{s.room}</span><b>{s.roomVal}</b></div>
        <div><span>{s.doctor}</span><b>{s.doctorVal}</b></div>
      </div>
      <div className="scr-status ok">{s.family}</div>
    </div>
  );
}

export function CrewScreen() {
  const s = useI18n().t.screens.crew;
  return (
    <div className="scr">
      <p className="scr-small">{s.small}</p>
      <h4 className="scr-title">{s.title}</h4>
      <div className="scr-card">
        <p><b>{s.case}</b></p>
        <p className="scr-muted">{s.where}</p>
      </div>
      <div className="scr-timer">
        <motion.span
          animate={{ width: ["100%", "0%"] }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        />
      </div>
      <div className="scr-actions">
        <span className="pill-btn dark">{s.accept}</span>
        <span className="pill-btn">{s.skip}</span>
      </div>
    </div>
  );
}

export function HospitalScreen() {
  const s = useI18n().t.screens.hosp;
  return (
    <div className="scr">
      <p className="scr-small">{s.small}</p>
      <h4 className="scr-title">{s.title}</h4>
      <div className="scr-card">
        <p><b>{s.man}</b></p>
        <p className="scr-muted">{s.note}</p>
      </div>
      <div className="scr-list">
        <div><span>{s.heartDoc}</span><b>✓</b></div>
        <div><span>{s.cathLab}</span><b>✓</b></div>
      </div>
      <div className="scr-actions">
        <span className="pill-btn dark">{s.accept}</span>
        <span className="pill-btn">{s.decline}</span>
      </div>
    </div>
  );
}
