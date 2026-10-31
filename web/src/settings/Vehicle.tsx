import { createSignal, type Component } from "solid-js";
import { config } from "../core/config";
import { autoSave, Group, NumberField, Page, Row, Segmented } from "./ui";

export const Vehicle: Component = () => {
  const [speed, setSpeed] = createSignal(config().units?.speed ?? "mph");
  const [temp, setTemp] = createSignal(config().units?.temp ?? "f");
  const saveUnits = autoSave("units");
  const units = () => ({ speed: speed(), temp: temp() });

  const g = config().gauges ?? {};
  const [gauges, setGauges] = createSignal({
    rpm_max: g.rpm_max ?? 7000,
    rpm_redline: g.rpm_redline ?? 6200,
    power_max_kw: g.power_max_kw ?? 150,
    power_regen_kw: g.power_regen_kw ?? 50,
  });
  const saveGauges = autoSave("gauges");
  const patchGauges = (p: Partial<ReturnType<typeof gauges>>) => {
    const next = { ...gauges(), ...p };
    setGauges(next);
    saveGauges(next, 0);
  };

  const hasPower = () => (config().layout ?? []).some((it) => it.widget === "power");

  return (
    <Page title="Units & gauges" back>
      <Group title="Units">
        <Row label="Speed" for="units-speed">
          <Segmented id="units-speed" label="Speed units" value={speed()}
            options={[{ value: "mph", label: "mph" }, { value: "kph", label: "km/h" }]}
            onChange={(v) => { setSpeed(v as "mph" | "kph"); saveUnits(units(), 0); }} />
        </Row>
        <Row label="Temperature" for="units-temp">
          <Segmented id="units-temp" label="Temperature units" value={temp()}
            options={[{ value: "f", label: "°F" }, { value: "c", label: "°C" }]}
            onChange={(v) => { setTemp(v as "f" | "c"); saveUnits(units(), 0); }} />
        </Row>
      </Group>

      <Group title="Tachometer" note="The red segments start at the redline. Redline must be below the top of the scale.">
        <Row label="Top of scale" for="rpm-max">
          <NumberField id="rpm-max" unit="rpm" step={100} min={3000} max={12000} value={gauges().rpm_max}
            onChange={(v) => patchGauges({ rpm_max: v })} />
        </Row>
        <Row label="Redline" for="rpm-redline">
          <NumberField id="rpm-redline" unit="rpm" step={100} min={2000} max={12000} value={gauges().rpm_redline}
            onChange={(v) => patchGauges({ rpm_redline: v })} />
        </Row>
      </Group>

      <Group
        title="Hybrid power meter"
        note={hasPower()
          ? "Charging fills left of center, power fills right. The top fifth of the power side shows red."
          : "Add the Hybrid power widget in Layout to show this meter."}
      >
        <Row label="Full power" for="power-max">
          <NumberField id="power-max" unit="kW" step={5} min={20} max={500} value={gauges().power_max_kw}
            onChange={(v) => patchGauges({ power_max_kw: v })} />
        </Row>
        <Row label="Full charging" for="power-regen">
          <NumberField id="power-regen" unit="kW" step={5} min={5} max={200} value={gauges().power_regen_kw}
            onChange={(v) => patchGauges({ power_regen_kw: v })} />
        </Row>
      </Group>
    </Page>
  );
};
