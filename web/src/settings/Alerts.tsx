import { createSignal, For, Show, type Component } from "solid-js";
import { config } from "../core/config";
import { METRICS, type MetricKind } from "../core/names";
import { autoSave, Group, Icon, NumberField, Page, Row, Segmented, Sheet } from "./ui";

interface Rule {
  topic: string;
  above?: number | null;
  below?: number | null;
  above_topic?: string | null;
  below_topic?: string | null;
  tolerance?: number | null;
  level: "warn" | "critical";
  message: string;
}

const LIMIT_TOPIC = "road.speed_limit_kph";
const isLimitRule = (r: Rule) => r.above_topic === LIMIT_TOPIC;

/** Exactly the fields the API accepts. */
function clean(r: Rule) {
  const base = { topic: r.topic, level: r.level, message: r.message.trim() || "ALERT" };
  if (r.above_topic != null) return { ...base, above_topic: r.above_topic, tolerance: r.tolerance ?? 0 };
  if (r.below_topic != null) return { ...base, below_topic: r.below_topic, tolerance: r.tolerance ?? 0 };
  return { ...base, ...(r.below != null ? { below: r.below } : { above: r.above ?? 0 }) };
}

// ---- units: rules are stored in °C / km/h; shown in the user's units ------

const mph = () => (config().units?.speed ?? "mph") === "mph";
const fahrenheit = () => (config().units?.temp ?? "f") === "f";

function unitOf(kind: MetricKind): string {
  return { temp: fahrenheit() ? "°F" : "°C", speed: mph() ? "mph" : "km/h", rpm: "rpm", percent: "%", volts: "V" }[kind];
}
function toDisplay(kind: MetricKind, v: number): number {
  if (kind === "temp" && fahrenheit()) return Math.round(v * 1.8 + 32);
  if (kind === "speed" && mph()) return Math.round(v * 0.621371);
  return kind === "volts" ? Math.round(v * 10) / 10 : Math.round(v);
}
function fromDisplay(kind: MetricKind, v: number): number {
  if (kind === "temp" && fahrenheit()) return Math.round(((v - 32) / 1.8) * 10) / 10;
  if (kind === "speed" && mph()) return Math.round((v / 0.621371) * 10) / 10;
  return v;
}
/** Speed *differences* (the limit tolerance) convert without an offset. */
const toDisplayDelta = (kph: number) => Math.round(mph() ? kph * 0.621371 : kph);
const fromDisplayDelta = (v: number) => Math.round((mph() ? v / 0.621371 : v) * 10) / 10;

const kindOf = (topic: string): MetricKind => METRICS[topic]?.kind ?? "rpm";
const metricLabel = (topic: string) => METRICS[topic]?.label ?? topic;

function sentence(r: Rule): string {
  if (isLimitRule(r)) return `Speed is more than ${toDisplayDelta(r.tolerance ?? 0)} ${unitOf("speed")} over the limit`;
  const k = kindOf(r.topic);
  const v = r.below != null ? r.below : r.above ?? 0;
  return `${metricLabel(r.topic)} ${r.below != null ? "below" : "above"} ${toDisplay(k, v)} ${unitOf(k)}`;
}

export const Alerts: Component = () => {
  const initial = (config() as { alerts?: { rules?: Rule[] } }).alerts?.rules ?? [];
  const [rules, setRules] = createSignal<Rule[]>(initial.map((r) => ({ ...r })));
  const [editing, setEditing] = createSignal<number | null>(null);
  const save = autoSave("alerts.rules");
  const commit = (next: Rule[], delay = 500) => {
    setRules(next);
    save(next.map(clean), delay);
  };
  const update = (i: number, patch: Partial<Rule>, delay = 500) =>
    commit(rules().map((r, j) => (j === i ? { ...r, ...patch } : r)), delay);
  const rule = () => (editing() !== null ? rules()[editing()!] : undefined);

  const addRule = () => {
    commit([...rules(), { topic: "vehicle.coolant_c", above: 110, level: "warn", message: "COOLANT HOT" }], 0);
    setEditing(rules().length - 1);
  };
  const changeMetric = (i: number, topic: string) => {
    if (topic === "__limit") {
      update(i, { topic: "vehicle.speed_kph", above_topic: LIMIT_TOPIC, tolerance: 8, above: null, below: null,
        message: "OVERSPEED" });
      return;
    }
    const r = rules()[i];
    update(i, { topic, above_topic: null, below_topic: null, tolerance: null,
      ...(r.below != null ? { below: r.below } : { above: r.above ?? 0 }) });
  };

  return (
    <Page title="Alerts" back>
      <p class="lede">Warnings that flash on the windshield when a reading crosses a limit.</p>

      <Group>
        <Show when={rules().length > 0}
          fallback={<p class="empty">No alerts yet. Add one to get a warning on the windshield when, for example, the engine runs hot.</p>}>
          <For each={rules()}>
            {(r, i) => (
              <button type="button" class="row rule-row" onClick={() => setEditing(i())}>
                <span class="sev" classList={{ critical: r.level === "critical" }}>
                  {r.level === "critical" ? "Critical" : "Warning"}
                </span>
                <span class="rule-text">
                  <span class="rule-sentence">{sentence(r)}</span>
                  <span class="rule-msg">Shows “{r.message}”</span>
                </span>
                <Icon name="chevron" class="chev" />
              </button>
            )}
          </For>
        </Show>
        <button type="button" class="row action" onClick={addRule}>
          <Icon name="plus" /><span>Add alert</span>
        </button>
      </Group>

      <Show when={rule()}>
        <Sheet title="Edit alert" onClose={() => setEditing(null)}>
          <div class="form">
            <Row label="Watch" for="rule-metric">
              <select
                id="rule-metric"
                value={isLimitRule(rule()!) ? "__limit" : rule()!.topic}
                onChange={(e) => changeMetric(editing()!, e.currentTarget.value)}
              >
                <For each={Object.entries(METRICS)}>{([t, m]) => <option value={t}>{m.label}</option>}</For>
                <option value="__limit">Speed over the limit</option>
              </select>
            </Row>

            <Show
              when={!isLimitRule(rule()!)}
              fallback={
                <Row label="Allowed over the limit" hint="Needs GPS and the speed-limit map" for="rule-tol">
                  <NumberField id="rule-tol" unit={unitOf("speed")} min={0}
                    value={toDisplayDelta(rule()!.tolerance ?? 0)}
                    onChange={(v) => update(editing()!, { tolerance: fromDisplayDelta(v) })} />
                </Row>
              }
            >
              <Row label="When it is" for="rule-cond">
                <Segmented
                  id="rule-cond"
                  label="Condition"
                  value={rule()!.below != null ? "below" : "above"}
                  options={[{ value: "above", label: "Above" }, { value: "below", label: "Below" }]}
                  onChange={(c) => {
                    const v = rule()!.below ?? rule()!.above ?? 0;
                    update(editing()!, c === "below" ? { below: v, above: null } : { above: v, below: null });
                  }}
                />
              </Row>
              <Row label="Limit" for="rule-value">
                <NumberField
                  id="rule-value"
                  unit={unitOf(kindOf(rule()!.topic))}
                  step={kindOf(rule()!.topic) === "volts" ? 0.1 : 1}
                  value={toDisplay(kindOf(rule()!.topic), rule()!.below ?? rule()!.above ?? 0)}
                  onChange={(v) => {
                    const stored = fromDisplay(kindOf(rule()!.topic), v);
                    update(editing()!, rule()!.below != null ? { below: stored } : { above: stored });
                  }}
                />
              </Row>
            </Show>

            <Row label="Severity" for="rule-level">
              <Segmented
                id="rule-level"
                label="Severity"
                value={rule()!.level}
                options={[{ value: "warn", label: "Warning" }, { value: "critical", label: "Critical" }]}
                onChange={(v) => update(editing()!, { level: v as Rule["level"] })}
              />
            </Row>
            <label class="field">
              <span class="row-label">Message on the windshield</span>
              <input
                id="rule-message"
                class="text"
                maxlength="40"
                value={rule()!.message}
                autocapitalize="characters"
                onInput={(e) => update(editing()!, { message: e.currentTarget.value.toUpperCase() }, 700)}
              />
              <span class="row-hint">Short and in capitals reads best at a glance. Up to 40 characters.</span>
            </label>
          </div>
          <button type="button" class="btn danger wide"
            onClick={() => { const i = editing()!; setEditing(null); commit(rules().filter((_, j) => j !== i), 0); }}>
            <Icon name="trash" /> Delete alert
          </button>
        </Sheet>
      </Show>
    </Page>
  );
};
