import { Show, type Component } from "solid-js";
import { useTopic } from "../core/topics";

// BSD_STAT is 3-bit; side encoding unknown until an on-car observation.
// Until then any nonzero status lights BOTH edge arrows — better a
// bilateral warning than a wrong-side one.
const LEFT_VALUES = [1, 3, 5, 7];
const RIGHT_VALUES = [2, 3, 6, 7];

/** Edge arrows when the blind spot monitor sees a vehicle. Rendered in the
 * Hud shell (absolute overlay) so they hug the projection strip's edges. */
export const BlindSpotOverlay: Component = () => {
  const status = useTopic("vehicle.bsm_status");
  const buzzer = useTopic("vehicle.bsm_buzzer");
  const active = () => (status() ?? 0) > 0;
  const pulsing = () => (buzzer() ?? 0) > 0;
  const leftOn = () => active() && LEFT_VALUES.includes(status()!);
  const rightOn = () => active() && RIGHT_VALUES.includes(status()!);

  return (
    <>
      <Show when={leftOn()}>
        <div class="bsm bsm-left" classList={{ pulsing: pulsing() }}>◀</div>
      </Show>
      <Show when={rightOn()}>
        <div class="bsm bsm-right" classList={{ pulsing: pulsing() }}>▶</div>
      </Show>
    </>
  );
};
