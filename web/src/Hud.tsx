import { createEffect, createSignal, For, on, onCleanup, Show, type Component } from "solid-js";
import { Dynamic } from "solid-js/web";
import { aspectRatio, config, mirrored } from "./core/config";
import { getWidget } from "./core/registry";
import { connState, lastBatchAt } from "./core/socket";
import { themeVars } from "./core/theme";
import { useTopic } from "./core/topics";
import { DebugOverlay } from "./DebugOverlay";
import { BlindSpotOverlay } from "./widgets/BlindSpot";

const STALE_MS = 2500;
const NUDGE = 0.005; // arrow key step, fraction of panel
const NUDGE_BIG = 0.02;
const SCALE_STEP = 0.02;

/** "NO LINK" badge when the socket is down or data stops flowing. */
const StatusOverlay: Component = () => {
  const [now, setNow] = createSignal(Date.now());
  const timer = setInterval(() => setNow(Date.now()), 500);
  onCleanup(() => clearInterval(timer));

  const stale = () => connState() !== "open" || now() - lastBatchAt() > STALE_MS;
  return (
    <Show when={stale()}>
      <div class="no-link">NO LINK</div>
    </Show>
  );
};

/** Quiet "OFFLINE" corner tag — internet widgets show cached data meanwhile. */
const NetOverlay: Component = () => {
  const online = useTopic("net.online");
  return (
    <Show when={online() === false}>
      <div class="offline">OFFLINE</div>
    </Show>
  );
};

export const Hud: Component = () => {
  const weather = useTopic("weather.current");
  const lights = useTopic("vehicle.lights_on");
  // night_mode config: on/off force it; auto prefers the actual headlight
  // state (CAN) and falls back to the weather's sunset flag.
  const night = () => {
    const mode = config().theme?.night_mode ?? "auto";
    if (mode !== "auto") return mode === "on";
    if (lights() !== undefined) return lights()! > 0;
    return weather() !== undefined && !weather()!.is_day;
  };

  // Debug overlay: settings-page switch is the base; the D key (or
  // ?debug=1) locally overrides without touching config.
  const [debugLocal, setDebugLocal] = createSignal<boolean | null>(
    new URLSearchParams(location.search).get("debug") === "1" ? true : null,
  );
  const debugOn = () => debugLocal() ?? config().debug ?? false;

  // Projection calibration — position/scale the content box on the panel
  // so it lands on the windshield's reflective patch.
  const d = config().display ?? {};
  const [disp, setDisp] = createSignal({
    scale: d.scale ?? 1,
    offset_x: d.offset_x ?? 0,
    offset_y: d.offset_y ?? 0,
  });
  const [cal, setCal] = createSignal(new URLSearchParams(location.search).get("cal") === "1");
  const [saved, setSaved] = createSignal(false);

  // Phone settings page edits display config live — re-seed unless the
  // driver is mid-calibration here (their in-progress nudges win).
  createEffect(
    on(
      () => config().display,
      (nd) => {
        if (nd && !cal()) {
          setDisp({ scale: nd.scale ?? 1, offset_x: nd.offset_x ?? 0, offset_y: nd.offset_y ?? 0 });
        }
      },
      { defer: true },
    ),
  );

  const save = async () => {
    await fetch("/api/display", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(disp()),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  const onKey = (ev: KeyboardEvent) => {
    if (ev.key === "c" || ev.key === "C") return setCal(!cal());
    if (ev.key === "d" || ev.key === "D") return setDebugLocal(!debugOn());
    if (!cal()) return;
    const step = ev.shiftKey ? NUDGE_BIG : NUDGE;
    const cur = disp();
    switch (ev.key) {
      case "ArrowLeft": setDisp({ ...cur, offset_x: cur.offset_x - step }); break;
      case "ArrowRight": setDisp({ ...cur, offset_x: cur.offset_x + step }); break;
      case "ArrowUp": setDisp({ ...cur, offset_y: cur.offset_y - step }); break;
      case "ArrowDown": setDisp({ ...cur, offset_y: cur.offset_y + step }); break;
      case "+": case "=": setDisp({ ...cur, scale: Math.min(1, cur.scale + SCALE_STEP) }); break;
      case "-": case "_": setDisp({ ...cur, scale: Math.max(0.1, cur.scale - SCALE_STEP) }); break;
      case "s": case "S": void save(); break;
      case "Escape": setCal(false); break;
      default: return;
    }
    ev.preventDefault();
  };
  window.addEventListener("keydown", onKey);
  onCleanup(() => window.removeEventListener("keydown", onKey));

  const viewportStyle = () => {
    const ar = aspectRatio();
    const { scale, offset_x, offset_y } = disp();
    return {
      width: ar ? `min(100vw, calc(100vh * ${ar}))` : "100vw",
      height: ar ? `min(100vh, calc(100vw / ${ar}))` : "100vh",
      transform: `translate(${offset_x * 100}vw, ${offset_y * 100}vh) scale(${scale})`,
      ...themeVars(config().theme),
    };
  };

  // Widgets sharing a slot stack vertically instead of overlapping.
  const slots = () => {
    const grouped = new Map<string, string[]>();
    for (const item of config().layout ?? []) {
      grouped.set(item.slot, [...(grouped.get(item.slot) ?? []), item.widget]);
    }
    return [...grouped.entries()];
  };

  return (
    <div class="viewport" style={viewportStyle()}>
      <div class="hud" classList={{ mirrored: mirrored(), night: night() }}>
        <For each={slots()}>
          {([slot, widgets]) => (
            <div class="slot" style={{ "grid-area": slot }}>
              <For each={widgets}>
                {(name) => (
                  <Show when={getWidget(name)}>
                    <Dynamic component={getWidget(name)!} />
                  </Show>
                )}
              </For>
            </div>
          )}
        </For>
        <StatusOverlay />
        <NetOverlay />
        <BlindSpotOverlay />
        <Show when={debugOn()}>
          <DebugOverlay />
        </Show>
        <Show when={cal()}>
          <div class="cal-frame">
            <div class="cal-info">
              {saved()
                ? "SAVED"
                : `scale ${disp().scale.toFixed(2)}  x ${disp().offset_x.toFixed(3)}  y ${disp().offset_y.toFixed(3)}  —  arrows move · +/− scale · S save · C exit`}
            </div>
          </div>
        </Show>
      </div>
    </div>
  );
};
