import { Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";

// LKAWLSL/LKAWLSR enum (2-bit). Values below follow the stock cluster's
// behavior as best known; refine after an on-car candump observation of
// 0x412 while crossing lines. 0 = no line; 1/2 = detected; 3 = departure.
const DETECTED_MIN = 1;
const ALERT_VALUE = 3;

/** Cluster-style lane indicator: two perspective lane lines from the
 * Toyota camera. Status only (like the factory display) — no geometry. */
export const Lanes: Component = () => {
  const left = useTopic("vehicle.lane_left");
  const right = useTopic("vehicle.lane_right");
  const buzzer = useTopic("vehicle.lda_buzzer");

  const cls = (v: number | undefined) => ({
    detected: v !== undefined && v >= DETECTED_MIN && v !== ALERT_VALUE,
    alert: v === ALERT_VALUE || ((buzzer() ?? 0) > 0 && v !== undefined && v >= DETECTED_MIN),
  });

  return (
    <Show when={left() !== undefined || right() !== undefined}>
      <div class="widget lanes">
        <svg viewBox="0 0 120 44" class="lanes-svg" aria-label="lane markings">
          {/* car marker — a small panda, because this car has residents */}
          <g class="lanes-car">
            <circle cx="56.6" cy="34.4" r="1.9" />
            <circle cx="63.4" cy="34.4" r="1.9" />
            <circle cx="60" cy="38" r="4.6" />
            <circle cx="58.2" cy="37.2" r="1.05" class="lanes-car-patch" />
            <circle cx="61.8" cy="37.2" r="1.05" class="lanes-car-patch" />
            <ellipse cx="60" cy="39.6" rx="0.9" ry="0.7" class="lanes-car-patch" />
          </g>
          {/* left / right lane lines converging toward a vanishing point */}
          <path d="M38 42 L52 4" class="lane-line" classList={cls(left())} />
          <path d="M82 42 L68 4" class="lane-line" classList={cls(right())} />
        </svg>
      </div>
    </Show>
  );
};
