/** HUD config fetched from /api/config (phone settings + drives pages). */
import { createSignal } from "solid-js";

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
  gauges?: {
    rpm_max?: number;
    rpm_redline?: number;
    power_max_kw?: number;
    power_regen_kw?: number;
  };
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

/** Apply a saved section to the local copy (dotted path, e.g. "alerts.rules")
 * so summaries elsewhere on the page reflect it without a refetch. */
export function applyLocal(section: string, value: unknown): void {
  const next = structuredClone(config()) as Record<string, unknown>;
  const parts = section.split(".");
  let node = next;
  for (const p of parts.slice(0, -1)) {
    if (typeof node[p] !== "object" || node[p] === null) node[p] = {};
    node = node[p] as Record<string, unknown>;
  }
  node[parts[parts.length - 1]] = value;
  setConfig(next as HudConfig);
}
