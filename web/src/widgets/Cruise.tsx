import { Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";
import { speedUnit } from "../core/config";

const KPH_TO_MPH = 0.621371;

/** ACC set-speed chip, visible only while cruise is engaged.
 * CACC's exact meaning needs on-car confirmation — the plausible-range
 * gate keeps garbage off the windshield until then. */
export const Cruise: Component = () => {
  const on = useTopic("vehicle.cruise_on");
  const set = useTopic("vehicle.cruise_set");
  const valid = () => (on() ?? 0) > 0 && set() !== undefined && set()! >= 30 && set()! <= 200;
  const display = () =>
    Math.round(speedUnit() === "mph" ? set()! * KPH_TO_MPH : set()!);
  return (
    <Show when={valid()}>
      <div class="widget cruise-chip">SET {display()}</div>
    </Show>
  );
};
