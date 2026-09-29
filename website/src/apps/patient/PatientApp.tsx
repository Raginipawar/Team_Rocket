import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import PhoneShell from "../shell/PhoneShell";
import { Otp, Permissions, PhoneEntry, Setup, Splash } from "./Onboarding";
import { AdjustLocation, Home, Speak, TypeReport } from "./Home";
import Live from "./Live";
import Cpr from "./Cpr";
import { AddDependent, FamilyHome, Invite, JoinFamily, MemberCard } from "./Family";
import { Contacts, History, Notifications, Profile, Settings } from "./Account";
import { getSession } from "./session";

function Signed({ children }: { children: ReactNode }) {
  const s = getSession();
  if (!s) return <Navigate to="/app/splash" replace />;
  return <>{children}</>;
}

export default function PatientApp() {
  return (
    <PhoneShell title="Patient app">
      <Routes>
        <Route path="splash" element={<Splash />} />
        <Route path="phone" element={<PhoneEntry />} />
        <Route path="otp" element={<Otp />} />
        <Route path="permissions" element={<Permissions />} />
        <Route path="setup" element={<Setup />} />
        <Route index element={<Signed><Home /></Signed>} />
        <Route path="speak" element={<Signed><Speak /></Signed>} />
        <Route path="type" element={<Signed><TypeReport /></Signed>} />
        <Route path="location" element={<Signed><AdjustLocation /></Signed>} />
        <Route path="live" element={<Signed><Live /></Signed>} />
        <Route path="follow" element={<Signed><Live family /></Signed>} />
        <Route path="cpr" element={<Cpr />} />
        <Route path="family" element={<Signed><FamilyHome /></Signed>} />
        <Route path="family/invite" element={<Signed><Invite /></Signed>} />
        <Route path="family/join" element={<Signed><JoinFamily /></Signed>} />
        <Route path="family/add" element={<Signed><AddDependent /></Signed>} />
        <Route path="family/:id" element={<Signed><MemberCard /></Signed>} />
        <Route path="profile" element={<Signed><Profile /></Signed>} />
        <Route path="contacts" element={<Signed><Contacts /></Signed>} />
        <Route path="history" element={<Signed><History /></Signed>} />
        <Route path="notifications" element={<Signed><Notifications /></Signed>} />
        <Route path="settings" element={<Signed><Settings /></Signed>} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </PhoneShell>
  );
}
