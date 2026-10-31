import { createResource, createSignal, onCleanup, onMount, Show, type Component } from "solid-js";
import { config } from "../core/config";
import { THEME_PRESETS } from "../core/theme";
import { Group, Icon, NavRow, Page } from "./ui";

interface Status {
  source?: "can" | "elm327" | "none";
  ap?: { active: boolean; ssid?: string; password?: string; url: string };
  online?: boolean;
}

async function fetchStatus(): Promise<Status> {
  const res = await fetch("/api/snapshot?pattern=*");
  const s = await res.json();
  return { source: s["vehicle.source"], ap: s["net.ap"], online: s["net.online"] };
}

/** What the windshield shows right now, refreshed while the page is open.
 * The capture is mirrored for the reflection; it's flipped back here so it
 * reads normally. */
export const LivePreview: Component = () => {
  const [src, setSrc] = createSignal("");
  const [state, setState] = createSignal<"loading" | "ok" | "none">("loading");
  let timer: ReturnType<typeof setInterval> | undefined;
  const refresh = () => {
    if (document.visibilityState === "visible") setSrc(`/api/screenshot?t=${Date.now()}`);
  };
  onMount(() => {
    refresh();
    timer = setInterval(refresh, 2500);
  });
  onCleanup(() => clearInterval(timer));
  return (
    <figure class="preview">
      <div class="preview-frame">
        <Show when={state() !== "none"}
          fallback={<p class="preview-empty">Preview unavailable. The HUD display isn't running on this device.</p>}>
          <img
            src={src()}
            alt="Live view of the HUD display"
            classList={{ unmirror: config().mirror !== false, ready: state() === "ok" }}
            onLoad={() => setState("ok")}
            onError={() => setState((s) => (s === "loading" ? "none" : s))}
          />
        </Show>
      </div>
      <figcaption>
        <span class="live-dot" classList={{ on: state() === "ok" }} />
        {state() === "ok" ? "Live from the windshield" : state() === "loading" ? "Connecting…" : "Offline"}
      </figcaption>
    </figure>
  );
};

export const Home: Component = () => {
  const [status] = createResource(fetchStatus);
  const c = () => config();

  const themeName = () => {
    const t = c().theme ?? {};
    const p = THEME_PRESETS.find((p) => p.theme.accent === (t.accent ?? "#3ce0ff") && p.theme.font === (t.font ?? "chakra"));
    return p?.name ?? "Custom";
  };
  const rules = () => ((c() as { alerts?: { rules?: unknown[] } }).alerts?.rules ?? []).length;
  const units = () => `${(c().units?.speed ?? "mph") === "mph" ? "mph" : "km/h"} · °${(c().units?.temp ?? "f").toUpperCase()}`;
  const source = () => ({ can: "CAN bus", elm327: "OBD adapter", none: "No vehicle" })[status()?.source ?? "none"];

  return (
    <Page title="Settings">
      <LivePreview />

      <div class="status-strip">
        <span class="chip" classList={{ warn: status()?.source === "none" }}>
          <Icon name="car" />{status.loading ? "…" : source()}
        </span>
        <span class="chip">
          <Icon name="wifi" />
          {status()?.ap?.active ? `HUD Wi-Fi ${status()!.ap!.ssid ?? ""}` : status()?.online ? "Online" : "No internet"}
        </span>
      </div>

      <Group>
        <NavRow href="#/look" icon="look" label="Look" value={themeName()} />
        <NavRow href="#/layout" icon="layout" label="Layout" value={`${(c().layout ?? []).length} widgets`} />
        <NavRow href="#/alerts" icon="alert" label="Alerts" value={`${rules()} ${rules() === 1 ? "rule" : "rules"}`} />
        <NavRow href="#/vehicle" icon="car" label="Units & gauges" value={units()} />
      </Group>

      <Group>
        <NavRow href="#/place" icon="pin" label="Location & Wi-Fi" />
        <NavRow href="/trips/" icon="drive" label="Drives" />
        <NavRow href="#/advanced" icon="wrench" label="Advanced" />
      </Group>

      <p class="footnote">Changes save automatically and show on the HUD right away.</p>
    </Page>
  );
};
