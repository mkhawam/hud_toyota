/** WebSocket client: auto-reconnect + freshness tracking for the stale indicator. */
import { createSignal } from "solid-js";
import { applyBatch } from "./topics";

export type ConnState = "connecting" | "open" | "closed";

const [connState, setConnState] = createSignal<ConnState>("connecting");
const [lastBatchAt, setLastBatchAt] = createSignal(0);
const [batchCount, setBatchCount] = createSignal(0); // total since page load — debug rate
export { batchCount, connState, lastBatchAt };

const RECONNECT_MS = 1000;

export function connect(): void {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  setConnState("connecting");

  ws.onopen = () => setConnState("open");
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "batch") {
      applyBatch(msg.topics);
      setLastBatchAt(Date.now());
      setBatchCount((c) => c + 1);
    }
  };
  ws.onclose = () => {
    setConnState("closed");
    setTimeout(connect, RECONNECT_MS);
  };
  ws.onerror = () => ws.close();
}
