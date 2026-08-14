import { For, Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";

/** Active diagnostic trouble codes — quiet unless the car reports some. */
export const Dtc: Component = () => {
  const codes = useTopic("vehicle.dtc_codes");
  return (
    <Show when={(codes() ?? []).length > 0}>
      <div class="widget dtc">
        <div class="dtc-title">CHECK ENGINE</div>
        <For each={codes()}>{(code) => <div class="dtc-code">{code}</div>}</For>
      </div>
    </Show>
  );
};
