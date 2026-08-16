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
    return "no connection";
  }
}

/** iOS-style auto-save: debounce writes, surface a quiet status. */
function autoSaver(section: string) {
  const [status, setStatus] = createSignal<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = createSignal("");
  let timer: ReturnType<typeof setTimeout> | undefined;
  const save = (value: unknown, delay = 450) => {
    clearTimeout(timer);
    setStatus("saving");
    timer = setTimeout(async () => {
      const err = await postSection(section, value);
      if (err) {
        setStatus("error");
        setError(err);
      } else {
        setStatus("saved");
        setTimeout(() => setStatus((s) => (s === "saved" ? "idle" : s)), 1200);
      }
    }, delay);
  };
  onCleanup(() => clearTimeout(timer));
  return { save, status, error };
}

/** Grouped inset list: small-caps title above, rounded group, footer below. */
const Group: Component<{
  title?: string;
  id?: string;
  status?: () => "idle" | "saving" | "saved" | "error";
  error?: () => string;
  footer?: string;
  children: JSX.Element;
}> = (props) => (
  <section class="group-wrap" id={props.id}>
    <Show when={props.title}>
      <div class="group-title">
        <span>{props.title}</span>
        <Show when={props.status}>
          <span class="group-status" classList={{ show: props.status!() !== "idle" }}>
            {props.status!() === "error" ? "⚠ not saved" : props.status!() === "saving" ? "…" : "✓ saved"}
          </span>
        </Show>
      </div>
    </Show>
    <div class="group">{props.children}</div>
    <Show when={props.status?.() === "error" && props.error}>
      <div class="group-footer error">{props.error!()}</div>
    </Show>
    <Show when={props.footer}>
      <div class="group-footer">{props.footer}</div>
    </Show>
  </section>
);

const Row: Component<{ label?: string; stacked?: boolean; children: JSX.Element }> = (props) => (
  <div class="ios-row" classList={{ stacked: props.stacked }}>
    <Show when={props.label}>
      <span class="row-label">{props.label}</span>
    </Show>
    <div class="row-control">{props.children}</div>
  </div>
);

const Seg: Component<{
  options: readonly { value: string; label: string; font?: string }[];
  value: () => string;
  onChange: (v: string) => void;
}> = (props) => (
  <div class="seg">
    <For each={[...props.options]}>
      {(o) => (
        <button
          classList={{ active: props.value() === o.value }}
          style={o.font ? { "font-family": o.font } : undefined}
          onClick={() => props.onChange(o.value)}
        >
          {o.label}
        </button>
      )}
    </For>
  </div>
);

// ---- sections -------------------------------------------------------------

const AppearanceGroup: Component = () => {
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
  const saver = autoSaver("theme");
  const patch = (p: Partial<ThemeConfig>, delay = 450) => {
    const merged = { ...theme(), ...p };
    setTheme(merged);
    saver.save(merged, delay);
  };

  return (
    <>
      <Group title="Theme presets" id="appearance">
        <div class="presets">
          <For each={THEME_PRESETS}>
            {(p) => (
              <button
                class="preset"
                style={{ "font-family": FONTS[p.theme.font ?? "chakra"].display, color: p.theme.accent }}
                onClick={() => patch(p.theme, 0)}
              >
                <span class="preset-name">{p.name}</span>
                <span class="preset-hint">{p.hint}</span>
              </button>
            )}
          </For>
        </div>
      </Group>

      <Group title="Appearance" status={saver.status} error={saver.error}>
        <Row label="Font">
          <Seg
            options={Object.entries(FONTS).map(([value, f]) => ({ value, label: f.name, font: f.display }))}
            value={() => theme().font}
            onChange={(v) => patch({ font: v as FontKey })}
          />
        </Row>
        <Row label="Accent" stacked>
          <div class="swatches">
            <For each={[...ACCENT_PRESETS]}>
              {(p) => (
                <button
                  class="swatch"
                  classList={{ active: theme().accent.toLowerCase() === p.hex }}
                  style={{ background: p.hex }}
                  title={p.name}
                  onClick={() => patch({ accent: p.hex })}
                />
              )}
            </For>
            <input
              class="hex"
              value={theme().accent}
              maxlength="7"
              onChange={(e) => patch({ accent: e.currentTarget.value })}
            />
          </div>
        </Row>
        <Row label="Glow">
          <input type="range" min="0" max="2" step="0.1" value={theme().glow}
            onInput={(e) => patch({ glow: Number(e.currentTarget.value) })} />
          <span class="row-value">{theme().glow.toFixed(1)}</span>
        </Row>
        <Row label="Speed size">
          <input type="range" min="24" max="48" step="1" value={theme().speed_size}
            onInput={(e) => patch({ speed_size: Number(e.currentTarget.value) })} />
          <span class="row-value">{theme().speed_size}</span>
        </Row>
        <Row label="Gauge width">
          <input type="range" min="28" max="60" step="1" value={theme().rpm_width}
            onInput={(e) => patch({ rpm_width: Number(e.currentTarget.value) })} />
          <span class="row-value">{theme().rpm_width}</span>
        </Row>
        <Row label="Night mode">
          <Seg
            options={[
              { value: "auto", label: "Auto" },
              { value: "on", label: "On" },
              { value: "off", label: "Off" },
            ]}
            value={() => theme().night_mode}
            onChange={(v) => patch({ night_mode: v as "auto" | "on" | "off" })}
          />
        </Row>
        <Row label="Night dim">
          <input type="range" min="0.2" max="1" step="0.05" value={theme().night_brightness}
            onInput={(e) => patch({ night_brightness: Number(e.currentTarget.value) })} />
          <span class="row-value">{theme().night_brightness.toFixed(2)}</span>
        </Row>
      </Group>
    </>
  );
};

const UnitsGroup: Component = () => {
  const [speed, setSpeed] = createSignal(config().units?.speed ?? "mph");
  const [temp, setTemp] = createSignal(config().units?.temp ?? "f");
  const saver = autoSaver("units");
  const save = () => saver.save({ speed: speed(), temp: temp() }, 0);
  return (
    <Group title="Units" id="units" status={saver.status} error={saver.error}>
      <Row label="Speed">
        <Seg
          options={[{ value: "mph", label: "MPH" }, { value: "kph", label: "KM/H" }]}
          value={speed}
          onChange={(v) => { setSpeed(v as "mph" | "kph"); save(); }}
        />
      </Row>
      <Row label="Temperature">
        <Seg
          options={[{ value: "f", label: "°F" }, { value: "c", label: "°C" }]}
          value={temp}
          onChange={(v) => { setTemp(v as "f" | "c"); save(); }}
        />
      </Row>
    </Group>
  );
};

const ProjectionGroup: Component = () => {
  const [mirror, setMirror] = createSignal(config().mirror ?? true);
  const saver = autoSaver("mirror");
  return (
    <Group
      title="Projection"
      status={saver.status}
      error={saver.error}
      footer="Mirrored for the windshield reflection. Position and scale are calibrated on the HUD itself with the C key."
    >
      <Row label="Mirror image">
        <input
          type="checkbox"
          checked={mirror()}
          onChange={(e) => { setMirror(e.currentTarget.checked); saver.save(e.currentTarget.checked, 0); }}
        />
      </Row>
    </Group>
  );
};

const LayoutGroup: Component = () => {
  const [items, setItems] = createSignal<LayoutItem[]>([...(config().layout ?? [])]);
  const saver = autoSaver("layout");
  const commit = (next: LayoutItem[], delay = 700) => {
    setItems(next);
    saver.save(next, delay);
  };
  const update = (i: number, patch: Partial<LayoutItem>) =>
    commit(items().map((it, j) => (j === i ? { ...it, ...patch } : it)));
  return (
    <Group title="Widget layout" id="layout" status={saver.status} error={saver.error}>
      <For each={items()}>
        {(item, i) => (
          <div class="ios-row">
            <div class="row-control layout-row">
              <select value={item.widget} onChange={(e) => update(i(), { widget: e.currentTarget.value })}>
                <For each={[...WIDGET_NAMES]}>{(w) => <option value={w}>{w}</option>}</For>
              </select>
              <select value={item.slot} onChange={(e) => update(i(), { slot: e.currentTarget.value })}>
                <For each={[...SLOTS]}>{(s) => <option value={s}>{s}</option>}</For>
              </select>
              <button class="remove" onClick={() => commit(items().filter((_, j) => j !== i()), 0)}>
                ✕
              </button>
            </div>
          </div>
        )}
      </For>
      <button class="action-row" onClick={() => commit([...items(), { widget: "clock", slot: "top-left" }], 700)}>
        Add widget
      </button>
    </Group>
  );
};

const GaugesGroup: Component = () => {
  const g = config().gauges ?? {};
  const [max, setMax] = createSignal(g.rpm_max ?? 7000);
  const [redline, setRedline] = createSignal(g.rpm_redline ?? 6200);
  const [pMax, setPMax] = createSignal(g.power_max_kw ?? 150);
  const [pRegen, setPRegen] = createSignal(g.power_regen_kw ?? 50);
  const saver = autoSaver("gauges");
  const save = () =>
    saver.save({ rpm_max: max(), rpm_redline: redline(), power_max_kw: pMax(), power_regen_kw: pRegen() });

  // Hybrid: the center meter can be the tach or the CHG/ECO/PWR power
  // gauge — switching just rewrites the layout entry.
  const layoutSaver = autoSaver("layout");
  const initialGauge = () =>
    (config().layout ?? []).some((i) => i.widget === "power") ? "power" : "rpm";
  const [gauge, setGauge] = createSignal(initialGauge());
  const switchGauge = (to: string) => {
    setGauge(to);
    const items = [...(config().layout ?? [])];
    const idx = items.findIndex((i) => i.widget === "rpm" || i.widget === "power");
    if (idx === -1) items.push({ widget: to, slot: "bottom-center" });
    else items[idx] = { ...items[idx], widget: to };
    layoutSaver.save(items, 0);
  };

  return (
    <Group title="Gauges" id="gauges" status={saver.status} error={saver.error}
      footer="Power shows the hybrid CHG / PWR meter; the kW value needs the HV CAN mapping (sim provides it on the desk).">
      <Row label="Center gauge">
        <Seg
          options={[{ value: "rpm", label: "RPM" }, { value: "power", label: "Power" }]}
          value={gauge}
          onChange={switchGauge}
        />
      </Row>
      <Row label="RPM range">
        <input type="number" step="100" value={max()}
          onChange={(e) => { setMax(Number(e.currentTarget.value)); save(); }} />
      </Row>
      <Row label="Redline">
        <input type="number" step="100" value={redline()}
          onChange={(e) => { setRedline(Number(e.currentTarget.value)); save(); }} />
      </Row>
      <Row label="Power max kW">
        <input type="number" step="5" value={pMax()}
          onChange={(e) => { setPMax(Number(e.currentTarget.value)); save(); }} />
      </Row>
      <Row label="Regen max kW">
        <input type="number" step="5" value={pRegen()}
          onChange={(e) => { setPRegen(Number(e.currentTarget.value)); save(); }} />
      </Row>
    </Group>
  );
};

interface AlertRule {
  topic: string;
  above?: number | null;
  below?: number | null;
  above_topic?: string | null;
  below_topic?: string | null;
  tolerance?: number | null;
  level: "warn" | "critical";
  message: string;
}

const isTopicRule = (r: AlertRule) => r.above_topic != null || r.below_topic != null;

/** Exactly the fields the API accepts — never round-trip anything extra. */
function cleanRule(r: AlertRule) {
  const base = { topic: r.topic, level: r.level, message: r.message };
  if (isTopicRule(r)) {
    return {
      ...base,
      ...(r.above_topic != null ? { above_topic: r.above_topic } : { below_topic: r.below_topic }),
      tolerance: r.tolerance ?? 0,
    };
  }
  return { ...base, ...(r.below != null ? { below: r.below } : { above: r.above ?? 0 }) };
}

const AlertsGroup: Component = () => {
  const initial = (config() as { alerts?: { rules?: AlertRule[] } }).alerts?.rules ?? [];
  const [rules, setRules] = createSignal<AlertRule[]>(initial.map((r) => ({ ...r })));
  const saver = autoSaver("alerts.rules");
  const commit = (next: AlertRule[], delay = 700) => {
    setRules(next);
    saver.save(next.map(cleanRule), delay);
  };
  const update = (i: number, patch: Partial<AlertRule>) =>
    commit(rules().map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const condOf = (r: AlertRule) => (r.below != null ? "below" : "above");
  const valueOf = (r: AlertRule) => r.below ?? r.above ?? 0;
  const setCond = (i: number, cond: string, value: number) =>
    update(i, cond === "below" ? { below: value, above: null } : { above: value, below: null });

  return (
    <Group title="Alerts" id="alerts" status={saver.status} error={saver.error}>
      <datalist id="topics">
        <For each={[...ALERT_TOPICS]}>{(t) => <option value={t} />}</For>
      </datalist>
      <For each={rules()}>
        {(rule, i) => (
          <div class="ios-row stacked rule">
            <div class="row-control rule-line">
              <input
                class="grow"
                list="topics"
                value={rule.topic}
                placeholder="topic"
                onChange={(e) => update(i(), { topic: e.currentTarget.value })}
              />
              <button class="remove" onClick={() => commit(rules().filter((_, j) => j !== i()), 0)}>
                ✕
              </button>
            </div>
            <div class="row-control rule-line">
              <Show
                when={!isTopicRule(rule)}
                fallback={
                  <span class="rule-ref">
                    vs {rule.above_topic ?? rule.below_topic} +{rule.tolerance ?? 0}
                  </span>
                }
              >
                <select value={condOf(rule)} onChange={(e) => setCond(i(), e.currentTarget.value, valueOf(rule))}>
                  <option value="above">above</option>
                  <option value="below">below</option>
                </select>
                <input
                  type="number"
                  value={valueOf(rule)}
                  onChange={(e) => setCond(i(), condOf(rule), Number(e.currentTarget.value))}
                />
              </Show>
              <select
                value={rule.level}
                onChange={(e) => update(i(), { level: e.currentTarget.value as AlertRule["level"] })}
              >
                <option value="warn">warn</option>
                <option value="critical">critical</option>
              </select>
            </div>
            <div class="row-control rule-line">
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
        class="action-row"
        onClick={() =>
          commit([...rules(), { topic: "vehicle.coolant_c", above: 110, level: "warn", message: "ALERT" }], 700)
        }
      >
        Add alert rule
      </button>
    </Group>
  );
};

const LocationGroup: Component = () => {
  const loc = (config() as { location?: { lat?: number; lon?: number } }).location ?? {};
  const [lat, setLat] = createSignal(loc.lat ?? 40.4862);
  const [lon, setLon] = createSignal(loc.lon ?? -74.4518);
  const saver = autoSaver("location");
  const save = () => saver.save({ lat: lat(), lon: lon() });
  const useGps = async () => {
    const res = await fetch("/api/snapshot?pattern=gps.position");
    const snap = await res.json();
    const fix = snap["gps.position"];
    if (fix) {
      setLat(fix.lat);
      setLon(fix.lon);
      saver.save({ lat: fix.lat, lon: fix.lon }, 0);
    }
  };
  return (
    <Group
      title="Home location"
      id="location"
      status={saver.status}
      error={saver.error}
      footer="Used for weather and speed limits until there is a GPS fix."
    >
      <Row label="Latitude">
        <input type="number" step="0.0001" value={lat()}
          onChange={(e) => { setLat(Number(e.currentTarget.value)); save(); }} />
      </Row>
      <Row label="Longitude">
        <input type="number" step="0.0001" value={lon()}
          onChange={(e) => { setLon(Number(e.currentTarget.value)); save(); }} />
      </Row>
      <button class="action-row" onClick={() => void useGps()}>
        Use Current GPS Position
      </button>
    </Group>
  );
};

const TripGroup: Component = () => {
  const [status, setStatus] = createSignal("");
  const reset = async () => {
    await fetch("/api/trip/reset", { method: "POST" });
    setStatus("Trip reset");
    setTimeout(() => setStatus(""), 2000);
  };
  return (
    <Group title="Trip computer" id="trip" footer={status() || "Distance, fuel, and timers restart from zero."}>
      <button class="action-row destructive" onClick={() => void reset()}>
        Reset Trip Data
      </button>
    </Group>
  );
};

interface DebugInfo {
  uptime_s: number;
  topics: Record<string, { value: unknown; age_s: number }>;
}

const DebugGroup: Component = () => {
  const [overlay, setOverlay] = createSignal(config().debug ?? false);
  const [info, setInfo] = createSignal<DebugInfo | null>(null);
  const [watching, setWatching] = createSignal(false);
  const saver = autoSaver("debug");

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

  const fmt = (v: unknown) => {
    const s = typeof v === "object" ? JSON.stringify(v) : String(v);
    return s.length > 42 ? s.slice(0, 41) + "…" : s;
  };

  return (
    <Group title="Debug" id="debug" status={saver.status} error={saver.error}
      footer="The overlay also toggles with the D key on the HUD.">
      <Row label="HUD debug overlay">
        <input type="checkbox" checked={overlay()}
          onChange={(e) => { setOverlay(e.currentTarget.checked); saver.save(e.currentTarget.checked, 0); }} />
      </Row>
      <button class="action-row" onClick={toggleWatch}>
        {watching() ? "Stop Watching Topics" : "Watch Live Topics"}
      </button>
      <Show when={watching() && info()}>
        <div class="ios-row stacked">
          <div class="row-control">
            <span class="rule-ref">uptime {Math.round(info()!.uptime_s)}s · {Object.keys(info()!.topics).length} topics</span>
          </div>
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
        </div>
      </Show>
    </Group>
  );
};

export const Settings: Component<{ backUrl?: string | null }> = (props) => (
  <main class="settings">
    <header class="topbar">
      <h1>HUD Settings</h1>
      <nav class="topnav">
        <Show when={props.backUrl != null}>
          <a class="back" href={props.backUrl!}>← HUD</a>
        </Show>
        <For each={[...NAV]}>{(n) => <a href={`#${n.id}`}>{n.label}</a>}</For>
      </nav>
    </header>
    <AppearanceGroup />
    <UnitsGroup />
    <ProjectionGroup />
    <LayoutGroup />
    <GaugesGroup />
    <AlertsGroup />
    <LocationGroup />
    <TripGroup />
    <DebugGroup />
  </main>
);
