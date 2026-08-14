import { Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";

/** Quiet until a 0-60 run has been recorded this boot. */
export const ZeroSixty: Component = () => {
  const zs = useTopic("trip.zero_sixty");
  return (
    <Show when={zs() && (zs()!.last_s != null || zs()!.best_s != null)}>
      <div class="widget zerosixty">
        <div class="zs-label">0–60</div>
        <div class="zs-times">
          <Show when={zs()!.last_s != null}>
            <span class="zs-last">{zs()!.last_s!.toFixed(2)}s</span>
          </Show>
          <Show when={zs()!.best_s != null}>
            <span class="zs-best">best {zs()!.best_s!.toFixed(2)}s</span>
          </Show>
        </div>
      </div>
    </Show>
  );
};
