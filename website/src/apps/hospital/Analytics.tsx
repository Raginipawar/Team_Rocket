import { useState } from "react";
import { ChartCard, Columns, HBars, Meter, StatTile } from "../../ui/charts";
import { SimTag } from "../../ui/Bits";

type Range = "today" | "7d" | "custom";

// Simulated analytics for Greenfield Heart Centre.
const DATA: Record<Range, {
  received: number; doorWait: number; accepted: number; response: number; fresh: number;
  byHour: number[]; reasons: [string, number][]; categories: [string, number][];
}> = {
  today: {
    received: 14, doorWait: 9, accepted: 86, response: 38, fresh: 82,
    byHour: [4, 3, 5, 6, 8, 12, 17, 9, 7, 11, 14, 8, 6, 9, 13, 10, 7, 5, 6, 8, 11, 9, 6, 5],
    reasons: [["No bed", 3], ["No specialist", 2], ["Equipment down", 1], ["Over capacity", 1]],
    categories: [["Heart", 6], ["Accident", 3], ["Breathing", 2], ["Stroke", 2], ["General", 1]],
  },
  "7d": {
    received: 96, doorWait: 11, accepted: 81, response: 44, fresh: 76,
    byHour: [7, 6, 6, 8, 10, 13, 16, 12, 9, 12, 15, 11, 9, 10, 14, 12, 9, 8, 9, 11, 13, 10, 8, 7],
    reasons: [["No bed", 14], ["No specialist", 9], ["Over capacity", 6], ["Equipment down", 4], ["Not equipped", 3]],
    categories: [["Heart", 38], ["Accident", 22], ["Breathing", 14], ["Stroke", 12], ["General", 10]],
  },
  custom: {
    received: 212, doorWait: 12, accepted: 79, response: 47, fresh: 71,
    byHour: [8, 7, 7, 9, 11, 14, 17, 14, 11, 13, 16, 12, 10, 11, 15, 13, 10, 9, 10, 12, 14, 11, 9, 8],
    reasons: [["No bed", 31], ["No specialist", 18], ["Over capacity", 15], ["Equipment down", 9], ["Not equipped", 7]],
    categories: [["Heart", 81], ["Accident", 49], ["Breathing", 31], ["Stroke", 28], ["General", 23]],
  },
};

const hourLabel = (h: number) => `${((h + 11) % 12) + 1}${h < 12 ? "a" : "p"}`;

export default function Analytics() {
  const [range, setRange] = useState<Range>("today");
  const x = DATA[range];
  const hours = x.byHour.map((v, h) => ({ label: hourLabel(h), value: v }));
  const reasons = x.reasons.map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
  const cats = x.categories.map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);

  return (
    <div className="h-page">
      <div className="h-page-head">
        <div className="seg3" role="group" aria-label="Date range">
          {([["today", "Today"], ["7d", "7 days"], ["custom", "Last 30 days"]] as const).map(([k, l]) => (
            <button key={k} aria-pressed={range === k} onClick={() => setRange(k)}>{l}</button>
          ))}
        </div>
        <SimTag />
      </div>

      <div className="kpis">
        <StatTile label="Patients received" value={String(x.received)} sub={range === "today" ? "today" : range === "7d" ? "last 7 days" : "last 30 days"} />
        <StatTile label="Avg ambulance door wait" value={`${x.doorWait} min`} sub={x.doorWait > 10 ? "above 10 min goal" : "within 10 min goal"} tone={x.doorWait > 10 ? "warn" : "good"} />
        <StatTile label="Requests accepted" value={`${x.accepted}%`} />
        <StatTile label="Avg time to respond" value={`${x.response} s`} sub="limit is 45 s" />
      </div>

      <div className="charts">
        <ChartCard title="Ambulance door wait by hour" note="Average minutes an ambulance waited at the ER door"
          table={{ head: ["Hour", "Minutes"], rows: hours.map((h) => [h.label, h.value]) }}>
          <Columns data={hours} unit="min" refLine={15} refLabel="15 min alert" />
        </ChartCard>

        <ChartCard title="Accepted vs rejected" note="Share of requests accepted, and why the rest were rejected"
          table={{ head: ["Outcome", "Count"], rows: [["Accepted %", x.accepted], ...reasons.map((r) => [`Rejected: ${r.label}`, r.value])] }}>
          <Meter value={x.accepted} label="of requests accepted" />
          <p className="card-k" style={{ margin: "14px 0 6px" }}>Reject reasons</p>
          <HBars data={reasons} />
        </ChartCard>

        <ChartCard title="Data freshness" note="Share of time bed and equipment numbers were under 10 min old"
          table={{ head: ["Measure", "Value"], rows: [["Fresh", `${x.fresh}%`]] }}>
          <Meter value={x.fresh} label="of the time data was fresh" />
        </ChartCard>

        <ChartCard title="Arrivals by category" note="Patients received"
          table={{ head: ["Category", "Patients"], rows: cats.map((c) => [c.label, c.value]) }}>
          <HBars data={cats} />
        </ChartCard>
      </div>
    </div>
  );
}
