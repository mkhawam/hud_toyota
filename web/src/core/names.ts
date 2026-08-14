/**
 * Widget and slot name lists shared by the HUD registry and the settings
 * page. Names only — importing this never pulls widget components into
 * the settings bundle.
 */
export const WIDGET_NAMES = [
  "speed",
  "rpm",
  "clock",
  "coolant",
  "fuel",
  "alerts",
  "source",
  "weather",
  "traffic",
  "dtc",
  "trip",
  "zerosixty",
  "speedlimit",
  "lanes",
  "cruise",
  "transtemp",
  "intaketemp",
] as const;

export const SLOTS = [
  "top-left",
  "top-center",
  "top-right",
  "center-left",
  "center",
  "center-right",
  "bottom-left",
  "bottom-center",
  "bottom-right",
] as const;

/** Topics worth suggesting in the alert-rule editor. */
export const ALERT_TOPICS = [
  "vehicle.speed_kph",
  "vehicle.rpm",
  "vehicle.coolant_c",
  "vehicle.fuel_pct",
  "vehicle.battery_v",
  "system.cpu_temp_c",
] as const;
