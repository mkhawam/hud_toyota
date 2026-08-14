import type { Component } from "solid-js";
import { useTopic } from "../core/topics";
import { tempUnit } from "../core/config";
import { ThermoIcon } from "./icons";

const WARN_C = 105;

export const Coolant: Component = () => {
  const c = useTopic("vehicle.coolant_c");
  const display = () => {
    const v = c();
    if (v === undefined) return "--°";
    return tempUnit() === "f" ? `${Math.round(v * 1.8 + 32)}°` : `${Math.round(v)}°`;
  };
  return (
    <div class="widget stat" classList={{ warn: (c() ?? 0) >= WARN_C }}>
      <ThermoIcon />
      <div class="stat-body">
        <div class="stat-value">{display()}</div>
        <div class="stat-label">COOLANT</div>
      </div>
    </div>
  );
};
