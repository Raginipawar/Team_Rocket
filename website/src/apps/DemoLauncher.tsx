import Icon from "../ui/Icon";
import DemoBar from "./shell/DemoBar";

const APPS = [
  { href: "#/app", icon: "user", title: "Patient app", who: "Person in need and relatives · phone", desc: "SOS by holding a button, speaking or typing, then live tracking, first aid, the hospital card, and the Family Space." },
  { href: "#/crew", icon: "ambulance", title: "Ambulance app", who: "Paramedic and driver · phone on the dashboard", desc: "Incoming request with a 20 second ring, navigation, one tap patient confirm, and the door timer. Dark by default at night." },
  { href: "#/hospital", icon: "hospital", title: "Hospital dashboard", who: "ER staff · laptop", desc: "New requests with a 45 second respond ring, incoming ambulances, at the door, rooms, resources, staff, analytics." },
  { href: "#/track/8Kq2", icon: "users", title: "Family tracking page", who: "Relative without the app · any phone", desc: "The page the SMS link opens. Location, arrival time and hospital only, no medical details. Six languages." },
  { href: "#/ops", icon: "settings", title: "Ops page", who: "Our on call team · from Telegram", desc: "Escalations with one tap options and a safe default, system analytics, and the scenario runner." },
];

export default function DemoLauncher() {
  return (
    <div className="launch">
      <header className="launch-top">
        <a href="#/" className="pshell-brand"><span className="logo-dot" aria-hidden="true">+</span>GoldenHour</a>
        <a href="#/" className="btn2 btn2-light btn2-sm">Back to website</a>
      </header>
      <main className="launch-main">
        <h1>Try the live demo</h1>
        <p className="lead">One simulated emergency, shared by every app. Open the patient, ambulance and hospital apps in separate tabs, press SOS, and watch each one update in real time.</p>
        <ol className="launch-steps">
          <li><span>Open the <b>Ambulance app</b> and the <b>Hospital dashboard</b> in new tabs (demo password: <b>demo</b>).</span></li>
          <li><span>In the <b>Patient app</b>, sign in with code <b>482913</b>, then hold the SOS button for one second.</span></li>
          <li><span>Accept in the ambulance, confirm the patient, accept in the hospital. With <b>Autoplay</b> on, bots step in for anyone who doesn't tap.</span></li>
        </ol>
        <div className="launch-grid">
          {APPS.map((a) => (
            <a key={a.href} href={a.href} target="_blank" rel="noreferrer" className="launch-card">
              <span className="launch-icon"><Icon name={a.icon} size={24} /></span>
              <h3>{a.title}</h3>
              <span className="muted-s">{a.who}</span>
              <p>{a.desc}</p>
              <span className="launch-open">Open in new tab <Icon name="chevron" size={16} /></span>
            </a>
          ))}
          <div className="launch-card plain"><DemoBar inline /></div>
        </div>
        <p className="fine">Everything here is simulated sample data from the project plan. No real hospital, ambulance or patient is involved.</p>
      </main>
    </div>
  );
}
