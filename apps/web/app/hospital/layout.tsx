import type { Metadata } from "next";
import type { ReactNode } from "react";
import HospitalLayoutClient from "./layout-client";

export const metadata: Metadata = {
  title: { default: "GoldenHour ER", template: "%s · GoldenHour ER" },
  manifest: "/hospital/manifest.webmanifest",
  appleWebApp: { capable: true, title: "GoldenHour ER", statusBarStyle: "black-translucent" },
};

export default function HospitalLayout({ children }: { children: ReactNode }) {
  return <HospitalLayoutClient>{children}</HospitalLayoutClient>;
}
