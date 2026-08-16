/** Theme config → CSS custom properties applied on the HUD root.
 * All derived colors (glows) are computed here in JS so the CSS stays
 * plain var() lookups — no color functions to worry about on the Pi. */

export interface ThemeConfig {
  accent?: string;
  glow?: number;
  night_mode?: "auto" | "on" | "off";
  night_brightness?: number;
  speed_size?: number;
  rpm_width?: number;
}

export const ACCENT_PRESETS = [
  { name: "glacier", hex: "#3ce0ff" },
  { name: "bulba", hex: "#3cff9d" },
  { name: "polar", hex: "#eaf6ff" },
  { name: "pika", hex: "#ffd23c" },
  { name: "mew", hex: "#b48cff" },
] as const;

function rgba(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16);
  const a = Math.max(0, Math.min(1, alpha));
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a.toFixed(3)})`;
}

function glowPair(hex: string, intensity: number, tight: number, wide: number): string {
  if (intensity <= 0.05) return "none";
  return `0 0 0.5cqh ${rgba(hex, tight * intensity)}, 0 0 3cqh ${rgba(hex, wide * intensity)}`;
}

export function themeVars(t: ThemeConfig | undefined): Record<string, string> {
  const accent = t?.accent ?? "#3ce0ff";
  const g = t?.glow ?? 0.85; // restrained by default — polished, not gamer bloom
  return {
    "--accent": accent,
    "--accent-soft": rgba(accent, Math.min(1, 0.6 * g)),
    "--warn-soft": rgba("#ffb300", Math.min(1, 0.6 * g)),
    "--crit-soft": rgba("#ff3b30", Math.min(1, 0.7 * g)),
    "--glow-fg": g <= 0.05
      ? "none"
      : `0 0 0.5cqh rgba(242, 249, 255, ${(0.55 * g).toFixed(3)}), 0 0 3cqh ${rgba(accent, 0.22 * g)}`,
    "--glow-accent": glowPair(accent, g, 0.6, 0.25),
    "--glow-warn": glowPair("#ffb300", g, 0.6, 0.25),
    "--glow-crit": glowPair("#ff3b30", g, 0.6, 0.3),
    "--night-brightness": String(t?.night_brightness ?? 0.55),
    "--speed-size": `${t?.speed_size ?? 36}cqh`,
    "--rpm-width": `${t?.rpm_width ?? 44}cqw`,
  };
}
