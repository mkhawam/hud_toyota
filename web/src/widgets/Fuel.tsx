import type { Component } from "solid-js";
import { useTopic } from "../core/topics";
import { FuelIcon } from "./icons";

const WARN_PCT = 10;

export const Fuel: Component = () => {
  const pct = useTopic("vehicle.fuel_pct");
  const display = () => (pct() === undefined ? "--%" : `${Math.round(pct()!)}%`);
  return (
    <div class="widget stat" classList={{ warn: (pct() ?? 100) <= WARN_PCT }}>
      <FuelIcon />
      <div class="stat-body">
        <div class="stat-value">{display()}</div>
        <div class="stat-label">FUEL</div>
      </div>
    </div>
  );
};
