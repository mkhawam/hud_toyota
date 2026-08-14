import type { Component } from "solid-js";
import { useTopic } from "../core/topics";

const MAX = 7000;
const REDLINE = 6200;

export const Rpm: Component = () => {
  const rpm = useTopic("vehicle.rpm");
  const val = () => rpm() ?? 0;
  const pct = () => Math.min(100, (val() / MAX) * 100);
  return (
    <div class="widget rpm">
      <div class="rpm-bar">
        <div
          class="rpm-fill"
          classList={{ redline: val() >= REDLINE }}
          style={{ width: `${pct()}%` }}
        />
        <div class="rpm-mark" style={{ left: `${(REDLINE / MAX) * 100}%` }} />
      </div>
      <div class="rpm-label">
        <span class="rpm-value">{Math.round(val())}</span> rpm
      </div>
    </div>
  );
};
