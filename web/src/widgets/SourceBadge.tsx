import { Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";

const LABELS: Record<string, string> = { can: "CAN", elm327: "OBD", none: "NO VEHICLE" };

/** Which vehicle source is live (published by the auto manager). */
export const SourceBadge: Component = () => {
  const source = useTopic("vehicle.source");
  return (
    <Show when={source()}>
      <div class="widget source-badge" classList={{ warn: source() === "none" }}>
        {LABELS[source()!] ?? source()}
      </div>
    </Show>
  );
};
