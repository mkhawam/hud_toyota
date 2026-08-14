import { Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";
import { speedUnit } from "../core/config";

const KPH_TO_MPH = 0.621371;
const MPH_TO_KPH = 1.609344;
const OVER_SOFT_KPH = 3; // amber
const OVER_HARD_KPH = 12; // red, pulsing

// Road Sign Assist enums — confirm on-car (TSGN sign-type id for a speed
// limit sign, and which SPDUNT value means mph).
const RSA_SPEED_SIGN_TYPE = 1;
const RSA_UNIT_MPH = 1;

export const Speed: Component = () => {
  const kph = useTopic("vehicle.speed_kph");
  const limit = useTopic("road.limit");
  const limitKph = useTopic("road.speed_limit_kph");
  const rsaSign = useTopic("vehicle.rsa_sign");
  const rsaValue = useTopic("vehicle.rsa_value");
  const rsaUnit = useTopic("vehicle.rsa_unit");

  const value = () => {
    const v = kph();
    if (v === undefined) return "--";
    return Math.round(speedUnit() === "mph" ? v * KPH_TO_MPH : v);
  };

  /** Camera-read posted limit (TSS 2.5+ RSA) — preferred over the OSM DB. */
  const cameraLimitKph = () => {
    if (rsaSign() !== RSA_SPEED_SIGN_TYPE) return null;
    const v = rsaValue();
    if (v == null || v < 1 || v > 199) return null;
    return rsaUnit() === RSA_UNIT_MPH ? v * MPH_TO_KPH : v;
  };

  const effectiveLimitKph = () => cameraLimitKph() ?? limitKph() ?? null;

  const over = () => {
    const l = effectiveLimitKph();
    const s = kph();
    if (l == null || s === undefined) return 0;
    return s - l;
  };

  const chip = () => {
    const cam = cameraLimitKph();
    if (cam != null) {
      const n = Math.round(speedUnit() === "mph" ? cam * KPH_TO_MPH : cam);
      return { text: `${n}`, estimated: false };
    }
    const l = limit();
    if (!l) return null;
    const n = speedUnit() === "mph" ? l.limit_mph : Math.round(l.limit_kph);
    return { text: `${l.estimated ? "~" : ""}${n}`, estimated: l.estimated };
  };

  return (
    <div class="widget speed">
      <div
        class="speed-value"
        classList={{ over: over() > OVER_SOFT_KPH, "over-hard": over() > OVER_HARD_KPH }}
      >
        {value()}
      </div>
      <div class="speed-unit">{speedUnit()}</div>
      <Show when={chip()}>
        <div class="limit-chip" classList={{ estimated: chip()!.estimated }}>
          LIMIT {chip()!.text}
        </div>
      </Show>
    </div>
  );
};
