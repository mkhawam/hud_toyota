import { createSignal, For, onCleanup, Show, type Component, type JSX } from "solid-js";
import { config, type LayoutItem } from "../core/config";
import { ALERT_TOPICS, SLOTS, WIDGET_NAMES } from "../core/names";
import { ACCENT_PRESETS, FONTS, THEME_PRESETS, type FontKey, type ThemeConfig } from "../core/theme";

const NAV = [
  { id: "appearance", label: "Theme" },
  { id: "units", label: "Units" },
  { id: "layout", label: "Layout" },
  { id: "gauges", label: "Gauges" },
  { id: "alerts", label: "Alerts" },
  { id: "location", label: "Location" },
  { id: "trip", label: "Trip" },
  { id: "debug", label: "Debug" },
] as const;

interface AlertRule {
  topic: string;
  above?: number | null;
  below?: number | null;
  level: "warn" | "critical";
  message: string;
}

async function postSection(section: string, value: unknown): Promise<string | null> {
  try {
    const res = await fetch(`/api/settings/${section}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(value),
    });
    const body = await res.json();
    if (body.ok) return null;
    return JSON.stringify(body.errors?.[0]?.msg ?? body.errors?.[0] ?? "save failed");
  } catch {
    return "network error";
  }
}

/** Section card with its own save button + status line. */
const Card: Component<{
  title: string;
  id?: string;
  onSave: () => Promise<string | null>;
  children: JSX.Element;
}> = (props) => {
  const [status, setStatus] = createSignal<"idle" | "saving" | "saved" | string>("idle");
  const save = async () => {
    setStatus("saving");
    const err = await props.onSave();
    setStatus(err ?? "saved");
    if (!err) setTimeout(() => setStatus("idle"), 2000);
  };
  return (
    <section class="card" id={props.id}>
      <h2>{props.title}</h2>
      {props.children}
      <div class="card-footer">
        <button class="save" onClick={() => void save()} disabled={status() === "saving"}>
          Save
        </button>
        <Show when={status() === "saved"}>
          <span class="ok">✓ saved</span>
        </Show>
        <Show when={status() !== "idle" && status() !== "saving" && status() !== "saved"}>
          <span class="err">{status()}</span>
        </Show>
      </div>
    </section>
  );
};

const UnitsCard: Component = () => {
  const [speed, setSpeed] = createSignal(config().units?.speed ?? "mph");
  const [temp, setTemp] = createSignal(config().units?.temp ?? "f");
  return (
    <Card title="Units" id="units" onSave={() => postSection("units", { speed: speed(), temp: temp() })}>
      <div class="row">
        <label>Speed</label>
        <div class="seg">
          <For each={["mph", "kph"] as const}>
            {(u) => (
              <button classList={{ active: speed() === u }} onClick={() => setSpeed(u)}>
                {u.toUpperCase()}
              </button>
            )}
          </For>
        </div>
      </div>
      <div class="row">
        <label>Temperature</label>
        <div class="seg">
          <For each={["f", "c"] as const}>
            {(u) => (
              <button classList={{ active: temp() === u }} onClick={() => setTemp(u)}>
                °{u.toUpperCase()}
              </button>
            )}
          </For>
        </div>
      </div>
    </Card>
  );
};

const MirrorCard: Component = () => {
  const [mirror, setMirror] = createSignal(config().mirror ?? true);
  return (
    <Card title="Projection" onSave={() => postSection("mirror", mirror())}>
      <div class="row">
        <label>Mirror image (windshield reflection)</label>
        <input
          type="checkbox"
          checked={mirror()}
          onChange={(e) => setMirror(e.currentTarget.checked)}
        />
      </div>
    </Card>
  );
};

const LayoutCard: Component = () => {
  const [items, setItems] = createSignal<LayoutItem[]>([...(config().layout ?? [])]);
  const update = (i: number, patch: Partial<LayoutItem>) =>
    setItems(items().map((it, j) => (j === i ? { ...it, ...patch } : it)));
  return (
    <Card title="Widget layout" id="layout" onSave={() => postSection("layout", items())}>
      <For each={items()}>
        {(item, i) => (
          <div class="row">
            <select value={item.widget} onChange={(e) => update(i(), { widget: e.currentTarget.value })}>
              <For each={[...WIDGET_NAMES]}>{(w) => <option value={w}>{w}</option>}</For>
            </select>
            <select value={item.slot} onChange={(e) => update(i(), { slot: e.currentTarget.value })}>
              <For each={[...SLOTS]}>{(s) => <option value={s}>{s}</option>}</For>
            </select>
            <button class="remove" onClick={() => setItems(items().filter((_, j) => j !== i()))}>
              ✕
            </button>
          </div>
        )}
      </For>
      <button class="add" onClick={() => setItems([...items(), { widget: "clock", slot: "top-left" }])}>
        + add widget
      </button>
    </Card>
  );
};

const AlertsCard: Component = () => {
  const initial = (config() as { alerts?: { rules?: AlertRule[] } }).alerts?.rules ?? [];
  const [rules, setRules] = createSignal<AlertRule[]>(initial.map((r) => ({ ...r })));
  const update = (i: number, patch: Partial<AlertRule>) =>
    setRules(rules().map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const condOf = (r: AlertRule) => (r.below != null ? "below" : "above");
  const valueOf = (r: AlertRule) => r.below ?? r.above ?? 0;
  const setCond = (i: number, cond: string, value: number) =>
    update(i, cond === "below" ? { below: value, above: null } : { above: value, below: null });
  return (
    <Card
      title="Alert rules"
      id="alerts"
      onSave={() =>
        postSection(
          "alerts.rules",
          rules().map((r) => ({
            topic: r.topic,
            ...(r.below != null ? { below: r.below } : { above: r.above ?? 0 }),
            level: r.level,
            message: r.message,
          })),
        )
      }
    >
      <datalist id="topics">
        <For each={[...ALERT_TOPICS]}>{(t) => <option value={t} />}</For>
      </datalist>
      <For each={rules()}>
        {(rule, i) => (
          <div class="rule">
            <div class="row">
              <input
                class="grow"
                list="topics"
                value={rule.topic}
                placeholder="topic"
                onChange={(e) => update(i(), { topic: e.currentTarget.value })}
              />
              <button class="remove" onClick={() => setRules(rules().filter((_, j) => j !== i()))}>
                ✕
              </button>
            </div>
            <div class="row">
              <select
                value={condOf(rule)}
                onChange={(e) => setCond(i(), e.currentTarget.value, valueOf(rule))}
              >
                <option value="above">above</option>
                <option value="below">below</option>
              </select>
              <input
                type="number"
                value={valueOf(rule)}
                onChange={(e) => setCond(i(), condOf(rule), Number(e.currentTarget.value))}
              />
              <select
                value={rule.level}
                onChange={(e) => update(i(), { level: e.currentTarget.value as AlertRule["level"] })}
              >
                <option value="warn">warn</option>
                <option value="critical">critical</option>
              </select>
            </div>
            <div class="row">
              <input
                class="grow"
                value={rule.message}
                placeholder="MESSAGE"
                maxlength="40"
                onChange={(e) => update(i(), { message: e.currentTarget.value })}
              />
            </div>
          </div>
        )}
      </For>
      <button
        class="add"
        onClick={() =>
          setRules([...rules(), { topic: "vehicle.coolant_c", above: 110, level: "warn", message: "ALERT" }])
        }
      >
        + add rule
      </button>
    </Card>
  );
};

const LocationCard: Component = () => {
  const loc = (config() as { location?: { lat?: number; lon?: number } }).location ?? {};
  const [lat, setLat] = createSignal(loc.lat ?? 40.4862);
  const [lon, setLon] = createSignal(loc.lon ?? -74.4518);
  const useGps = async () => {
    const res = await fetch("/api/snapshot?pattern=gps.position");
    const snap = await res.json();
    const fix = snap["gps.position"];
    if (fix) {
      setLat(fix.lat);
      setLon(fix.lon);
    }
  };
  return (
    <Card title="Home location" id="location" onSave={() => postSection("location", { lat: lat(), lon: lon() })}>
      <div class="row">
        <label>Lat</label>
        <input type="number" step="0.0001" value={lat()} onChange={(e) => setLat(Number(e.currentTarget.value))} />
        <label>Lon</label>
        <input type="number" step="0.0001" value={lon()} onChange={(e) => setLon(Number(e.currentTarget.value))} />
      </div>
      <button class="add" onClick={() => void useGps()}>
        use current GPS position
      </button>
    </Card>
  );
};

const Slider: Component<{
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onInput: (v: number) => void;
  suffix?: string;
}> = (props) => (
  <div class="row">
    <label>{props.label}</label>
    <input
      type="range"
      class="grow"
      min={props.min}
      max={props.max}
      step={props.step}
      value={props.value}
      onInput={(e) => props.onInput(Number(e.currentTarget.value))}
    />
    <span class="slider-val">
      {props.value}
      {props.suffix ?? ""}
    </span>
  </div>
);

const AppearanceCard: Component = () => {
  const t = config().theme ?? {};
  const [theme, setTheme] = createSignal<Required<ThemeConfig>>({
    accent: t.accent ?? "#3ce0ff",
    glow: t.glow ?? 0.85,
    font: t.font ?? "chakra",
    night_mode: t.night_mode ?? "auto",
    night_brightness: t.night_brightness ?? 0.55,
    speed_size: t.speed_size ?? 36,
    rpm_width: t.rpm_width ?? 44,
  });
  const patch = (p: Partial<ThemeConfig>) => setTheme({ ...theme(), ...p });

  const [presetStatus, setPresetStatus] = createSignal("");
  const applyPreset = async (name: string, p: ThemeConfig) => {
    const merged = { ...theme(), ...p };
    setTheme(merged);
    const err = await postSection("theme", merged);
    setPresetStatus(err ?? `${name} applied`);
    setTimeout(() => setPresetStatus(""), 2000);
  };

  return (
    <Card title="Appearance" id="appearance" onSave={() => postSection("theme", theme())}>
      {/* one-tap skins — apply + save immediately */}
      <div class="presets">
        <For each={THEME_PRESETS}>
          {(p) => (
            <button
              class="preset"
              style={{
                "font-family": FONTS[p.theme.font ?? "chakra"].display,
                color: p.theme.accent,
                "border-color": p.theme.accent + "55",
              }}
              onClick={() => void applyPreset(p.name, p.theme)}
            >
              <span class="preset-name">{p.name}</span>
              <span class="preset-hint">{p.hint}</span>
            </button>
          )}
        </For>
      </div>
      <Show when={presetStatus()}>
        <p class="ok">✓ {presetStatus()}</p>
      </Show>

      <div class="row">
        <label>Font</label>
        <div class="seg">
          <For each={Object.entries(FONTS)}>
            {([key, f]) => (
              <button
                classList={{ active: theme().font === key }}
                style={{ "font-family": f.display }}
                onClick={() => patch({ font: key as FontKey })}
              >
                {f.name}
              </button>
            )}
          </For>
        </div>
      </div>

      <div class="row">
        <label>Accent</label>
        <div class="swatches">
          <For each={[...ACCENT_PRESETS]}>
            {(p) => (
              <div class="swatch-item">
                <button
                  class="swatch"
                  classList={{ active: theme().accent.toLowerCase() === p.hex }}
                  style={{ background: p.hex }}
                  onClick={() => patch({ accent: p.hex })}
                />
                <span class="swatch-name">{p.name}</span>
              </div>
            )}
          </For>
          <input
            class="hex"
            value={theme().accent}
            maxlength="7"
            onChange={(e) => patch({ accent: e.currentTarget.value })}
          />
        </div>
      </div>
      <Slider label="Glow" min={0} max={2} step={0.1} value={theme().glow}
        onInput={(v) => patch({ glow: v })} />
      <Slider label="Speed size" min={24} max={48} step={1} value={theme().speed_size}
        onInput={(v) => patch({ speed_size: v })} />
      <Slider label="RPM width" min={28} max={60} step={1} value={theme().rpm_width}
        onInput={(v) => patch({ rpm_width: v })} />
      <div class="row">
        <label>Night mode</label>
        <div class="seg">
          <For each={["auto", "on", "off"] as const}>
            {(m) => (
              <button classList={{ active: theme().night_mode === m }} onClick={() => patch({ night_mode: m })}>
                {m.toUpperCase()}
              </button>
            )}
          </For>
        </div>
      </div>
      <Slider label="Night dim" min={0.2} max={1} step={0.05} value={theme().night_brightness}
        onInput={(v) => patch({ night_brightness: v })} />
    </Card>
  );
};

const GaugesCard: Component = () => {
  const g = config().gauges ?? {};
  const [max, setMax] = createSignal(g.rpm_max ?? 7000);
  const [redline, setRedline] = createSignal(g.rpm_redline ?? 6200);
  return (
    <Card title="Gauges" id="gauges" onSave={() => postSection("gauges", { rpm_max: max(), rpm_redline: redline() })}>
      <div class="row">
        <label>RPM max</label>
        <input type="number" step="100" value={max()} onChange={(e) => setMax(Number(e.currentTarget.value))} />
        <label>Redline</label>
        <input type="number" step="100" value={redline()} onChange={(e) => setRedline(Number(e.currentTarget.value))} />
      </div>
    </Card>
  );
};

interface DebugInfo {
  uptime_s: number;
  topics: Record<string, { value: unknown; age_s: number }>;
}

const DebugCard: Component = () => {
  const [overlay, setOverlay] = createSignal(config().debug ?? false);
  const [info, setInfo] = createSignal<DebugInfo | null>(null);
  const [watching, setWatching] = createSignal(false);
  const [status, setStatus] = createSignal("");

  let timer: ReturnType<typeof setInterval> | undefined;
  const poll = async () => {
    try {
      setInfo(await (await fetch("/api/debug")).json());
    } catch {
      setInfo(null);
    }
  };
  const toggleWatch = () => {
    setWatching(!watching());
    if (watching()) {
      void poll();
      timer = setInterval(() => void poll(), 2000);
    } else {
      clearInterval(timer);
    }
  };
  onCleanup(() => clearInterval(timer));

  const saveOverlay = async (on: boolean) => {
    setOverlay(on);
    const err = await postSection("debug", on);
    setStatus(err ?? "saved");
    setTimeout(() => setStatus(""), 1500);
  };

  const fmt = (v: unknown) => {
    const s = typeof v === "object" ? JSON.stringify(v) : String(v);
    return s.length > 42 ? s.slice(0, 41) + "…" : s;
  };

  return (
    <section class="card" id="debug">
      <h2>Debug</h2>
      <div class="row">
        <label>Debug overlay on the HUD</label>
        <input type="checkbox" checked={overlay()} onChange={(e) => void saveOverlay(e.currentTarget.checked)} />
        <Show when={status()}>
          <span class="ok">✓ {status()}</span>
        </Show>
      </div>
      <button class="add" onClick={toggleWatch}>
        {watching() ? "stop watching" : "watch live topics"}
      </button>
      <Show when={watching() && info()}>
        <p class="hint">uptime {Math.round(info()!.uptime_s)}s · {Object.keys(info()!.topics).length} topics</p>
        <div class="debug-table">
          <For each={Object.entries(info()!.topics)}>
            {([name, t]) => (
              <div class="debug-row" classList={{ stale: t.age_s > 10 }}>
                <span class="debug-topic">{name}</span>
                <span class="debug-value">{fmt(t.value)}</span>
                <span class="debug-age">{t.age_s < 2 ? "" : `${Math.round(t.age_s)}s`}</span>
              </div>
            )}
          </For>
        </div>
      </Show>
    </section>
  );
};

const TripCard: Component = () => {
  const [status, setStatus] = createSignal("");
  const reset = async () => {
    await fetch("/api/trip/reset", { method: "POST" });
    setStatus("trip reset");
    setTimeout(() => setStatus(""), 2000);
  };
  return (
    <section class="card" id="trip">
      <h2>Trip computer</h2>
      <div class="row">
        <button class="grow" onClick={() => void reset()}>
          Reset trip (distance / fuel / time)
        </button>
        <Show when={status()}>
          <span class="ok">✓ {status()}</span>
        </Show>
      </div>
    </section>
  );
};

export const Settings: Component = () => (
  <main class="settings">
    <header class="topbar">
      <h1>HUD Settings</h1>
      <nav class="topnav">
        <For each={[...NAV]}>{(n) => <a href={`#${n.id}`}>{n.label}</a>}</For>
      </nav>
    </header>
    <AppearanceCard />
    <UnitsCard />
    <MirrorCard />
    <GaugesCard />
    <LayoutCard />
    <AlertsCard />
    <LocationCard />
    <TripCard />
    <DebugCard />
    <p class="hint">
      Changes apply to the HUD live. Display position/scale is easier to calibrate on the HUD
      itself: press <b>C</b> with a keyboard attached.
    </p>
  </main>
);
