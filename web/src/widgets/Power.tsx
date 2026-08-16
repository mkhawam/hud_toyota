import { For, Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";
import { config } from "../core/config";

// Hybrid power meter, stock-cluster style: CHG (regen) fills left of the
// zero mark, drive power fills right, the top of the range reads as PWR.
const SEGMENTS = 48;
const SEG_W = 4;
const SEG_GAP = 2.4;
const VIEW_W = SEGMENTS * (SEG_W + SEG_GAP) - SEG_GAP;
const PWR_ZONE_FRAC = 0.8; // of max power → red segments

export const Power: Component = () => {
  const kw = useTopic("vehicle.power_kw");
  const gear = useTopic("vehicle.gear");
  const max = () => config().gauges?.power_max_kw ?? 150;
  const regen = () => config().gauges?.power_regen_kw ?? 50;
  const val = () => kw() ?? 0;

  // segment index of the zero mark (regen portion of the scale)
  const zeroSeg = () => Math.round((regen() / (regen() + max())) * SEGMENTS);

  const segClass = (i: number) => {
    const z = zeroSeg();
    const v = val();
    if (i < z) {
      // regen side: lit from zero leftward
      const litFrom = z - Math.min(z, Math.ceil((Math.max(0, -v) / regen()) * z));
      return i >= litFrom ? "seg seg-chg" : "seg seg-off";
    }
    // drive side: lit from zero rightward
    const driveSegs = SEGMENTS - z;
    const lit = Math.min(driveSegs, Math.ceil((Math.max(0, v) / max()) * driveSegs));
    const isPwr = (i - z) / driveSegs >= PWR_ZONE_FRAC;
    if (i - z >= lit) return isPwr ? "seg seg-off seg-red-off" : "seg seg-off";
    return isPwr ? "seg seg-red" : "seg";
  };

  return (
    <div class="widget rpm">
      <svg viewBox={`0 0 ${VIEW_W} 12`} class="rpm-gauge" aria-label="hybrid power">
        <For each={[...Array(SEGMENTS).keys()]}>
          {(i) => <rect x={i * (SEG_W + SEG_GAP)} y="2" width={SEG_W} height="10" rx="1.2" class={segClass(i)} />}
        </For>
        {/* zero mark */}
        <rect x={zeroSeg() * (SEG_W + SEG_GAP) - SEG_GAP / 2 - 0.5} y="0" width="1" height="12" class="power-zero" />
      </svg>
      <div class="rpm-info">
        <span class="power-side">CHG</span>
        <Show when={gear()}>
          <span class="rpm-gear">{gear()}</span>
        </Show>
        <span class="rpm-value" classList={{ "power-regen": val() < -1 }}>
          {Math.abs(Math.round(val()))}
        </span>
        <span class="rpm-unit">kW</span>
        <span class="power-side pwr">PWR</span>
      </div>
    </div>
  );
};
