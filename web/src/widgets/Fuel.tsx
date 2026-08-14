import type { Component } from "solid-js";
import { useTopic } from "../core/topics";

const WARN_PCT = 10;

export const Fuel: Component = () => {
  const pct = useTopic("vehicle.fuel_pct");
  const display = () => (pct() === undefined ? "--%" : `${Math.round(pct()!)}%`);
  return (
    <div class="widget stat" classList={{ warn: (pct() ?? 100) <= WARN_PCT }}>
      <div class="stat-label">FUEL</div>
      <div class="stat-value">{display()}</div>
    </div>
  );
};
