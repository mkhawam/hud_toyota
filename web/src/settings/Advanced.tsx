import { createSignal, For, onCleanup, Show, type Component } from "solid-js";
import { config } from "../core/config";
import { autoSave, Group, Icon, Page, Row, showToast, Switch } from "./ui";

interface DebugInfo {
  uptime_s: number;
  topics: Record<string, { value: unknown; age_s: number }>;
}

export const Advanced: Component = () => {
  const [overlay, setOverlay] = createSignal(config().debug === true);
  const saveDebug = autoSave("debug");

  // Reset trip: second tap within 4 s confirms.
  const [armed, setArmed] = createSignal(false);
  let armTimer: ReturnType<typeof setTimeout> | undefined;
  const resetTrip = async () => {
    if (!armed()) {
      setArmed(true);
      armTimer = setTimeout(() => setArmed(false), 4000);
      return;
    }
    clearTimeout(armTimer);
    setArmed(false);
    try {
      await fetch("/api/trip/reset", { method: "POST" });
      showToast("Trip reset");
    } catch {
      showToast("Can't reach the HUD.", true);
    }
  };

  const [info, setInfo] = createSignal<DebugInfo | null>(null);
  const [watching, setWatching] = createSignal(false);
  let poll: ReturnType<typeof setInterval> | undefined;
  const load = async () => {
    try { setInfo(await (await fetch("/api/debug")).json()); } catch { setInfo(null); }
  };
  const toggleWatch = () => {
    const on = !watching();
    setWatching(on);
    clearInterval(poll);
    if (on) { void load(); poll = setInterval(() => void load(), 2000); }
  };
  onCleanup(() => { clearInterval(poll); clearTimeout(armTimer); });

  const fmt = (v: unknown) => {
    const s = typeof v === "number" && !Number.isInteger(v) ? v.toFixed(2)
      : typeof v === "object" ? JSON.stringify(v) : String(v);
    return s.length > 40 ? s.slice(0, 39) + "…" : s;
  };

  return (
    <Page title="Advanced" back>
      <Group title="Trip computer" note="Clears distance, fuel used and drive time. Your best 0–60 is kept.">
        <button type="button" class="row action danger" onClick={() => void resetTrip()}>
          <Icon name="trash" />
          <span>{armed() ? "Tap again to reset the trip" : "Reset trip"}</span>
        </button>
      </Group>

      <Group title="Diagnostics" note="The overlay can also be toggled with the D key on a keyboard plugged into the HUD.">
        <Row label="Debug overlay on the HUD" for="debug-overlay">
          <Switch id="debug-overlay" label="Debug overlay on the HUD" checked={overlay()}
            onChange={(v) => { setOverlay(v); saveDebug(v, 0); }} />
        </Row>
        <button type="button" class="row action" onClick={toggleWatch}>
          <Icon name="drive" />
          <span>{watching() ? "Stop live readings" : "Show live readings"}</span>
        </button>
        <Show when={watching()}>
          <div class="topics">
            <Show when={info()} fallback={<p class="empty">Loading…</p>}>
              <p class="topics-meta">Running {Math.round(info()!.uptime_s / 60)} min · {Object.keys(info()!.topics).length} readings</p>
              <For each={Object.entries(info()!.topics)}>
                {([name, t]) => (
                  <div class="topic" classList={{ stale: t.age_s > 10 }}>
                    <span class="topic-name">{name}</span>
                    <span class="topic-value">{fmt(t.value)}</span>
                  </div>
                )}
              </For>
            </Show>
          </div>
        </Show>
      </Group>
    </Page>
  );
};
