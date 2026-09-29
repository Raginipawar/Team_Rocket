"use client";

import dynamic from "next/dynamic";
import type { LiveMapProps } from "./LiveMap";

// MapLibre needs the browser; load it on the client only.
const LiveMap = dynamic(() => import("./LiveMap"), {
  ssr: false,
  loading: () => <div className="h-[280px] animate-pulse rounded-[24px] bg-soft" aria-hidden />,
});

export default function Map(props: LiveMapProps) {
  return <LiveMap {...props} />;
}
export type { LiveMapProps };
