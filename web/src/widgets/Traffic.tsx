import { Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";

/** Traffic flow vs free-flow on the nearest road. Quiet when flowing. */
export const Traffic: Component = () => {
  const flow = useTopic("traffic.flow");
  const slowdownPct = () => Math.round((1 - flow()!.ratio) * 100);
  return (
    <Show when={flow() && (flow()!.road_closed || slowdownPct() >= 15)}>
      <div class="widget traffic" classList={{ heavy: flow()!.road_closed || slowdownPct() >= 40 }}>
        {flow()!.road_closed ? "ROAD CLOSED" : `TRAFFIC −${slowdownPct()}%`}
      </div>
    </Show>
  );
};
