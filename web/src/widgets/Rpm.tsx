import { For, Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";
import { config } from "../core/config";

const SEGMENTS = 32;
const SEG_W = 7;
const SEG_GAP = 2.6;
const VIEW_W = SEGMENTS * (SEG_W + SEG_GAP) - SEG_GAP;

/** Segmented tick gauge (EV-cluster style) with the current gear inline.
 * Range and redline come from config (gauges.rpm_max / rpm_redline). */
export const Rpm: Component = () => {
  const rpm = useTopic("vehicle.rpm");
  const gear = useTopic("vehicle.gear");
  const max = () => config().gauges?.rpm_max ?? 7000;
  const redline = () => config().gauges?.rpm_redline ?? 6200;
  const val = () => rpm() ?? 0;
  const litCount = () => Math.round((Math.min(val(), max()) / max()) * SEGMENTS);

  const segClass = (i: number) => {
    const isRed = (i / SEGMENTS) * max() >= redline();
    if (i >= litCount()) return isRed ? "seg seg-off seg-red-off" : "seg seg-off";
    return isRed ? "seg seg-red" : "seg";
  };

  return (
    <div class="widget rpm">
      <svg viewBox={`0 0 ${VIEW_W} 10`} class="rpm-gauge" aria-label="engine rpm">
        <For each={[...Array(SEGMENTS).keys()]}>
          {(i) => <rect x={i * (SEG_W + SEG_GAP)} y="0" width={SEG_W} height="10" rx="1.2" class={segClass(i)} />}
        </For>
      </svg>
      <div class="rpm-info">
        <Show when={gear()}>
          <span class="rpm-gear">{gear()}</span>
        </Show>
        <span class="rpm-value">{Math.round(val())}</span>
        <span class="rpm-unit">rpm</span>
      </div>
    </div>
  );
};
