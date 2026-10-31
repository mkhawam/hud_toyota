/** Shared building blocks for the settings app. */
import { createSignal, For, onCleanup, onMount, Show, type Component, type JSX } from "solid-js";
import { Portal } from "solid-js/web";
import { applyLocal } from "../core/config";

// ---- saving ---------------------------------------------------------------

const [toast, setToast] = createSignal<{ text: string; error: boolean } | null>(null);
let toastTimer: ReturnType<typeof setTimeout> | undefined;
export function showToast(text: string, error = false): void {
  clearTimeout(toastTimer);
  setToast({ text, error });
  if (!error) toastTimer = setTimeout(() => setToast(null), 1600);
}

function errorText(body: { errors?: unknown[] }): string {
  const e = body.errors?.[0] as { msg?: string; loc?: unknown[] } | string | undefined;
  if (!e) return "The HUD rejected that change.";
  if (typeof e === "string") return e;
  const field = Array.isArray(e.loc) && e.loc.length ? ` (${e.loc.join(" › ")})` : "";
  return (e.msg ?? "Invalid value") + field;
}

/** POST one config section. Returns null on success, else a readable error. */
export async function saveSection(section: string, value: unknown): Promise<string | null> {
  try {
    const res = await fetch(`/api/settings/${section}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(value),
    });
    const body = await res.json();
    if (body.ok) {
      applyLocal(section, body.value);
      return null;
    }
    return errorText(body);
  } catch {
    return "Can't reach the HUD. Check that your phone is on the same Wi-Fi.";
  }
}

/** Debounced auto-save with toast feedback. Changes apply to the HUD live. */
export function autoSave(section: string) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  onCleanup(() => clearTimeout(timer));
  return (value: unknown, delay = 400) => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const err = await saveSection(section, value);
      if (err) showToast(err, true);
      else showToast("Saved");
    }, delay);
  };
}

export const Toast: Component = () => (
  <Show when={toast()}>
    <div class="toast" classList={{ error: toast()!.error }} role="status" aria-live="polite"
      onClick={() => setToast(null)}>
      <Show when={!toast()!.error} fallback={<Icon name="alert" />}>
        <Icon name="check" />
      </Show>
      <span>{toast()!.text}</span>
    </div>
  </Show>
);

// ---- icons (stroke, currentColor) ----------------------------------------

const ICONS: Record<string, string> = {
  look: "M12 3a9 9 0 1 0 0 18c1 0 1.6-.8 1.6-1.6 0-.5-.2-.8-.4-1.1-.3-.3-.4-.7-.4-1.1 0-.9.7-1.6 1.6-1.6h1.9A4.7 4.7 0 0 0 21 11.8C21 7 17 3 12 3ZM7.5 12.5h.01M9.5 8h.01M14.5 8h.01",
  layout: "M3 6.5h18v11H3zM9 6.5v11M15 6.5v11M3 10.2h18M3 13.8h18",
  alert: "M12 4 21.5 20h-19ZM12 10v4.5M12 17.2h.01",
  car: "M5 16.5h14M6.5 16.5V19M17.5 16.5V19M4.5 16.5l1.6-5.2A2 2 0 0 1 8 9.8h8a2 2 0 0 1 1.9 1.5l1.6 5.2M7.5 13.5h.01M16.5 13.5h.01",
  pin: "M12 21s6.5-5.8 6.5-11a6.5 6.5 0 1 0-13 0c0 5.2 6.5 11 6.5 11ZM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
  wrench: "M14.7 6.3a4 4 0 0 0-5.4 5.2l-5 5a1.4 1.4 0 0 0 2 2l5-5a4 4 0 0 0 5.2-5.4l-2.4 2.4-1.8-.4-.4-1.8Z",
  chevron: "M9.5 6l6 6-6 6",
  back: "M14.5 6l-6 6 6 6",
  check: "M5 12.5l4.5 4.5L19 7.5",
  plus: "M12 5v14M5 12h14",
  trash: "M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12",
  wifi: "M4.5 9.5a11 11 0 0 1 15 0M7.5 12.8a6.5 6.5 0 0 1 9 0M10.6 16a2 2 0 0 1 2.8 0M12 19h.01",
  drive: "M4 18l4-6 3.5 3L16 8l4 5M4 21h16",
};

export const Icon: Component<{ name: string; class?: string }> = (props) => (
  <svg class={`icon ${props.class ?? ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d={ICONS[props.name] ?? ""} />
  </svg>
);

// ---- layout ---------------------------------------------------------------

export const Page: Component<{ title: string; back?: boolean; children: JSX.Element }> = (props) => (
  <>
    <header class="page-header">
      <Show when={props.back} fallback={<span class="brand-mark">HUD</span>}>
        <a class="back-link" href="#/" aria-label="Back to all settings">
          <Icon name="back" />
          <span>Settings</span>
        </a>
      </Show>
    </header>
    <main class="page">
      <h1 class="page-title">{props.title}</h1>
      {props.children}
    </main>
  </>
);

export const Group: Component<{ title?: string; note?: JSX.Element; children: JSX.Element }> = (props) => (
  <section class="group">
    <Show when={props.title}>
      <h2 class="group-title">{props.title}</h2>
    </Show>
    <div class="group-body">{props.children}</div>
    <Show when={props.note}>
      <p class="group-note">{props.note}</p>
    </Show>
  </section>
);

export const Row: Component<{ label: string; hint?: string; for?: string; stacked?: boolean; children?: JSX.Element }> = (props) => (
  <div class="row" classList={{ stacked: props.stacked }}>
    <div class="row-text">
      <label class="row-label" for={props.for}>{props.label}</label>
      <Show when={props.hint}>
        <span class="row-hint">{props.hint}</span>
      </Show>
    </div>
    <div class="row-control">{props.children}</div>
  </div>
);

/** Row that navigates (section list on the home screen). */
export const NavRow: Component<{ href: string; icon: string; label: string; value?: string }> = (props) => (
  <a class="row nav-row" href={props.href}>
    <span class="nav-icon"><Icon name={props.icon} /></span>
    <span class="row-label">{props.label}</span>
    <span class="row-value">{props.value}</span>
    <Icon name="chevron" class="chev" />
  </a>
);

export const Segmented: Component<{
  id: string;
  label: string;
  options: { value: string; label: string; font?: string }[];
  value: string;
  onChange: (v: string) => void;
}> = (props) => (
  <div class="seg" role="radiogroup" aria-label={props.label} id={props.id}>
    <For each={props.options}>
      {(o) => (
        <button
          type="button"
          role="radio"
          aria-checked={props.value === o.value}
          classList={{ on: props.value === o.value }}
          style={o.font ? { "font-family": o.font } : undefined}
          onClick={() => props.onChange(o.value)}
        >
          {o.label}
        </button>
      )}
    </For>
  </div>
);

export const Switch: Component<{ id: string; checked: boolean; onChange: (v: boolean) => void; label: string }> = (props) => (
  <button
    type="button"
    id={props.id}
    role="switch"
    aria-checked={props.checked}
    aria-label={props.label}
    class="switch"
    classList={{ on: props.checked }}
    onClick={() => props.onChange(!props.checked)}
  >
    <span class="knob" />
  </button>
);

/** Slider with its value and unit always visible. */
export const Slider: Component<{
  id: string;
  label: string;
  hint?: string;
  min: number;
  max: number;
  step: number;
  value: number;
  format: (v: number) => string;
  onInput: (v: number) => void;
}> = (props) => (
  <div class="row slider-row">
    <div class="slider-head">
      <label class="row-label" for={props.id}>{props.label}</label>
      <output class="slider-value" for={props.id}>{props.format(props.value)}</output>
    </div>
    <input
      id={props.id}
      type="range"
      min={props.min}
      max={props.max}
      step={props.step}
      value={props.value}
      style={{ "--fill": `${((props.value - props.min) / (props.max - props.min)) * 100}%` }}
      onInput={(e) => props.onInput(Number(e.currentTarget.value))}
    />
    <Show when={props.hint}>
      <span class="row-hint">{props.hint}</span>
    </Show>
  </div>
);

/** Number field with a unit suffix; commits on change. */
export const NumberField: Component<{
  id: string;
  value: number;
  unit?: string;
  step?: number;
  min?: number;
  max?: number;
  wide?: boolean;
  onChange: (v: number) => void;
}> = (props) => (
  <span class="num-field" classList={{ wide: props.wide }}>
    <input
      id={props.id}
      type="number"
      inputmode="decimal"
      step={props.step ?? 1}
      min={props.min}
      max={props.max}
      value={props.value}
      onChange={(e) => {
        const v = Number(e.currentTarget.value);
        if (Number.isFinite(v)) props.onChange(v);
      }}
    />
    <Show when={props.unit}>
      <span class="unit">{props.unit}</span>
    </Show>
  </span>
);

/** Bottom sheet for multi-field edits. Escape or the backdrop closes it. */
export const Sheet: Component<{ title: string; onClose: () => void; children: JSX.Element }> = (props) => {
  let panel: HTMLDivElement | undefined;
  const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") props.onClose(); };
  onMount(() => {
    document.addEventListener("keydown", onKey);
    document.body.classList.add("sheet-open");
    panel?.querySelector<HTMLElement>("button, input, select")?.focus();
  });
  onCleanup(() => {
    document.removeEventListener("keydown", onKey);
    document.body.classList.remove("sheet-open");
  });
  return (
    <Portal>
      <div class="sheet-backdrop" onClick={props.onClose} />
      <div class="sheet" role="dialog" aria-modal="true" aria-label={props.title} ref={panel}>
        <div class="sheet-grip" aria-hidden="true" />
        <div class="sheet-head">
          <h2>{props.title}</h2>
          <button type="button" class="text-btn" onClick={props.onClose}>Done</button>
        </div>
        <div class="sheet-body">{props.children}</div>
      </div>
    </Portal>
  );
};
