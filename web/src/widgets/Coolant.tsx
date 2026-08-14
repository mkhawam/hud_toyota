import type { Component } from "solid-js";
import { useTopic } from "../core/topics";
import { tempUnit } from "../core/config";

const WARN_C = 105;

export const Coolant: Component = () => {
  const c = useTopic("vehicle.coolant_c");
  const display = () => {
    const v = c();
    if (v === undefined) return "--°";
    return tempUnit() === "f" ? `${Math.round(v * 1.8 + 32)}°F` : `${Math.round(v)}°C`;
  };
  return (
    <div class="widget stat" classList={{ warn: (c() ?? 0) >= WARN_C }}>
      <div class="stat-label">COOLANT</div>
      <div class="stat-value">{display()}</div>
    </div>
  );
};
