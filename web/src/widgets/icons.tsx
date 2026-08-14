import type { Component, JSX } from "solid-js";

/** Minimal stroke icons, currentColor — they inherit widget state colors. */
const I: Component<{ children: JSX.Element; class?: string }> = (props) => (
  <svg
    viewBox="0 0 24 24"
    class={`icon ${props.class ?? ""}`}
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    {props.children}
  </svg>
);

const Cloud = () => (
  <path d="M6.5 17h9.5a3.8 3.8 0 0 0 .4-7.58A5.2 5.2 0 0 0 6.3 8.5 4.1 4.1 0 0 0 6.5 17Z" />
);

export const SunIcon: Component = () => (
  <I>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.5 1.5M16.9 16.9l1.5 1.5M18.4 5.6l-1.5 1.5M7.1 16.9l-1.5 1.5" />
  </I>
);

export const PartlyIcon: Component = () => (
  <I>
    <circle cx="7.5" cy="7.5" r="2.6" />
    <path d="M7.5 2.8v1.4M2.8 7.5h1.4M4.2 4.2l1 1" />
    <path d="M9 19h8.2a3.4 3.4 0 0 0 .36-6.78A4.6 4.6 0 0 0 8.8 11.5 3.7 3.7 0 0 0 9 19Z" />
  </I>
);

export const CloudIcon: Component = () => <I><Cloud /></I>;

export const FogIcon: Component = () => (
  <I>
    <path d="M7 12.5h10.5a3.2 3.2 0 0 0 .3-6.38A4.6 4.6 0 0 0 8.9 5.4 3.4 3.4 0 0 0 7 12.5Z" />
    <path d="M5 16.5h14M7 20h10" />
  </I>
);

export const RainIcon: Component = () => (
  <I>
    <path d="M7 14h9.5a3.4 3.4 0 0 0 .36-6.78A4.7 4.7 0 0 0 7.8 6.3 3.6 3.6 0 0 0 7 14Z" />
    <path d="M9 17l-1 3M13 17l-1 3M17 17l-1 3" />
  </I>
);

export const SnowIcon: Component = () => (
  <I>
    <path d="M7 14h9.5a3.4 3.4 0 0 0 .36-6.78A4.7 4.7 0 0 0 7.8 6.3 3.6 3.6 0 0 0 7 14Z" />
    <circle cx="9" cy="18" r="0.6" fill="currentColor" />
    <circle cx="13" cy="20" r="0.6" fill="currentColor" />
    <circle cx="16.5" cy="17.5" r="0.6" fill="currentColor" />
  </I>
);

export const StormIcon: Component = () => (
  <I>
    <path d="M7 13h9.5a3.4 3.4 0 0 0 .36-6.78A4.7 4.7 0 0 0 7.8 5.3 3.6 3.6 0 0 0 7 13Z" />
    <path d="M13 13l-2.5 4h3L11 21" />
  </I>
);

export const ThermoIcon: Component = () => (
  <I>
    <path d="M10.5 4.5a1.8 1.8 0 0 1 3.6 0v8.2a4 4 0 1 1-3.6 0Z" />
    <path d="M12.3 9v6.5" />
  </I>
);

export const FuelIcon: Component = () => (
  <I>
    <rect x="4.5" y="4" width="9" height="16" rx="1.4" />
    <path d="M7 8h4" />
    <path d="M13.5 10h1.6l2.4 2.4V18a1.6 1.6 0 0 1-3.2 0v-3.5h-0.8" />
  </I>
);

export const WarnIcon: Component = () => (
  <I>
    <path d="M12 4 21.5 20h-19Z" />
    <path d="M12 10v4.5" />
    <circle cx="12" cy="17" r="0.5" fill="currentColor" />
  </I>
);

/** WMO weather code → condition icon. */
export function weatherIcon(code: number): Component {
  if (code === 0) return SunIcon;
  if (code <= 2) return PartlyIcon;
  if (code === 3) return CloudIcon;
  if (code <= 48) return FogIcon;
  if (code <= 67) return RainIcon;
  if (code <= 77) return SnowIcon;
  if (code <= 82) return RainIcon;
  if (code <= 86) return SnowIcon;
  return StormIcon;
}
