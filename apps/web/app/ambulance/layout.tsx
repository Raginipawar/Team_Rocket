import type { Metadata } from "next";
import type { ReactNode } from "react";
import AmbulanceLayoutClient from "./layout-client";

export const metadata: Metadata = {
  title: { default: "GoldenHour Crew", template: "%s · GoldenHour Crew" },
  manifest: "/ambulance/manifest.webmanifest",
  appleWebApp: { capable: true, title: "GoldenHour Crew", statusBarStyle: "black-translucent" },
};

export default function AmbulanceLayout({ children }: { children: ReactNode }) {
  return <AmbulanceLayoutClient>{children}</AmbulanceLayoutClient>;
}
