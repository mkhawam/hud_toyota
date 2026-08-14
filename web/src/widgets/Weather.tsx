import { Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";
import { tempUnit } from "../core/config";

const STALE_MIN = 30;

/** WMO weather code → short glanceable label. */
function label(code: number): string {
  if (code === 0) return "CLEAR";
  if (code <= 2) return "PARTLY CLOUDY";
  if (code === 3) return "OVERCAST";
  if (code <= 48) return "FOG";
  if (code <= 57) return "DRIZZLE";
  if (code <= 67) return "RAIN";
  if (code <= 77) return "SNOW";
  if (code <= 82) return "SHOWERS";
  if (code <= 86) return "SNOW SHOWERS";
  return "THUNDERSTORM";
}

export const Weather: Component = () => {
  const w = useTopic("weather.current");
  const temp = () => {
    const v = w()!.temp_c;
    return tempUnit() === "f" ? `${Math.round(v * 1.8 + 32)}°` : `${Math.round(v)}°`;
  };
  const ageMin = () => {
    const t = w()?.fetched_at;
    return t ? (Date.now() / 1000 - t) / 60 : 0;
  };
  return (
    <Show when={w()}>
      <div class="widget weather" classList={{ stale: ageMin() > STALE_MIN }}>
        <div class="weather-temp">{temp()}</div>
        <div class="weather-label">{label(w()!.code)}</div>
        <Show when={ageMin() > STALE_MIN}>
          <div class="weather-age">{Math.round(ageMin())}m ago</div>
        </Show>
      </div>
    </Show>
  );
};
