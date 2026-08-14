import { Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";
import { speedUnit } from "../core/config";

/** US-style speed limit sign; "~" marks an estimated (untagged road) limit. */
export const SpeedLimit: Component = () => {
  const limit = useTopic("road.limit");
  const num = () => {
    const l = limit()!;
    return speedUnit() === "mph" ? l.limit_mph : Math.round(l.limit_kph);
  };
  return (
    <Show when={limit()}>
      <div class="widget limit-sign" classList={{ estimated: limit()!.estimated }}>
        <div class="limit-sign-title">SPEED LIMIT</div>
        <div class="limit-sign-value">
          {limit()!.estimated ? "~" : ""}
          {num()}
        </div>
      </div>
    </Show>
  );
};
