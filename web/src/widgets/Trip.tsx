import { Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";
import { speedUnit } from "../core/config";

const LP100K_TO_MPG = 235.215;

function econ(lp100k: number | null | undefined): string {
  if (lp100k == null || lp100k <= 0) return "--";
  return speedUnit() === "mph"
    ? `${(LP100K_TO_MPG / lp100k).toFixed(1)}`
    : `${lp100k.toFixed(1)}`;
}

export const Trip: Component = () => {
  const dist = useTopic("trip.distance_km");
  const time = useTopic("trip.time_s");
  const avg = useTopic("trip.avg_lp100k");
  const inst = useTopic("trip.instant_lp100k");

  const distance = () => {
    const km = dist() ?? 0;
    return speedUnit() === "mph" ? `${(km * 0.621371).toFixed(1)} mi` : `${km.toFixed(1)} km`;
  };
  const duration = () => {
    const s = time() ?? 0;
    return `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}`;
  };
  const econUnit = () => (speedUnit() === "mph" ? "mpg" : "L/100");

  return (
    <Show when={dist() !== undefined}>
      <div class="widget trip">
        <div class="trip-econ">
          <span class="trip-avg">{econ(avg())}</span>
          <span class="trip-unit">{econUnit()}</span>
          <span class="trip-inst">{econ(inst())} now</span>
        </div>
        <div class="trip-meta">
          {distance()} · {duration()}
        </div>
      </div>
    </Show>
  );
};
