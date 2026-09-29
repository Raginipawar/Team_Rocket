import { lazy, Suspense } from "react";
import { HashRouter, Route, Routes } from "react-router-dom";
import { MotionConfig } from "framer-motion";
import I18nProvider from "./i18n/I18nProvider";
import DemoProvider from "./demo/DemoProvider";
import ToastProvider from "./ui/ToastProvider";
import SitePage from "./site/SitePage";
import "./apps/app.css";
import "./apps/screens.css";

const PatientApp = lazy(() => import("./apps/patient/PatientApp"));
const AmbulanceApp = lazy(() => import("./apps/ambulance/AmbulanceApp"));
const HospitalApp = lazy(() => import("./apps/hospital/HospitalApp"));
const FamilyTrack = lazy(() => import("./apps/family/FamilyTrack"));
const OpsApp = lazy(() => import("./apps/ops/OpsApp"));
const DemoLauncher = lazy(() => import("./apps/DemoLauncher"));

export default function App() {
  return (
    <I18nProvider>
      <MotionConfig reducedMotion="user">
        <DemoProvider>
          <ToastProvider>
            <HashRouter>
              <Suspense fallback={<div className="route-loading"><span className="spin" /></div>}>
                <Routes>
                  <Route path="/" element={<SitePage />} />
                  <Route path="/demo" element={<DemoLauncher />} />
                  <Route path="/app/*" element={<PatientApp />} />
                  <Route path="/crew/*" element={<AmbulanceApp />} />
                  <Route path="/hospital/*" element={<HospitalApp />} />
                  <Route path="/track/:token" element={<FamilyTrack />} />
                  <Route path="/ops/*" element={<OpsApp />} />
                  <Route path="*" element={<SitePage />} />
                </Routes>
              </Suspense>
            </HashRouter>
          </ToastProvider>
        </DemoProvider>
      </MotionConfig>
    </I18nProvider>
  );
}
