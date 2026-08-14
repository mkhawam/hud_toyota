import { createResource, createSignal, For, Show, type Component } from "solid-js";
import { speedUnit } from "../core/config";
import { SpeedChart } from "./SpeedChart";

export interface Drive {
  id: number;
  started_at: number;
  ended_at: number | null;
  distance_km: number;
  fuel_l: number;
  max_speed_kph: number;
  avg_moving_kph: number;
  sample_count: number;
}

export interface Sample {
  drive_id: number;
  ts: number;
  speed_kph: number | null;
  rpm: number | null;
  coolant_c: number | null;
  fuel_pct: number | null;
  lat: number | null;
  lon: number | null;
  limit_kph: number | null;
}

const KPH_TO_MPH = 0.621371;
const LP100K_TO_MPG = 235.215;

const fetchDrives = async (): Promise<Drive[]> => (await fetch("/api/drives")).json();
const fetchSamples = async (id: number): Promise<Sample[]> =>
  (await fetch(`/api/drives/${id}/samples`)).json();

function fmtDate(ts: number): string {
  return new Date(ts * 1000).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function fmtDuration(d: Drive): string {
  if (d.ended_at == null) return "…";
  const s = d.ended_at - d.started_at;
  return `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}`;
}

export const Trips: Component = () => {
  const [drives] = createResource(fetchDrives);
  const [selected, setSelected] = createSignal<Drive | null>(null);
  const [samples] = createResource(() => selected()?.id, fetchSamples);
  const [showTable, setShowTable] = createSignal(false);

  const mph = () => speedUnit() === "mph";
  const dist = (km: number) => (mph() ? `${(km * KPH_TO_MPH).toFixed(1)} mi` : `${km.toFixed(1)} km`);
  const speed = (kph: number) => `${Math.round(mph() ? kph * KPH_TO_MPH : kph)} ${mph() ? "mph" : "km/h"}`;
  const econ = (d: Drive) => {
    if (d.distance_km < 0.5 || d.fuel_l <= 0) return "--";
    const lp100k = (d.fuel_l / d.distance_km) * 100;
    return mph() ? `${(LP100K_TO_MPG / lp100k).toFixed(1)} mpg` : `${lp100k.toFixed(1)} L/100`;
  };

  return (
    <main class="trips">
      <h1>Drives</h1>

      <Show when={drives()} fallback={<p class="empty">Loading…</p>}>
        <Show when={drives()!.length > 0} fallback={<p class="empty">No drives recorded yet.</p>}>
          <table class="drive-list">
            <thead>
              <tr>
                <th>When</th>
                <th>Distance</th>
                <th>Time</th>
                <th>Economy</th>
                <th>Max</th>
              </tr>
            </thead>
            <tbody>
              <For each={drives()}>
                {(d) => (
                  <tr
                    classList={{ selected: selected()?.id === d.id }}
                    onClick={() => setSelected(selected()?.id === d.id ? null : d)}
                  >
                    <td>{fmtDate(d.started_at)}</td>
                    <td>{dist(d.distance_km)}</td>
                    <td>{fmtDuration(d)}</td>
                    <td>{econ(d)}</td>
                    <td>{speed(d.max_speed_kph)}</td>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
        </Show>
      </Show>

      <Show when={selected()}>
        <section class="detail">
          <h2>{fmtDate(selected()!.started_at)}</h2>
          <Show when={samples()} fallback={<p class="empty">Loading samples…</p>}>
            <SpeedChart samples={samples()!} />
            <button class="toggle" onClick={() => setShowTable(!showTable())}>
              {showTable() ? "hide" : "show"} data table
            </button>
            <Show when={showTable()}>
              <table class="sample-table">
                <thead>
                  <tr>
                    <th>t</th>
                    <th>speed</th>
                    <th>limit</th>
                    <th>rpm</th>
                    <th>coolant</th>
                  </tr>
                </thead>
                <tbody>
                  <For each={samples()!.filter((_, i) => i % 10 === 0)}>
                    {(s) => (
                      <tr>
                        <td>{Math.round(s.ts - selected()!.started_at)}s</td>
                        <td>{s.speed_kph != null ? speed(s.speed_kph) : "--"}</td>
                        <td>{s.limit_kph != null ? speed(s.limit_kph) : "--"}</td>
                        <td>{s.rpm != null ? Math.round(s.rpm) : "--"}</td>
                        <td>{s.coolant_c != null ? `${Math.round(s.coolant_c)}°C` : "--"}</td>
                      </tr>
                    )}
                  </For>
                </tbody>
              </table>
            </Show>
          </Show>
        </section>
      </Show>
    </main>
  );
};
