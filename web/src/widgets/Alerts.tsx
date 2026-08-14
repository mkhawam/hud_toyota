import { For, Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";

export const Alerts: Component = () => {
  const alerts = useTopic("alerts.active");
  const sorted = () =>
    [...(alerts() ?? [])].sort((a, b) => (a.level === "critical" ? -1 : 1) - (b.level === "critical" ? -1 : 1));
  return (
    <Show when={sorted().length > 0}>
      <div class="widget alerts">
        <For each={sorted()}>
          {(a) => (
            <div class="alert" classList={{ critical: a.level === "critical" }}>
              {a.message}
            </div>
          )}
        </For>
      </div>
    </Show>
  );
};
