import { useParams } from "react-router-dom";
import { Banner, SimTag, Stepper } from "../../ui/Bits";
import Icon from "../../ui/Icon";
import DemoMap from "../../ui/DemoMap";
import LanguageMenu from "../../components/LanguageMenu";
import { useI18n } from "../../i18n/context";
import { PEOPLE, TRACK_TOKEN } from "../../demo/data";
import { useDemoActions } from "../../demo/actions";
import { hospitalInfo } from "../../demo/hospitalInfo";
import { clock } from "../../demo/format";
import { patientSteps } from "../../demo/steps";
import DemoBar from "../shell/DemoBar";

/* Section 6 · Family tracking page (SMS link, no app, no login).
   Privacy (spec 2.25): location, ETA and hospital only. No severity, category or medical details. */
export default function FamilyTrack() {
  const { token } = useParams();
  const { t } = useI18n();
  const tr = t.track;
  const { s, d, now } = useDemoActions();
  const person = PEOPLE.find((p) => p.id === s.forWhom);
  const name = person?.name ?? "Rajesh Kulkarni";
  const info = hospitalInfo(d.hospitalId, s.room);
  const ended = token !== TRACK_TOKEN || !d.active || d.stage === "cancelled";

  const steps = patientSteps(d, s.sosAt, now).map((st, i) => ({ ...st, label: tr.steps[i] ?? st.label }));
  const eta = (min: number) => `${min} ${tr.min}`;
  const range = (min: number) => `(${Math.max(1, min - 2)} ${tr.to} ${min + 3} ${tr.min})`;

  return (
    <div className="track">
      <header className="track-top">
        <a href="#/" className="pshell-brand"><span className="logo-dot" aria-hidden="true">+</span>GoldenHour</a>
        <span className="track-title">{tr.title}</span>
        <LanguageMenu />
      </header>

      <main className="track-body">
        {ended ? (
          <div className="empty"><span className="empty-icon"><Icon name="check" size={26} /></span><p>{tr.expired}</p><a className="btn2 btn2-red" href="tel:108"><Icon name="phone" size={18} />{tr.call108}</a></div>
        ) : (
          <>
            <h1 className="ptitle">{tr.ambulanceFor.replace("{name}", name)}</h1>
            {d.reroute && d.hospitalAcceptedAt !== null && <Banner type="warning">{tr.changed.replace("{name}", info.h.name)}</Banner>}
            {d.stage === "handedOver" && <Banner type="success">{tr.final.replace("{time}", clock(d.received))}</Banner>}

            <div className="track-grid">
              <div className="track-col">
                <Stepper steps={steps} />
              </div>
              <div className="track-col">
                <DemoMap d={d} now={now} height={280} signal={s.signal} />
                <div className="card">
                  <p className="card-k">{tr.ambulance}</p>
                  {d.accepted === null ? <p className="loading-line"><span className="spin" />{tr.finding}</p> : (
                    <>
                      <p className="amb-reg">MH14 AB 1234</p>
                      {d.stage === "going" || d.stage === "transporting" ? (
                        <p className="eta eta-big"><b>{eta(d.etaMin)}</b> <span className="eta-range">{range(d.etaMin)}</span></p>
                      ) : d.arrivedAt && d.leg === "patient" ? <p className="ok-text"><Icon name="check" size={16} stroke={2.6} />{tr.arrived}</p> : null}
                    </>
                  )}
                </div>
                {d.confirmed !== null && (
                  <div className="card">
                    <p className="card-k">{tr.hospital}</p>
                    {d.hospitalAcceptedAt === null ? <p className="loading-line"><span className="spin" />{tr.choosing}</p> : (
                      <>
                        <h3 className="h-name">{info.h.name}</h3>
                        <p className="muted-s">{info.h.address}</p>
                        <div className="kv">
                          <div><span>{tr.gate}</span><b>{info.gate}</b></div>
                          <div><span>{tr.room}</span><b>{info.room}</b></div>
                          <div><span>{tr.team}</span><b>{info.team}</b></div>
                        </div>
                        <div className="row-2">
                          <a className="btn2 btn2-light" href={`https://www.google.com/maps/search/${encodeURIComponent(info.h.name + " " + info.h.area)}`} target="_blank" rel="noreferrer"><Icon name="compass" size={18} />{tr.directions}</a>
                          <a className="btn2 btn2-light" href={`tel:${info.er}`}><Icon name="phone" size={18} />{tr.callEr}</a>
                        </div>
                      </>
                    )}
                  </div>
                )}
                <p className="muted-s center-text">{tr.noMedical}</p>
              </div>
            </div>
          </>
        )}
      </main>

      <footer className="track-foot">
        <a className="btn2 btn2-red" href="tel:108"><Icon name="phone" size={18} />{tr.call108}</a>
        <a className="link-btn" href="#/app">{tr.getApp}</a>
        <SimTag />
      </footer>
      <div className="demobar-fixed"><DemoBar /></div>
    </div>
  );
}
