/**
 * Topic → signal store. Each bus topic maps to one Solid signal; a widget
 * subscribing to `vehicle.rpm` re-renders only the DOM nodes reading that
 * signal when a new value arrives — cheap even at high frequency.
 */
import { createSignal, type Accessor } from "solid-js";

/** Known topic shapes — mirror of the backend's normalized channels. */
export interface Topics {
  "vehicle.speed_kph": number;
  "vehicle.rpm": number;
  "vehicle.coolant_c": number;
  "vehicle.fuel_pct": number;
  "vehicle.throttle_pct": number;
  "vehicle.gear": string;
  "vehicle.battery_v": number;
  "vehicle.ambient_c": number;
  "vehicle.dtc_codes": string[];
  "vehicle.maf_gs": number;
  "vehicle.source": "can" | "elm327" | "none";
  // CAN-only channels (absent on the ELM327 fallback — widgets hide)
  "vehicle.lane_left": number;
  "vehicle.lane_right": number;
  "vehicle.lda_buzzer": number;
  "vehicle.rsa_sign": number;
  "vehicle.rsa_value": number;
  "vehicle.rsa_unit": number;
  "vehicle.bsm_status": number;
  "vehicle.bsm_buzzer": number;
  "vehicle.lights_on": number;
  "vehicle.cruise_on": number;
  "vehicle.cruise_set": number;
  "vehicle.brake_on": number;
  "vehicle.brake_hold": number;
  "vehicle.pcs_warn": number;
  "vehicle.trans_temp_c": number;
  "vehicle.intake_temp_c": number;
  "vehicle.odometer_km": number;
  "vehicle.steer_deg": number;
  // Full active set on every change — last-value semantics mean new/reconnecting
  // clients are always primed with the current alerts, not a partial event stream.
  "alerts.active": { id: string; level: "warn" | "critical"; message: string }[];
  "net.online": boolean;
  "system.cpu_temp_c": number;
  "weather.current": {
    temp_c: number;
    feels_c: number;
    code: number; // WMO weather code
    wind_kph: number;
    is_day: boolean;
    fetched_at?: number;
  };
  "traffic.flow": {
    current_kph: number;
    freeflow_kph: number;
    ratio: number;
    road_closed: boolean;
    fetched_at?: number;
  };
  "gps.position": { lat: number; lon: number };
  "gps.speed_kph": number;
  "gps.heading": number;
  "config.updated": { section: string };
  "road.speed_limit_kph": number | null;
  "road.limit": {
    limit_kph: number;
    limit_mph: number;
    estimated: boolean;
    highway: string;
    name: string | null;
  } | null;
  "trip.distance_km": number;
  "trip.time_s": number;
  "trip.fuel_l": number;
  "trip.avg_lp100k": number | null;
  "trip.instant_lp100k": number | null;
  "trip.zero_sixty": { last_s: number | null; best_s: number | null };
}

interface Entry {
  get: Accessor<unknown>;
  set: (v: unknown) => void;
}

const entries = new Map<string, Entry>();

function entry(topic: string): Entry {
  let e = entries.get(topic);
  if (!e) {
    const [get, set] = createSignal<unknown>(undefined);
    e = { get, set: (v) => set(() => v) };
    entries.set(topic, e);
  }
  return e;
}

export function useTopic<K extends keyof Topics>(topic: K): Accessor<Topics[K] | undefined>;
export function useTopic(topic: string): Accessor<unknown>;
export function useTopic(topic: string): Accessor<unknown> {
  return entry(topic).get;
}

/** Apply a server batch: { topic: [value, ts] }. */
export function applyBatch(topics: Record<string, [unknown, number]>): void {
  for (const [topic, [value]] of Object.entries(topics)) {
    entry(topic).set(value);
  }
}
