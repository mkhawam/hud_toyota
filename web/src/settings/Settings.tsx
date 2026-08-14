import { createSignal, For, Show, type Component, type JSX } from "solid-js";
import { config, type LayoutItem } from "../core/config";
import { ALERT_TOPICS, SLOTS, WIDGET_NAMES } from "../core/names";

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
    <section class="card">
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
    <Card title="Units" onSave={() => postSection("units", { speed: speed(), temp: temp() })}>
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
    <Card title="Widget layout" onSave={() => postSection("layout", items())}>
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
    <Card title="Home location" onSave={() => postSection("location", { lat: lat(), lon: lon() })}>
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

const TripCard: Component = () => {
  const [status, setStatus] = createSignal("");
  const reset = async () => {
    await fetch("/api/trip/reset", { method: "POST" });
    setStatus("trip reset");
    setTimeout(() => setStatus(""), 2000);
  };
  return (
    <section class="card">
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
    <h1>HUD Settings</h1>
    <UnitsCard />
    <MirrorCard />
    <LayoutCard />
    <AlertsCard />
    <LocationCard />
    <TripCard />
    <p class="hint">
      Changes apply to the HUD live. Display position/scale is easier to calibrate on the HUD
      itself: press <b>C</b> with a keyboard attached.
    </p>
  </main>
);
