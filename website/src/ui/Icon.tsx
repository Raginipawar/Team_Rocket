import type { Category } from "../demo/data";

// Simple 24px line icons, drawn to match the site (no emoji anywhere).
const P: Record<string, string> = {
  phone: "M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2",
  mic: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
  keyboard: "M3 7h18v10H3zM7 11h.01M11 11h.01M15 11h.01M7 14h10",
  pin: "M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5",
  bell: "M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 21h4",
  globe: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c2.5 3 2.5 15 0 18M12 3c-2.5 3-2.5 15 0 18",
  back: "M15 5l-7 7 7 7",
  turnLeft: "M17 20v-7a4 4 0 0 0-4-4H6M10 5L6 9l4 4",
  turnRight: "M7 20v-7a4 4 0 0 1 4-4h7M14 5l4 4-4 4",
  chevron: "M9 5l7 7-7 7",
  check: "M5 12.5l4.5 4.5L19 7.5",
  x: "M6 6l12 12M18 6L6 18",
  alert: "M12 4l9 16H3zM12 10v4M12 17h.01",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2",
  target: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 1v4M12 19v4M1 12h4M19 12h4",
  plus: "M12 5v14M5 12h14",
  minus: "M5 12h14",
  expand: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
  share: "M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M12 3v12M8 7l4-4 4 4",
  copy: "M8 8h11v11H8zM5 16V5h11",
  compass: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM15.5 8.5l-2 5-5 2 2-5z",
  speaker: "M4 9v6h4l5 4V5L8 9zM16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11",
  dots: "M12 5h.01M12 12h.01M12 19h.01",
  home: "M4 11l8-7 8 7v9h-5v-6H9v6H4z",
  users: "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 6.5M18 20a6.5 6.5 0 0 0-2.5-5",
  user: "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  history: "M4 12a8 8 0 1 0 2.3-5.6M4 4v4h4M12 8v4l3 2",
  settings: "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1c.6.5 1.3.9 2 1.2L10 21h4l.5-2.6c.7-.3 1.4-.7 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z",
  userPlus: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21a7 7 0 0 1 14 0M19 8v6M16 11h6",
  logout: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4",
  mail: "M3 6h18v12H3zM3 7l9 7 9-7",
  play: "M8 5v14l11-7z",
  stop: "M7 7h10v10H7z",
  bed: "M3 18V8M3 14h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5M7 12a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3",
  road: "M8 3L4 21M16 3l4 18M12 5v2M12 11v2M12 17v2",
  doctor: "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM5 21v-2a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v2M12 14v4M10 16h4",
  wifiOff: "M2 8.5a15 15 0 0 1 6-3M22 8.5a15 15 0 0 0-8.5-3.5M5 12a10 10 0 0 1 4-2.3M19 12a10 10 0 0 0-2.5-1.7M8.5 15.5a5 5 0 0 1 7 0M12 19h.01M3 3l18 18",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
  grid: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  box: "M4 7l8-4 8 4v10l-8 4-8-4zM4 7l8 4 8-4M12 11v10",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  lock: "M6 11h12v10H6zM8 11V7a4 4 0 0 1 8 0v4",
  eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6",
  ambulance: "M2 16V7h11v9M13 10h4l4 4v2h-8M6 11h4M8 9v4M6 18.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM17 18.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3",
  hospital: "M4 21V5h16v16M9 21v-4h6v4M12 8v5M9.5 10.5h5",
  star: "M12 3l2.8 5.8 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.3l1-6.2L3 9.7l6.2-.9z",
};

export default function Icon({ name, size = 20, stroke = 1.8, className }: { name: keyof typeof P | string; size?: number; stroke?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d={P[name] ?? ""} />
    </svg>
  );
}

const CAT: Record<Category, string> = {
  cardiac: "M12 20s-7.5-4.6-9-9.5C2 7 4.5 4 7.5 4 9.5 4 11 5.2 12 6.8 13 5.2 14.5 4 16.5 4 19.5 4 22 7 21 10.5c-1.5 4.9-9 9.5-9 9.5zM5 11h3l1.5-2.5L12 14l1.5-3H19",
  stroke: "M9.5 4A4.5 4.5 0 0 0 5 8.5 4 4 0 0 0 4 16a3.5 3.5 0 0 0 5.5 3M14.5 4A4.5 4.5 0 0 1 19 8.5a4 4 0 0 1 1 7.5 3.5 3.5 0 0 1-5.5 3M12 4v16M9 10h-1.5M15 10h1.5M9 14.5H7.5M15 14.5h1.5",
  trauma: "M4.5 14.5l10-10a3 3 0 0 1 4.2 4.2l-10 10a3 3 0 0 1-4.2-4.2zM9.5 9.5l5 5M11 11h.01M13 13h.01M11 13h.01M13 11h.01",
  burns: "M12 21a6 6 0 0 0 6-6c0-4-3-6-4-10-2.5 2-3 4-3 5.5C10 9 9 8 8.5 7 6.8 9 6 11.3 6 15a6 6 0 0 0 6 6zM12 21a2.5 2.5 0 0 1-2.5-2.5c0-1.7 1.2-2.4 2.5-4 1.3 1.6 2.5 2.3 2.5 4A2.5 2.5 0 0 1 12 21z",
  respiratory: "M12 3v8M12 11l-3 2M12 11l3 2M9 7C5 7 3 12 3 16.5 3 19 4.5 20 6 20c2.5 0 3-2 3-4.5zM15 7c4 0 6 5 6 9.5 0 2.5-1.5 3.5-3 3.5-2.5 0-3-2-3-4.5z",
  obstetric: "M12 6.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM10 22v-6l-2-1 1.5-6h3a5 5 0 0 1 2.5 6l-1 1v6",
  pediatric: "M12 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM8 22v-7l-2-4 3-2h6l3 2-2 4v7M12 15v7",
  poisoning: "M9 3h6M10 3v4l-4 5v8a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-8l-4-5V3M9.5 13.5l5 5M14.5 13.5l-5 5",
  general: "M9 3h6v6h6v6h-6v6H9v-6H3V9h6z",
};

export function CategoryIcon({ c, size = 20 }: { c: Category; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={CAT[c]} />
    </svg>
  );
}
