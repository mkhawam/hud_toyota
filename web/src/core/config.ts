/** HUD config fetched from /api/config; ?mirror=0|1 overrides for dev. */
import { createEffect, createRoot, createSignal, on } from "solid-js";
import { useTopic } from "./topics";

export interface LayoutItem {
  widget: string;
  slot: string;
}

export interface DisplayConfig {
  aspect?: string | null; // "3:1" — shape of the projected strip
  scale?: number;
  offset_x?: number;
  offset_y?: number;
}

export interface HudConfig {
  mirror?: boolean;
  units?: { speed?: "mph" | "kph"; temp?: "f" | "c" };
  layout?: LayoutItem[];
  display?: DisplayConfig;
  theme?: import("./theme").ThemeConfig;
  gauges?: { rpm_max?: number; rpm_redline?: number };
  debug?: boolean;
}

const [config, setConfig] = createSignal<HudConfig>({});
export { config };

export async function loadConfig(): Promise<void> {
  try {
    const res = await fetch("/api/config");
    if (res.ok) setConfig(await res.json());
  } catch {
    // offline / backend down — defaults apply, widgets show placeholders
  }
}

/** Re-fetch config whenever the settings page saves (config.updated on the
 * bus). Refetching is idempotent, so the primed last-value a reconnecting
 * client receives is harmless. */
export function watchConfigUpdates(): void {
  createRoot(() => {
    const updated = useTopic("config.updated");
    createEffect(on(updated, () => void loadConfig(), { defer: true }));
  });
}

export function mirrored(): boolean {
  const q = new URLSearchParams(location.search).get("mirror");
  if (q !== null) return q === "1" || q === "true";
  return config().mirror ?? false;
}

export function speedUnit(): "mph" | "kph" {
  return config().units?.speed ?? "mph";
}

export function tempUnit(): "f" | "c" {
  return config().units?.temp ?? "f";
}

/** "3:1" or "21:7" → 3; null/absent → fill the whole panel. */
export function aspectRatio(): number | null {
  const raw = config().display?.aspect;
  if (!raw) return null;
  const [w, h] = String(raw).split(":").map(Number);
  return w > 0 && h > 0 ? w / h : null;
}
