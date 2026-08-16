import { createSignal, For, onCleanup, type Component } from "solid-js";
import { batchCount, connState } from "./core/socket";
import { topicAgeMs, topicIndex, useTopic } from "./core/topics";

function fmtValue(v: unknown): string {
  if (v === null || v === undefined) return "∅";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  if (typeof v === "string") return v;
  if (typeof v === "boolean") return v ? "true" : "false";
  const s = JSON.stringify(v);
  return s.length > 38 ? s.slice(0, 37) + "…" : s;
}

function fmtAge(ms: number | null): string {
  if (ms === null) return "";
  if (ms < 1500) return "·";
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
  return `${Math.round(ms / 60_000)}m`;
}

const TopicRow: Component<{ name: string; now: number }> = (props) => {
  const value = useTopic(props.name);
  const age = () => topicAgeMs(props.name, props.now);
  return (
    <div class="dbg-row" classList={{ stale: (age() ?? 0) > 10_000 }}>
      <span class="dbg-topic">{props.name}</span>
      <span class="dbg-value">{fmtValue(value())}</span>
      <span class="dbg-age">{fmtAge(age())}</span>
    </div>
  );
};

/** Live diagnostics: connection, batch rate, every topic with value + age.
 * Toggled by the D key, ?debug=1, or the settings page's debug switch. */
export const DebugOverlay: Component = () => {
  const [now, setNow] = createSignal(Date.now());
  const [rate, setRate] = createSignal(0);
  let lastCount = batchCount();
  const timer = setInterval(() => {
    setNow(Date.now());
    setRate(batchCount() - lastCount);
    lastCount = batchCount();
  }, 1000);
  onCleanup(() => clearInterval(timer));

  return (
    <div class="debug-panel">
      <div class="dbg-head">
        <span classList={{ ok: connState() === "open", bad: connState() !== "open" }}>
          WS {connState()}
        </span>
        <span>{rate()} batch/s</span>
        <span>{topicIndex().length} topics</span>
      </div>
      <div class="dbg-rows">
        <For each={topicIndex()}>{(name) => <TopicRow name={name} now={now()} />}</For>
      </div>
    </div>
  );
};
