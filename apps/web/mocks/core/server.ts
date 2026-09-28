// GoldenHour mock core: a stand-in for services/core with the same REST (§7) and
// WebSocket (§8) contract, used while teammates' routers are missing or not running.
// Run with `npm run mock:core` (port 8010). Switch any area of the web app to the
// real core with NEXT_PUBLIC_API_MODE_<AREA>=real; see apps/web/README.md.

import { createServer } from "node:http";
import { WebSocketServer, type WebSocket } from "ws";
import { MOCK } from "./config";
import { handle } from "./http";
import "./routes";
import { resetWorld } from "./routes";
import { addSub, allowed, removeSub, type WsRole, type Sub } from "./bus";
import { hashToken, opsSessions, verify, issueOpsLink } from "./auth";
import { db } from "./world";
import { startSim } from "./sim";

resetWorld();
startSim();

const server = createServer((req, res) => void handle(req, res));
const wss = new WebSocketServer({ noServer: true });

server.on("upgrade", (req, socket, head) => {
  const url = new URL(req.url ?? "/", "http://mock");
  if (url.pathname !== "/ws") {
    socket.destroy();
    return;
  }
  wss.handleUpgrade(req, socket, head, (ws) => onConnection(ws, url.searchParams.get("token") ?? ""));
});

function canSeeEmergency(role: WsRole, emergencyId: string, sub: Sub) {
  const e = db.emergencies.get(emergencyId);
  if (!e) return false;
  if (role === "patient") return e.caller_user_id === sub.userId;
  if (role === "paramedic") return e.ambulance_id === sub.ambulanceId || [...db.offers.values()].some((o) => o.emergency_id === e.id && o.ambulance_id === sub.ambulanceId);
  if (role === "hospital_staff") return e.hospital_id === sub.hospitalId || [...db.requests.values()].some((r) => r.emergency_id === e.id && r.hospital_id === sub.hospitalId);
  return false;
}

/** token = access JWT | family track token | ops session (§8). */
function onConnection(ws: WebSocket, token: string) {
  let role: WsRole | null = null;
  let userId: string | null = null;
  let hospitalId: string | null = null;
  let ambulanceId: string | null = null;
  let trackEmergencyId: string | null = null;
  if (token.split(".").length === 3) {
    try {
      const c = verify(token, "access");
      role = c.role === "developer" ? "ops" : (c.role as WsRole);
      userId = c.sub;
      hospitalId = c.hospital_id ?? null;
      ambulanceId = c.ambulance_id ?? null;
    } catch {
      ws.close(4401, "invalid token");
      return;
    }
  } else if (opsSessions.has(token) && opsSessions.get(token)!.expires > Date.now()) {
    role = "ops";
    userId = opsSessions.get(token)!.user_id;
  } else {
    const hash = hashToken(token);
    const e = [...db.emergencies.values()].find((x) => x.track_token === hash);
    if (e) {
      role = "family";
      trackEmergencyId = e.id;
    }
  }
  if (!role) {
    ws.close(4401, "invalid token");
    return;
  }
  const sub = addSub({ ws, role, userId, hospitalId, ambulanceId, trackEmergencyId });
  ws.on("message", (raw) => {
    let msg: { op?: string; channel?: string; data?: Record<string, unknown> };
    try {
      msg = JSON.parse(raw.toString());
    } catch {
      return;
    }
    if (msg.op === "ping") ws.send(JSON.stringify({ event: "pong" }));
    else if (msg.op === "subscribe" && msg.channel) {
      let internal = msg.channel;
      if (msg.channel.startsWith("track:")) {
        const hash = hashToken(msg.channel.slice(6));
        const e = [...db.emergencies.values()].find((x) => x.track_token === hash);
        if (!e || (role === "family" && e.id !== trackEmergencyId)) {
          ws.send(JSON.stringify({ event: "error", data: { code: "FORBIDDEN", channel: msg.channel } }));
          return;
        }
        internal = `track:${hash}`;
      } else if (!allowed(sub, msg.channel, canSeeEmergency)) {
        ws.send(JSON.stringify({ event: "error", data: { code: "FORBIDDEN", channel: msg.channel } }));
        return;
      }
      sub.channels.set(internal, msg.channel);
      ws.send(JSON.stringify({ event: "subscribed", channel: msg.channel }));
    } else if (msg.op === "unsubscribe" && msg.channel) {
      for (const [k, v] of sub.channels) if (v === msg.channel) sub.channels.delete(k);
    } else if (msg.op === "heartbeat" && role === "paramedic" && ambulanceId) {
      const a = db.ambulances.get(ambulanceId);
      if (a) a.last_heartbeat_at = Date.now();
    }
  });
  ws.on("close", () => removeSub(sub));
  ws.on("error", () => removeSub(sub));
}

server.listen(MOCK.PORT, () => {
  console.log(`\n[mock-core] GoldenHour mock core on http://localhost:${MOCK.PORT} (REST /api/v1, WS /ws)`);
  console.log(`[mock-core] logins: patient OTP any number | staff +919000000001..8 / demo1234 | paramedic +919100000001..15 / demo1234`);
  console.log(`[mock-core] ops one-time link: ${MOCK.WEB_ORIGIN}/ops/${issueOpsLink()}\n`);
});
